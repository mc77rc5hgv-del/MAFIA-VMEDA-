from app.bot.keyboards.game import (
    TARGETS_PER_PAGE,
    DiscussionCallback,
    GamePanelCallback,
    day_vote_keyboard,
    discussion_keyboard,
    game_panel_keyboard,
    lobby_keyboard,
    night_target_keyboard,
)
from app.bot.keyboards.menu import PrivateMenuCallback, private_game_keyboard, private_home_keyboard
from app.game.models import ActionType, GamePlayer, GameSession, RoleKey


def player(user_id: int, role: RoleKey) -> GamePlayer:
    return GamePlayer(user_id, f"Игрок {user_id}", role=role)


def callback_targets(markup: object) -> set[int]:
    keyboard = markup.inline_keyboard  # type: ignore[attr-defined]
    return {
        int(button.callback_data.rsplit(":", maxsplit=1)[1])
        for row in keyboard
        for button in row
        if button.callback_data is not None and button.callback_data.startswith(("d:", "n:"))
    }


def test_mafia_keyboard_hides_teammates() -> None:
    session = GameSession(chat_id=-100, created_by=1, phase_number=1)
    session.players = {
        1: player(1, RoleKey.MAFIA_BOSS),
        2: player(2, RoleKey.MAFIA),
        3: player(3, RoleKey.LAWYER),
        4: player(4, RoleKey.CIVILIAN),
    }

    markup = night_target_keyboard(session, 1, ActionType.MAFIA_VOTE)

    assert callback_targets(markup) == {4}


def test_day_keyboard_paginates_fifty_players_and_keeps_callbacks_compact() -> None:
    session = GameSession(chat_id=-1001234567890, created_by=1, phase_number=12)
    session.players = {user_id: player(user_id, RoleKey.CIVILIAN) for user_id in range(1, 51)}

    markup = day_vote_keyboard(session)

    buttons = [button for row in markup.inline_keyboard for button in row]
    assert len(buttons) == TARGETS_PER_PAGE + 2
    assert 0 in callback_targets(markup)
    assert all(
        len(button.callback_data.encode()) <= 64
        for button in buttons
        if button.callback_data is not None
    )


def test_discussion_keyboard_identifies_game_and_phase() -> None:
    session = GameSession(chat_id=-100, created_by=1, phase_number=7)

    buttons = [button for row in discussion_keyboard(session).inline_keyboard for button in row]
    button = next(button for button in buttons if button.text == "🗳 Завершить обсуждение")
    callback = DiscussionCallback.unpack(button.callback_data or "")

    assert button.text == "🗳 Завершить обсуждение"
    assert callback.game == session.callback_token
    assert callback.phase == 7


def test_group_game_panel_has_navigation_and_compact_callbacks() -> None:
    session = GameSession(chat_id=-100, created_by=1, phase_number=12)

    markup = game_panel_keyboard(session, "vmeda_mafia_bot", include_finish_discussion=True)
    buttons = [button for row in markup.inline_keyboard for button in row]
    labels = {button.text for button in buttons}

    assert {"📊 Статус", "👥 Игроки", "🎮 Личное меню", "🗳 Завершить обсуждение"} <= labels
    private_menu = next(button for button in buttons if button.text == "🎮 Личное меню")
    assert private_menu.url and f"game_{session.callback_token}" in private_menu.url
    status_button = next(button for button in buttons if button.text == "📊 Статус")
    callback = GamePanelCallback.unpack(status_button.callback_data or "")
    assert callback.game == session.callback_token
    assert callback.phase == 12
    assert callback.action == "status"
    assert all(
        len(button.callback_data.encode()) <= 64
        for button in buttons
        if button.callback_data is not None
    )


def test_private_menu_links_group_and_active_game_controls() -> None:
    session = GameSession(chat_id=-100, created_by=1)
    home_buttons = [
        button for row in private_home_keyboard("vmeda_mafia_bot").inline_keyboard for button in row
    ]
    game_buttons = [
        button
        for row in private_game_keyboard(session, show_actions=True).inline_keyboard
        for button in row
    ]

    assert any(button.url and "startgroup=true" in button.url for button in home_buttons)
    game_labels = {button.text for button in game_buttons}
    assert {"🎯 Ночные действия", "🔄 Обновить", "⬅️ К списку игр"} <= game_labels
    refresh = next(button for button in game_buttons if button.text == "🔄 Обновить")
    callback = PrivateMenuCallback.unpack(refresh.callback_data or "")
    assert callback.action == "game"
    assert callback.game == session.callback_token


def test_lobby_and_private_menu_offer_player_name_controls() -> None:
    session = GameSession(chat_id=-100, created_by=1)
    lobby_buttons = [
        button
        for row in lobby_keyboard(session, "vmeda_mafia_bot").inline_keyboard
        for button in row
    ]
    private_buttons = [
        button for row in private_home_keyboard("vmeda_mafia_bot").inline_keyboard for button in row
    ]

    name_link = next(button for button in lobby_buttons if button.text == "✏️ Имя в игре")
    assert name_link.url and f"name_{session.callback_token}" in name_link.url
    assert any(button.text == "✏️ Моё имя" for button in private_buttons)
