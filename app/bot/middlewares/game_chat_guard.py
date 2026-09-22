from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatMemberStatus, ContentType
from aiogram.types import Message

from app.game.models import GamePhase, GameSession
from app.services.moderation import ModerationService
from app.services.registry import GameRegistry

SERVICE_MESSAGES = {
    ContentType.NEW_CHAT_MEMBERS,
    ContentType.LEFT_CHAT_MEMBER,
    ContentType.NEW_CHAT_TITLE,
    ContentType.NEW_CHAT_PHOTO,
    ContentType.DELETE_CHAT_PHOTO,
    ContentType.GROUP_CHAT_CREATED,
    ContentType.SUPERGROUP_CHAT_CREATED,
    ContentType.CHANNEL_CHAT_CREATED,
    ContentType.MIGRATE_TO_CHAT_ID,
    ContentType.MIGRATE_FROM_CHAT_ID,
    ContentType.PINNED_MESSAGE,
}


class GameChatGuardMiddleware(BaseMiddleware):
    """Keep the game chat writable only for eligible living players."""

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        registry: GameRegistry | None = data.get("registry")
        moderation: ModerationService | None = data.get("moderation")
        if registry is None or moderation is None:
            return await handler(event, data)

        session = registry.get(event.chat.id)
        if (
            session is None
            or session.phase is GamePhase.LOBBY
            or event.content_type in SERVICE_MESSAGES
        ):
            return await handler(event, data)
        text = event.text or event.caption or ""
        is_command = text.startswith("/")
        user_id = event.from_user.id if event.from_user is not None else None
        if user_id is not None and moderation.can_user_speak(session, user_id):
            result = await handler(event, data)
            if is_command:
                await moderation.delete_message(event.chat.id, event.message_id)
            return result

        if (
            is_command
            and user_id is not None
            and await self._can_use_commands(event, session, data.get("bot"))
        ):
            result = await handler(event, data)
            await moderation.delete_message(event.chat.id, event.message_id)
            return result

        await moderation.delete_message(event.chat.id, event.message_id)
        return None

    @staticmethod
    async def _can_use_commands(event: Message, session: GameSession, bot: Any) -> bool:
        if event.from_user is None:
            return False
        user_id = event.from_user.id
        if user_id in session.players or user_id == session.created_by:
            return True
        if bot is None:
            return False
        member = await bot.get_chat_member(event.chat.id, user_id)
        return member.status in {
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }
