from __future__ import annotations

import asyncio
from collections.abc import Iterable
from contextlib import suppress
from html import escape

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import Message

from app.bot.keyboards.game import day_vote_keyboard, night_target_keyboard, revenge_keyboard
from app.game.models import GamePlayer, GameSession, ResolutionResult, RoleKey
from app.game.roles import get_role_definition

ACTION_TITLES = {
    "mafia_vote": "🔪 Выберите жертву мафии",
    "inspect": "🔎 Выберите игрока для проверки",
    "commissioner_shot": "🔫 Выберите цель для выстрела",
    "heal": "💊 Выберите игрока для лечения",
    "maniac_kill": "🩸 Выберите жертву",
    "block": "❄️ Выберите игрока для блокировки",
    "watch": "👁 Выберите, за кем наблюдать",
}


class MessagingService:
    def __init__(self, bot: Bot, private_messages_per_second: int = 25) -> None:
        self.bot = bot
        self._private_send_lock = asyncio.Lock()
        self._private_send_interval = 1 / private_messages_per_second
        self._last_private_send = 0.0

    async def can_message(self, user_id: int) -> bool:
        try:
            message = await self._send_private(
                user_id,
                "✅ Личные сообщения активированы. Теперь вы можете участвовать в игре.",
            )
        except (TelegramForbiddenError, TelegramBadRequest):
            return False
        with suppress(TelegramBadRequest):
            await message.delete()
        return True

    async def send_roles(
        self,
        players: Iterable[GamePlayer],
        assignments: dict[int, RoleKey],
    ) -> list[int]:
        failed: list[int] = []
        player_list = list(players)
        mafia_names = [
            escape(player.display_name)
            for player in player_list
            if get_role_definition(assignments[player.user_id]).faction.value == "mafia"
        ]
        players_by_id = {player.user_id: player for player in player_list}

        async def send(player: GamePlayer) -> None:
            role = assignments[player.user_id]
            definition = get_role_definition(role)
            details: list[str] = []
            if definition.faction.value == "mafia":
                details.append("🤝 Состав мафии: " + ", ".join(mafia_names))
            ward_id = player.metadata.get("ward_id")
            if role is RoleKey.LAWYER and isinstance(ward_id, int):
                ward = players_by_id[ward_id]
                details.append(f"🛡 Ваш подопечный: {escape(ward.display_name)}")
            suffix = ""
            if details:
                suffix = "\n\n" + "\n".join(details)
            try:
                await self._send_private(
                    player.user_id,
                    f"🎭 <b>Ваша роль: {definition.name}</b>\n\n{definition.description}{suffix}",
                    protect_content=True,
                )
            except (TelegramForbiddenError, TelegramBadRequest):
                failed.append(player.user_id)

        await asyncio.gather(*(send(player) for player in player_list))
        return failed

    async def send_night_prompts(self, session: GameSession) -> None:
        await asyncio.gather(
            *(
                self.send_night_prompts_for_player(session, player.user_id)
                for player in session.alive_players
            )
        )

    async def send_night_prompts_for_player(
        self,
        session: GameSession,
        user_id: int,
    ) -> int:
        player = session.players.get(user_id)
        if player is None or player.role is None or not player.alive:
            return 0
        definition = get_role_definition(player.role)
        sent = 0
        for action_type in definition.night_actions:
            title = ACTION_TITLES.get(action_type.value, "Выберите цель")
            if await self._safe_private(
                player.user_id,
                f"🌙 <b>Ночь №{session.phase_number}</b>\n{title}",
                reply_markup=night_target_keyboard(
                    session,
                    player.user_id,
                    action_type,
                ),
            ):
                sent += 1
        return sent

    async def send_night_results(
        self,
        session: GameSession,
        result: ResolutionResult,
    ) -> None:
        for commissioner_id, role in result.investigations.items():
            definition = get_role_definition(role)
            text = f"🔎 Результат проверки: <b>{definition.name}</b>"
            recipients = {commissioner_id}
            recipients.update(
                player.user_id
                for player in session.alive_players
                if player.metadata.get("starting_role") == RoleKey.WARRANT_OFFICER.value
            )
            await asyncio.gather(*(self._safe_private(user_id, text) for user_id in recipients))

        for watcher_id, visitor_ids in result.witnesses.items():
            visitors = [
                escape(session.require_player(user_id).display_name) for user_id in visitor_ids
            ]
            text = "👁 Ночных посетителей не было."
            if visitors:
                text = "👁 Ночью к цели приходили: " + ", ".join(visitors)
            await self._safe_private(watcher_id, text)

        for user_id, role in result.role_changes.items():
            definition = get_role_definition(role)
            await self._safe_private(
                user_id,
                f"🎖 Вы унаследовали роль: <b>{definition.name}</b>",
            )

    async def send_day_vote_prompts(self, session: GameSession) -> None:
        await asyncio.gather(
            *(
                self._safe_private(
                    player.user_id,
                    f"🗳 <b>Голосование, день №{session.phase_number}</b>\n"
                    "Выберите кандидата на казнь.",
                    reply_markup=day_vote_keyboard(session),
                )
                for player in session.alive_players
                if player.user_id not in session.day_blocked
            )
        )

    async def send_revenge_prompt(self, session: GameSession, best_friend_id: int) -> None:
        await self._safe_private(
            best_friend_id,
            "💔 Вас казнили. Выберите игрока, которого заберёте с собой.",
            reply_markup=revenge_keyboard(session, best_friend_id),
        )

    async def _send_private(self, user_id: int, text: str, **kwargs: object) -> Message:
        async with self._private_send_lock:
            loop = asyncio.get_running_loop()
            delay = self._last_private_send + self._private_send_interval - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)
            while True:
                try:
                    message = await self.bot.send_message(user_id, text, **kwargs)
                    self._last_private_send = loop.time()
                    return message
                except TelegramRetryAfter as error:
                    await asyncio.sleep(error.retry_after)

    async def _safe_private(self, user_id: int, text: str, **kwargs: object) -> bool:
        try:
            await self._send_private(user_id, text, **kwargs)
        except (TelegramForbiddenError, TelegramBadRequest):
            return False
        return True
