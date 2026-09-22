from types import SimpleNamespace

import pytest
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatPermissions

from app.game.models import GamePhase, GamePlayer, GameSession
from app.services.moderation import ModerationService


class BotStub:
    def __init__(self) -> None:
        self.default_changes: list[ChatPermissions] = []
        self.member_changes: list[tuple[int, ChatPermissions]] = []
        self.chat_permissions = ChatPermissions(
            can_send_messages=True,
            can_send_photos=False,
            can_send_polls=True,
        )

    async def get_me(self) -> SimpleNamespace:
        return SimpleNamespace(id=99)

    async def get_chat_member(self, chat_id: int, user_id: int) -> SimpleNamespace:
        del chat_id, user_id
        return SimpleNamespace(
            status=ChatMemberStatus.ADMINISTRATOR,
            can_restrict_members=True,
            can_delete_messages=True,
        )

    async def get_chat(self, chat_id: int) -> SimpleNamespace:
        del chat_id
        return SimpleNamespace(permissions=self.chat_permissions)

    async def set_chat_permissions(
        self,
        chat_id: int,
        permissions: ChatPermissions,
        **kwargs: object,
    ) -> None:
        del chat_id, kwargs
        self.default_changes.append(permissions)

    async def restrict_chat_member(
        self,
        chat_id: int,
        user_id: int,
        permissions: ChatPermissions,
        **kwargs: object,
    ) -> None:
        del chat_id, kwargs
        self.member_changes.append((user_id, permissions))


@pytest.mark.asyncio
async def test_chat_is_locked_and_original_permissions_are_saved() -> None:
    bot = BotStub()
    moderation = ModerationService(bot, permission_check_delay=0)  # type: ignore[arg-type]
    session = GameSession(chat_id=-100, created_by=1)

    await moderation.lock_chat_for_game(session)

    assert session.original_chat_permissions is not None
    assert session.original_chat_permissions["can_send_messages"] is True
    assert session.original_chat_permissions["can_send_photos"] is False
    assert bot.default_changes[-1].can_send_messages is False


@pytest.mark.asyncio
async def test_only_living_unblocked_players_are_opened_during_day() -> None:
    bot = BotStub()
    moderation = ModerationService(bot)  # type: ignore[arg-type]
    session = GameSession(
        chat_id=-100,
        created_by=1,
        phase=GamePhase.DISCUSSION,
        original_chat_permissions=bot.chat_permissions.model_dump(),
    )
    session.players = {
        1: GamePlayer(1, "Живой"),
        2: GamePlayer(2, "Погибший", alive=False),
        3: GamePlayer(3, "Заблокированный"),
    }
    session.day_blocked = {3}

    await moderation.set_day_permissions(session)

    changes = {user_id: permissions for user_id, permissions in bot.member_changes}
    assert changes[1].can_send_messages is True
    assert changes[1].can_send_photos is False
    assert changes[2].can_send_messages is False
    assert changes[3].can_send_messages is False
    assert moderation.can_user_speak(session, 999) is False


@pytest.mark.asyncio
async def test_original_chat_permissions_are_restored_after_game() -> None:
    bot = BotStub()
    moderation = ModerationService(bot)  # type: ignore[arg-type]
    session = GameSession(
        chat_id=-100,
        created_by=1,
        original_chat_permissions=bot.chat_permissions.model_dump(),
    )
    session.players[1] = GamePlayer(1, "Игрок", alive=False)

    await moderation.restore_permissions(session)

    assert bot.default_changes[-1].can_send_messages is True
    assert bot.default_changes[-1].can_send_photos is False
    assert bot.member_changes[-1][1].can_send_messages is True


@pytest.mark.asyncio
async def test_existing_player_restriction_is_preserved_after_game() -> None:
    bot = BotStub()

    async def restricted_member(chat_id: int, user_id: int) -> SimpleNamespace:
        del chat_id, user_id
        return SimpleNamespace(
            status=ChatMemberStatus.RESTRICTED,
            can_send_messages=False,
            can_send_audios=False,
            can_send_documents=False,
            can_send_photos=False,
            can_send_videos=False,
            can_send_video_notes=False,
            can_send_voice_notes=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            can_react_to_messages=False,
            can_invite_users=False,
            can_pin_messages=False,
            can_manage_topics=False,
            can_change_info=False,
            until_date=1_800_000_000,
        )

    bot.get_chat_member = restricted_member  # type: ignore[method-assign]
    moderation = ModerationService(bot)  # type: ignore[arg-type]
    session = GameSession(chat_id=-100, created_by=1)
    session.players[1] = GamePlayer(1, "Ограниченный")

    await moderation.lock_chat_for_game(session)
    await moderation.set_day_permissions(session)
    await moderation.restore_permissions(session)

    assert session.original_player_permissions[1]["can_send_messages"] is False
    assert session.original_player_permissions[1]["until_date"] == 1_800_000_000
    assert bot.member_changes[-1][1].can_send_messages is False


@pytest.mark.asyncio
async def test_lobby_cancel_does_not_change_chat_permissions() -> None:
    bot = BotStub()
    moderation = ModerationService(bot)  # type: ignore[arg-type]
    session = GameSession(chat_id=-100, created_by=1)

    await moderation.restore_permissions(session)

    assert bot.default_changes == []
    assert bot.member_changes == []


@pytest.mark.asyncio
async def test_missing_admin_permissions_prevent_game_start() -> None:
    bot = BotStub()
    bot.get_chat_member = _restricted_bot_member  # type: ignore[method-assign]
    moderation = ModerationService(bot, permission_check_delay=0)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="ограничивать участников"):
        await moderation.ensure_bot_permissions(-100)


@pytest.mark.asyncio
async def test_string_admin_status_from_telegram_is_accepted() -> None:
    bot = BotStub()

    async def string_admin(chat_id: int, user_id: int) -> SimpleNamespace:
        del chat_id, user_id
        return SimpleNamespace(
            status="administrator",
            can_restrict_members=True,
            can_delete_messages=True,
        )

    bot.get_chat_member = string_admin  # type: ignore[method-assign]
    moderation = ModerationService(bot, permission_check_delay=0)  # type: ignore[arg-type]

    await moderation.ensure_bot_permissions(-100)


@pytest.mark.asyncio
async def test_permission_check_retries_telegram_propagation() -> None:
    bot = BotStub()
    statuses = iter([ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR])

    async def changing_status(chat_id: int, user_id: int) -> SimpleNamespace:
        del chat_id, user_id
        return SimpleNamespace(
            status=next(statuses),
            can_restrict_members=True,
            can_delete_messages=True,
        )

    bot.get_chat_member = changing_status  # type: ignore[method-assign]
    moderation = ModerationService(bot, permission_check_delay=0)  # type: ignore[arg-type]

    await moderation.ensure_bot_permissions(-100)


@pytest.mark.asyncio
async def test_unsaved_admin_change_has_clear_message() -> None:
    bot = BotStub()

    async def ordinary_member(chat_id: int, user_id: int) -> SimpleNamespace:
        del chat_id, user_id
        return SimpleNamespace(status=ChatMemberStatus.MEMBER)

    bot.get_chat_member = ordinary_member  # type: ignore[method-assign]
    moderation = ModerationService(
        bot,  # type: ignore[arg-type]
        permission_check_attempts=1,
        permission_check_delay=0,
    )

    with pytest.raises(ValueError, match="Сохранить изменения"):
        await moderation.ensure_bot_permissions(-100)


async def _restricted_bot_member(chat_id: int, user_id: int) -> SimpleNamespace:
    del chat_id, user_id
    return SimpleNamespace(
        status=ChatMemberStatus.ADMINISTRATOR,
        can_restrict_members=False,
        can_delete_messages=True,
    )
