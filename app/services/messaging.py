from __future__ import annotations

import asyncio
from collections.abc import Iterable
from contextlib import suppress

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)

from app.bot.keyboards.game import night_target_keyboard, revenge_keyboard
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
    def __init__(self, bot: Bot, max_parallel: int = 20) -> None:
        self.bot = bot
        self._semaphore = asyncio.Semaphore(max_parallel)

    async def can_message(self, user_id: int) -> bool:
        try:
            message = await self.bot.send_message(
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
            player.display_name
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
                details.append(f"🛡 Ваш подопечный: {ward.display_name}")
            suffix = ""
            if details:
                suffix = "\n\n" + "\n".join(details)
            async with self._semaphore:
                try:
                    await self.bot.send_message(
                        player.user_id,
                        f"🎭 <b>Ваша роль: {definition.name}</b>\n\n"
                        f"{definition.description}{suffix}",
                        protect_content=True,
                    )
                except TelegramRetryAfter as error:
                    await asyncio.sleep(error.retry_after)
                    await self.bot.send_message(
                        player.user_id,
                        f"🎭 <b>Ваша роль: {definition.name}</b>\n\n"
                        f"{definition.description}{suffix}",
                        protect_content=True,
                    )
                except (TelegramForbiddenError, TelegramBadRequest):
                    failed.append(player.user_id)

        await asyncio.gather(*(send(player) for player in player_list))
        return failed

    async def send_night_prompts(self, session: GameSession) -> None:
        async def send(player: GamePlayer) -> None:
            if player.role is None or not player.alive:
                return
            definition = get_role_definition(player.role)
            for action_type in definition.night_actions:
                title = ACTION_TITLES.get(action_type.value, "Выберите цель")
                async with self._semaphore:
                    await self.bot.send_message(
                        player.user_id,
                        f"🌙 <b>Ночь №{session.phase_number}</b>\n{title}",
                        reply_markup=night_target_keyboard(
                            session,
                            player.user_id,
                            action_type,
                        ),
                    )

        await asyncio.gather(*(send(player) for player in session.alive_players))

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
            await asyncio.gather(
                *(self.bot.send_message(user_id, text) for user_id in recipients)
            )

        for watcher_id, visitor_ids in result.witnesses.items():
            visitors = [session.require_player(user_id).display_name for user_id in visitor_ids]
            text = "👁 Ночных посетителей не было."
            if visitors:
                text = "👁 Ночью к цели приходили: " + ", ".join(visitors)
            await self.bot.send_message(watcher_id, text)

        for user_id, role in result.role_changes.items():
            definition = get_role_definition(role)
            await self.bot.send_message(
                user_id,
                f"🎖 Вы унаследовали роль: <b>{definition.name}</b>",
            )

    async def send_revenge_prompt(self, session: GameSession, best_friend_id: int) -> None:
        await self.bot.send_message(
            best_friend_id,
            "💔 Вас казнили. Выберите игрока, которого заберёте с собой.",
            reply_markup=revenge_keyboard(session, best_friend_id),
        )
