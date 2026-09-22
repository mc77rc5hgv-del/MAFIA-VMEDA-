from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatMemberStatus

from app.bot.handlers.callbacks.game import _can_manage_game, _refresh_lobby
from app.config import Settings
from app.game.models import GamePlayer, GameSession
from app.services.game_flow import GameFlowService


class BotStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int | str]] = []

    async def get_me(self) -> SimpleNamespace:
        return SimpleNamespace(username="mafia_bot")

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        self.calls.append(("delete", chat_id, message_id))

    async def send_message(self, chat_id: int, text: str, **kwargs: object) -> SimpleNamespace:
        assert kwargs.get("reply_markup") is not None or "Ночь" in text
        self.calls.append(("send", chat_id, text))
        return SimpleNamespace(message_id=222)


@pytest.mark.asyncio
async def test_game_phase_post_is_deleted_and_sent_at_bottom() -> None:
    bot = BotStub()
    flow = GameFlowService.__new__(GameFlowService)
    flow.bot = bot
    session = GameSession(chat_id=-100123, created_by=1, main_message_id=111)

    await flow._update_game_post(session, "🌙 Ночь №1")

    assert bot.calls == [
        ("delete", -100123, 111),
        ("send", -100123, "🌙 Ночь №1"),
    ]
    assert session.main_message_id == 222
    assert session.main_message_text == "🌙 Ночь №1"


@pytest.mark.asyncio
async def test_lobby_menu_is_deleted_and_resent_after_update() -> None:
    bot = BotStub()
    session = GameSession(chat_id=-100456, created_by=1, main_message_id=333)
    session.players[1] = GamePlayer(user_id=1, display_name="Игрок", ready=True)

    await _refresh_lobby(bot, session, Settings(bot_token="test"))

    assert bot.calls[0] == ("delete", -100456, 333)
    assert bot.calls[1][0:2] == ("send", -100456)
    assert "Игроков: <b>1/50</b>" in str(bot.calls[1][2])
    assert session.main_message_id == 222


@pytest.mark.asyncio
async def test_creator_and_group_admin_can_manage_game() -> None:
    session = GameSession(chat_id=-100789, created_by=10)
    creator_query = SimpleNamespace(from_user=SimpleNamespace(id=10))
    assert await _can_manage_game(creator_query, session)

    bot = SimpleNamespace(
        get_chat_member=AsyncMock(
            return_value=SimpleNamespace(status=ChatMemberStatus.ADMINISTRATOR)
        )
    )
    admin_query = SimpleNamespace(from_user=SimpleNamespace(id=20), bot=bot)
    assert await _can_manage_game(admin_query, session)


@pytest.mark.asyncio
async def test_early_discussion_finish_cancels_timer_before_transition() -> None:
    calls: list[tuple[str, int, str | int]] = []

    class TimerStub:
        def cancel(self, chat_id: int, name: str) -> None:
            calls.append(("cancel", chat_id, name))

    flow = GameFlowService.__new__(GameFlowService)
    flow.timers = TimerStub()

    async def end_discussion(chat_id: int, phase_number: int) -> None:
        calls.append(("finish", chat_id, phase_number))

    flow._end_discussion = end_discussion

    await flow.end_discussion_early(-100789, 4)

    assert calls == [
        ("cancel", -100789, "discussion"),
        ("finish", -100789, 4),
    ]
