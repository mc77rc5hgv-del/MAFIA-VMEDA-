from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup

from app.bot.keyboards.game import discussion_keyboard
from app.config import Settings
from app.database.repositories import StatisticsStore
from app.game.engine import GameEngine
from app.game.models import Faction, GamePhase, GameSession, RoleKey
from app.game.roles import get_role_definition
from app.game.timers import GameTimerManager
from app.services.messaging import MessagingService
from app.services.moderation import ModerationService
from app.services.registry import GameRegistry


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
        statistics: StatisticsStore,
    ) -> None:
        self.bot = bot
        self.registry = registry
        self.engine = engine
        self.messaging = messaging
        self.moderation = moderation
        self.timers = timers
        self.settings = settings
        self.statistics = statistics

    async def begin_game(self, session: GameSession) -> None:
        await self.moderation.set_night_permissions(session)
        await self._begin_night(session)

    async def _begin_night(self, session: GameSession) -> None:
        session.phase_deadline = datetime.now(UTC) + timedelta(seconds=self.settings.night_seconds)
        await self._update_game_post(
            session,
            f"🌙 <b>Ночь №{session.phase_number}</b>\n"
            f"На действия — {self.settings.night_seconds} секунд. Город засыпает…",
        )
        await self.registry.persist(session)
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
            await self.messaging.send_night_results(session, result)
            if session.phase is GamePhase.FINISHED:
                await self._announce_and_finish(session)
                return

            await self.moderation.set_day_permissions(session)
            session.phase_deadline = datetime.now(UTC) + timedelta(
                seconds=self.settings.discussion_seconds
            )
            await self._update_game_post(
                session,
                escape("\n".join(result.public_events)) + "\n\n"
                "☀️ <b>Наступил день</b>\n"
                f"На обсуждение — {self.settings.discussion_seconds} секунд.",
                reply_markup=discussion_keyboard(session),
            )
            await self.registry.persist(session)
            self.timers.schedule(
                chat_id,
                "discussion",
                self.settings.discussion_seconds,
                lambda: self._end_discussion(chat_id, phase_number),
            )

    async def end_discussion_early(self, chat_id: int, phase_number: int) -> None:
        self.timers.cancel(chat_id, "discussion")
        await self._end_discussion(chat_id, phase_number)

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
            session.phase_deadline = datetime.now(UTC) + timedelta(
                seconds=self.settings.voting_seconds
            )
            await self._update_game_post(
                session,
                "🗳 <b>Дневное голосование</b>\n"
                "Кнопки для голосования отправлены участникам в личные сообщения.",
            )
            await self.registry.persist(session)
            await self.messaging.send_day_vote_prompts(session)
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
            await self._update_game_post(session, escape("\n".join(result.public_events)))
            if result.pending_revenge_by is not None:
                session.phase_deadline = datetime.now(UTC) + timedelta(
                    seconds=self.settings.verdict_seconds
                )
                await self.registry.persist(session)
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
                await self._update_game_post(session, escape("\n".join(result.public_events)))
            await self.registry.persist(session)
            await self._continue_or_finish(session)

    async def _continue_or_finish(self, session: GameSession) -> None:
        if session.phase is GamePhase.FINISHED:
            await self._announce_and_finish(session)
            return
        if session.phase is GamePhase.NIGHT:
            await self.moderation.set_night_permissions(session)
            await self._begin_night(session)

    async def _announce_and_finish(self, session: GameSession) -> None:
        winner = self._winner_text(session.winner)
        roles = "\n".join(
            f"• {escape(player.display_name)} — "
            f"{get_role_definition(player.role).name if player.role is not None else 'без роли'}"
            for player in session.players.values()
        )
        session.phase_deadline = None
        await self._update_game_post(
            session,
            f"🏁 <b>Игра завершена</b>\nПобедитель: <b>{winner}</b>\n\n{roles}",
        )
        await self.moderation.restore_permissions(session)
        await self.statistics.record_finished_game(session)
        self.timers.cancel_all(session.chat_id)
        await self.registry.discard(session.chat_id)

    async def cancel_game(self, session: GameSession) -> None:
        self.timers.cancel_all(session.chat_id)
        await self.moderation.restore_permissions(session)
        await self.registry.discard(session.chat_id)

    async def resume(self, session: GameSession) -> None:
        """Restore the timer and moderation state after a process restart."""
        if session.phase is GamePhase.LOBBY:
            return
        if session.phase is GamePhase.FINISHED:
            await self._announce_and_finish(session)
            return
        if session.phase is GamePhase.CANCELLED:
            await self.cancel_game(session)
            return
        if session.phase is GamePhase.NIGHT:
            await self.moderation.set_night_permissions(session)
            self._schedule_remaining(
                session,
                "night",
                lambda: self._end_night(session.chat_id, session.phase_number),
            )
            return
        if session.phase is GamePhase.DISCUSSION:
            await self.moderation.set_day_permissions(session)
            self._schedule_remaining(
                session,
                "discussion",
                lambda: self._end_discussion(session.chat_id, session.phase_number),
            )
            return
        if session.phase is GamePhase.VOTING:
            await self.moderation.set_day_permissions(session)
            self._schedule_remaining(
                session,
                "voting",
                lambda: self._end_voting(session.chat_id, session.phase_number),
            )
            return
        if session.phase is GamePhase.VERDICT and session.pending_revenge_by is not None:
            self._schedule_remaining(
                session,
                "revenge",
                lambda: self.resolve_revenge(
                    session.chat_id,
                    session.pending_revenge_by or 0,
                    None,
                ),
            )

    def _schedule_remaining(
        self,
        session: GameSession,
        name: str,
        callback: Callable[[], Awaitable[None]],
    ) -> None:
        remaining = 0.0
        if session.phase_deadline is not None:
            remaining = max(0.0, (session.phase_deadline - datetime.now(UTC)).total_seconds())
        self.timers.schedule(session.chat_id, name, remaining, callback)

    async def _update_game_post(
        self,
        session: GameSession,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        """Move the single public game post to the bottom of the group chat."""
        if session.main_message_id is not None:
            with suppress(TelegramBadRequest):
                await self.bot.delete_message(
                    chat_id=session.chat_id,
                    message_id=session.main_message_id,
                )
        message = await self.bot.send_message(
            session.chat_id,
            text,
            reply_markup=reply_markup,
        )
        session.main_message_id = message.message_id

    @staticmethod
    def _winner_text(winner: Faction | RoleKey | None) -> str:
        if winner is Faction.TOWN:
            return "Мирные жители"
        if winner is Faction.MAFIA:
            return "Мафия"
        if isinstance(winner, RoleKey):
            return get_role_definition(winner).name
        return "не определён"
