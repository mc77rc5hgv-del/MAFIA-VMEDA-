from datetime import UTC, datetime

from app.bot.handlers.private.admin import _is_owner, _user_text
from app.bot.keyboards.admin import AdminPanelCallback, admin_home_keyboard, admin_users_keyboard
from app.bot.keyboards.menu import private_home_keyboard
from app.config import Settings
from app.database.repositories import AdminUser


def test_admin_access_is_limited_to_configured_owner() -> None:
    settings = Settings(bot_token="test", bot_admin_id=1326779223)

    assert _is_owner(1326779223, settings)
    assert not _is_owner(1, settings)
    assert not _is_owner(None, settings)


def test_admin_navigation_callbacks_are_compact_and_identify_user() -> None:
    user = AdminUser(
        telegram_id=1326779223,
        display_name="Администратор",
        username="admin",
        games_played=12,
        games_won=7,
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
        active_games=1,
    )
    markups = [
        admin_home_keyboard(),
        admin_users_keyboard([user], page=2, total_pages=4),
    ]
    buttons = [button for markup in markups for row in markup.inline_keyboard for button in row]

    assert all(
        len(button.callback_data.encode()) <= 64
        for button in buttons
        if button.callback_data is not None
    )
    user_button = next(button for button in buttons if button.text == "👤 Администратор")
    callback = AdminPanelCallback.unpack(user_button.callback_data or "")
    assert callback.action == "user"
    assert callback.page == 2
    assert callback.user_id == 1326779223


def test_admin_button_is_only_added_to_owner_menu() -> None:
    regular_labels = {
        button.text for row in private_home_keyboard("bot").inline_keyboard for button in row
    }
    owner_labels = {
        button.text
        for row in private_home_keyboard("bot", show_admin=True).inline_keyboard
        for button in row
    }

    assert "🛡 Админ-панель" not in regular_labels
    assert "🛡 Админ-панель" in owner_labels


def test_admin_user_card_contains_private_statistics() -> None:
    user = AdminUser(
        telegram_id=10,
        display_name="Игрок <тест>",
        username="player",
        games_played=4,
        games_won=1,
        first_seen=None,
        last_seen=None,
        active_games=0,
    )

    text = _user_text(user)

    assert "Игрок &lt;тест&gt;" in text
    assert "<code>10</code>" in text
    assert "25%" in text
