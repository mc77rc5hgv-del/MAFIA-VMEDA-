from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.admin import AdminPanelCallback
from app.game.models import GameSession


class PrivateMenuCallback(CallbackData, prefix="pm"):
    action: str
    game: str = "-"


def private_home_keyboard(
    bot_username: str | None,
    *,
    show_admin: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🎮 Моя игра",
        callback_data=PrivateMenuCallback(action="games"),
    )
    builder.button(
        text="🎭 Роли",
        callback_data=PrivateMenuCallback(action="roles"),
    )
    builder.button(
        text="📖 Правила",
        callback_data=PrivateMenuCallback(action="rules"),
    )
    builder.button(
        text="✏️ Моё имя",
        callback_data=PrivateMenuCallback(action="name"),
    )
    if bot_username:
        builder.button(
            text="➕ Добавить в группу",
            url=f"https://t.me/{bot_username}?startgroup=true",
        )
    if show_admin:
        builder.button(
            text="🛡 Админ-панель",
            callback_data=AdminPanelCallback(action="home"),
        )
    builder.adjust(1, 2, 1, 1, 1)
    return builder.as_markup()


def private_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Главное меню",
                    callback_data=PrivateMenuCallback(action="home").pack(),
                )
            ]
        ]
    )


def private_games_keyboard(
    games: list[tuple[GameSession, str]],
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for session, title in games:
        builder.button(
            text=f"🎲 {title}"[:40],
            callback_data=PrivateMenuCallback(
                action="game",
                game=session.callback_token,
            ),
        )
    builder.button(
        text="⬅️ Главное меню",
        callback_data=PrivateMenuCallback(action="home"),
    )
    builder.adjust(1)
    return builder.as_markup()


def private_game_keyboard(
    session: GameSession,
    *,
    show_actions: bool,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if show_actions:
        builder.button(
            text="🎯 Ночные действия",
            callback_data=PrivateMenuCallback(
                action="actions",
                game=session.callback_token,
            ),
        )
    builder.button(
        text="🔄 Обновить",
        callback_data=PrivateMenuCallback(
            action="game",
            game=session.callback_token,
        ),
    )
    builder.button(
        text="⬅️ К списку игр",
        callback_data=PrivateMenuCallback(action="games"),
    )
    builder.adjust(1, 2)
    return builder.as_markup()
