from __future__ import annotations

from aiogram import Bot

from app.bot.keyboards.game import day_vote_keyboard
from app.config import Settings
from app.game.engine import GameEngine
from app.game.models import Faction, GamePhase, GameSession, RoleKey
from app.game.roles import get_role_definition
from app.game.timers import GameTimerManager
from app.services.messaging import MessagingService
from app.services.moderation import ModerationService
from app.services.registry import GameRegistry
from app.texts.events import GAME_STARTED


class GameFlowService:
    """Coordinates game phases, Telegram messages, and phase timers."""

    def __init__(
        self,
        bot: Bot,
        registry: GameRegistry,
        engine: GameEngine,
        messaging: MessagingService,
        moderation: ModerationService,
        timers: GameTimerManager,
        settings: Settings,
    ) -> None:
        self.bot = bot
        self.registry = registry
        self.engine = engine
        self.messaging = messaging
        self.moderation = moderation
        self.timers = timers
        self.settings = settings

    async def begin_game(self, session: GameSession) -> None:
        await self.bot.send_message(session.chat_id, GAME_STARTED)
        await self.moderation.set_night_permissions(session)
        await self._begin_night(session)

    async def _begin_night(self, session: GameSession) -> None:
        await self.messaging.send_night_prompts(session)
        phase_number = session.phase_number
        self.timers.schedule(
            session.chat_id,
            "night",
            self.settings.night_seconds,
            lambda: self._end_night(session.chat_id, phase_number),
        )

    async def _end_night(self, chat_id: int, phase_number: int) -> None:
        lock = await self.registry.lock_for(chat_id)
        async with lock:
            session = self.registry.get(chat_id)
            if (
                session is None
                or session.phase is not GamePhase.NIGHT
                or session.phase_number != phase_number
            ):
                return
            result = self.engine.resolve_night(session)
            await self.bot.send_message(chat_id, "\n".join(result.public_events))
            await self.messaging.send_night_results(session, result)
            if session.phase is GamePhase.FINISHED:
                await self._announce_and_finish(session)
                return

            await self.moderation.set_day_permissions(session)
            await self.bot.send_message(
                chat_id,
                "☀️ <b>Наступил день</b>\n"
                f"На обсуждение — {self.settings.discussion_seconds} секунд.",
            )
            self.timers.schedule(
                chat_id,
                "discussion",
                self.settings.discussion_seconds,
                lambda: self._end_discussion(chat_id, phase_number),
            )

    async def _end_discussion(self, chat_id: int, phase_number: int) -> None:
        lock = await self.registry.lock_for(chat_id)
        async with lock:
            session = self.registry.get(chat_id)
            if (
                session is None
                or session.phase is not GamePhase.DISCUSSION
                or session.phase_number != phase_number
            ):
                return
            self.engine.start_voting(session)
            await self.bot.send_message(
                chat_id,
                "🗳 <b>Дневное голосование</b>\nВыберите кандидата на казнь.",
                reply_markup=day_vote_keyboard(session),
            )
            self.timers.schedule(
                chat_id,
                "voting",
                self.settings.voting_seconds,
                lambda: self._end_voting(chat_id, phase_number),
            )

    async def _end_voting(self, chat_id: int, phase_number: int) -> None:
        lock = await self.registry.lock_for(chat_id)
        async with lock:
            session = self.registry.get(chat_id)
            if (
                session is None
                or session.phase is not GamePhase.VOTING
                or session.phase_number != phase_number
            ):
                return
            result = self.engine.resolve_day_vote(session)
            await self.bot.send_message(chat_id, "\n".join(result.public_events))
            if result.pending_revenge_by is not None:
                await self.messaging.send_revenge_prompt(
                    session,
                    result.pending_revenge_by,
                )
                self.timers.schedule(
                    chat_id,
                    "revenge",
                    self.settings.verdict_seconds,
                    lambda: self.resolve_revenge(
                        chat_id,
                        result.pending_revenge_by,
                        None,
                    ),
                )
                return
            await self._continue_or_finish(session)

    async def resolve_revenge(
        self,
        chat_id: int,
        best_friend_id: int,
        target_id: int | None,
    ) -> None:
        lock = await self.registry.lock_for(chat_id)
        async with lock:
            session = self.registry.get(chat_id)
            if session is None or session.pending_revenge_by != best_friend_id:
                return
            self.timers.cancel(chat_id, "revenge")
            result = self.engine.resolve_revenge(session, best_friend_id, target_id)
            if result.public_events:
                await self.bot.send_message(chat_id, "\n".join(result.public_events))
            await self._continue_or_finish(session)

    async def _continue_or_finish(self, session: GameSession) -> None:
        if session.phase is GamePhase.FINISHED:
            await self._announce_and_finish(session)
            return
        if session.phase is GamePhase.NIGHT:
            await self.moderation.set_night_permissions(session)
            await self.bot.send_message(
                session.chat_id,
                f"🌙 <b>Наступает ночь №{session.phase_number}</b>",
            )
            await self._begin_night(session)

    async def _announce_and_finish(self, session: GameSession) -> None:
        winner = self._winner_text(session.winner)
        roles = "\n".join(
            f"• {player.display_name} — "
            f"{get_role_definition(player.role).name if player.role is not None else 'без роли'}"
            for player in session.players.values()
        )
        await self.bot.send_message(
            session.chat_id,
            f"🏁 <b>Игра завершена</b>\nПобедитель: <b>{winner}</b>\n\n{roles}",
        )
        await self.moderation.restore_permissions(session)
        self.timers.cancel_all(session.chat_id)
        self.registry.remove(session.chat_id)

    async def cancel_game(self, session: GameSession) -> None:
        self.timers.cancel_all(session.chat_id)
        await self.moderation.restore_permissions(session)
        self.registry.remove(session.chat_id)

    @staticmethod
    def _winner_text(winner: Faction | RoleKey | None) -> str:
        if winner is Faction.TOWN:
            return "Мирные жители"
        if winner is Faction.MAFIA:
            return "Мафия"
        if isinstance(winner, RoleKey):
            return get_role_definition(winner).name
        return "не определён"
