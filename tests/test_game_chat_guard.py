from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatMemberStatus, ChatType, ContentType
from aiogram.types import Chat, Message, User

from app.bot.middlewares.game_chat_guard import GameChatGuardMiddleware
from app.game.models import GamePhase, GamePlayer
from app.services.moderation import ModerationService
from app.services.registry import GameRegistry


def message(text: str) -> Message:
    return Message(
        message_id=42,
        date=datetime.now(UTC),
        chat=Chat(id=-100, type=ChatType.SUPERGROUP),
        from_user=User(id=99, is_bot=False, first_name="Наблюдатель"),
        text=text,
    )


@pytest.mark.asyncio
async def test_outsider_message_is_deleted_without_running_handler() -> None:
    registry = GameRegistry()
    session = registry.create(-100, 1)
    session.phase = GamePhase.DISCUSSION
    moderation = SimpleNamespace(
        can_user_speak=ModerationService.can_user_speak,
        delete_message=AsyncMock(),
    )
    handler = AsyncMock()

    await GameChatGuardMiddleware()(
        handler,
        message("Я не участвую"),
        {"registry": registry, "moderation": moderation},
    )

    handler.assert_not_awaited()
    moderation.delete_message.assert_awaited_once_with(-100, 42)


@pytest.mark.asyncio
async def test_living_player_can_write_during_discussion() -> None:
    registry = GameRegistry()
    session = registry.create(-100, 1)
    session.phase = GamePhase.DISCUSSION
    session.players[99] = GamePlayer(99, "Игрок")
    moderation = SimpleNamespace(
        can_user_speak=ModerationService.can_user_speak,
        delete_message=AsyncMock(),
    )
    handler = AsyncMock(return_value="handled")

    result = await GameChatGuardMiddleware()(
        handler,
        message("Обсуждаю"),
        {"registry": registry, "moderation": moderation},
    )

    assert result == "handled"
    handler.assert_awaited_once()
    moderation.delete_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_dead_player_command_works_but_command_message_is_removed() -> None:
    registry = GameRegistry()
    session = registry.create(-100, 1)
    session.phase = GamePhase.DISCUSSION
    session.players[99] = GamePlayer(99, "Погибший", alive=False)
    moderation = SimpleNamespace(
        can_user_speak=ModerationService.can_user_speak,
        delete_message=AsyncMock(),
    )
    handler = AsyncMock(return_value="status")

    result = await GameChatGuardMiddleware()(
        handler,
        message("/status"),
        {"registry": registry, "moderation": moderation},
    )

    assert result == "status"
    handler.assert_awaited_once()
    moderation.delete_message.assert_awaited_once_with(-100, 42)


@pytest.mark.asyncio
async def test_outsider_command_is_removed_without_running_handler() -> None:
    registry = GameRegistry()
    session = registry.create(-100, 1)
    session.phase = GamePhase.NIGHT
    bot = SimpleNamespace(get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member")))
    moderation = SimpleNamespace(
        can_user_speak=ModerationService.can_user_speak,
        delete_message=AsyncMock(),
    )
    handler = AsyncMock()

    await GameChatGuardMiddleware()(
        handler,
        message("/game"),
        {"registry": registry, "moderation": moderation, "bot": bot},
    )

    handler.assert_not_awaited()
    moderation.delete_message.assert_awaited_once_with(-100, 42)


@pytest.mark.asyncio
async def test_group_admin_can_use_commands_during_game() -> None:
    registry = GameRegistry()
    session = registry.create(-100, 1)
    session.phase = GamePhase.NIGHT
    bot = SimpleNamespace(
        get_chat_member=AsyncMock(
            return_value=SimpleNamespace(status=ChatMemberStatus.ADMINISTRATOR)
        )
    )
    moderation = SimpleNamespace(
        can_user_speak=ModerationService.can_user_speak,
        delete_message=AsyncMock(),
    )
    handler = AsyncMock(return_value="handled")

    result = await GameChatGuardMiddleware()(
        handler,
        message("/stopgame"),
        {"registry": registry, "moderation": moderation, "bot": bot},
    )

    assert result == "handled"
    handler.assert_awaited_once()
    moderation.delete_message.assert_awaited_once_with(-100, 42)


def test_service_message_types_are_explicitly_recognized() -> None:
    from app.bot.middlewares.game_chat_guard import SERVICE_MESSAGES

    assert ContentType.NEW_CHAT_MEMBERS in SERVICE_MESSAGES
