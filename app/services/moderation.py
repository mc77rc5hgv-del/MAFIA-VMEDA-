import asyncio
from collections.abc import Iterable
from contextlib import suppress

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import ChatPermissions

from app.game.models import GameSession


class ModerationService:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def mute_player(self, chat_id: int, user_id: int) -> None:
        await self.bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=ChatPermissions(can_send_messages=False),
            use_independent_chat_permissions=True,
        )

    async def unmute_player(self, chat_id: int, user_id: int) -> None:
        await self.bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_invite_users=True,
            ),
            use_independent_chat_permissions=True,
        )

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        await self.bot.delete_message(chat_id, message_id)

    async def set_night_permissions(self, session: GameSession) -> None:
        await self._apply_many(
            self.mute_player(session.chat_id, player.user_id)
            for player in session.players.values()
        )

    async def set_day_permissions(self, session: GameSession) -> None:
        operations = []
        for player in session.players.values():
            if player.alive and player.user_id not in session.day_blocked:
                operations.append(self.unmute_player(session.chat_id, player.user_id))
            else:
                operations.append(self.mute_player(session.chat_id, player.user_id))
        await self._apply_many(operations)

    async def restore_permissions(self, session: GameSession) -> None:
        await self._apply_many(
            self.unmute_player(session.chat_id, player.user_id)
            for player in session.players.values()
        )

    @staticmethod
    async def _apply_many(operations: Iterable[object]) -> None:
        async def safely(operation: object) -> None:
            with suppress(TelegramBadRequest, TelegramForbiddenError):
                await operation  # type: ignore[misc]

        await asyncio.gather(*(safely(operation) for operation in operations))
