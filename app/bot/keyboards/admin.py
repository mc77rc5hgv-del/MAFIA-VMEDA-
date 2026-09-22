from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.repositories import AdminUser


class AdminPanelCallback(CallbackData, prefix="adm"):
    action: str
    page: int = 0
    user_id: int = 0


def admin_home_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📊 Статистика",
        callback_data=AdminPanelCallback(action="stats"),
    )
    builder.button(
        text="👥 Пользователи",
        callback_data=AdminPanelCallback(action="users"),
    )
    builder.button(
        text="🎮 Активные игры",
        callback_data=AdminPanelCallback(action="games"),
    )
    builder.button(
        text="🔄 Обновить",
        callback_data=AdminPanelCallback(action="home"),
    )
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def admin_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Админ-панель",
                    callback_data=AdminPanelCallback(action="home").pack(),
                )
            ]
        ]
    )


def admin_users_keyboard(
    users: list[AdminUser],
    *,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for user in users:
        builder.button(
            text=f"👤 {user.display_name}"[:42],
            callback_data=AdminPanelCallback(
                action="user",
                page=page,
                user_id=user.telegram_id,
            ),
        )
    builder.adjust(1)
    navigation: list[InlineKeyboardButton] = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=AdminPanelCallback(action="users", page=page - 1).pack(),
            )
        )
    if page + 1 < total_pages:
        navigation.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=AdminPanelCallback(action="users", page=page + 1).pack(),
            )
        )
    if navigation:
        builder.row(*navigation)
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Админ-панель",
            callback_data=AdminPanelCallback(action="home").pack(),
        )
    )
    return builder.as_markup()


def admin_user_keyboard(page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ К пользователям",
                    callback_data=AdminPanelCallback(action="users", page=page).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Админ-панель",
                    callback_data=AdminPanelCallback(action="home").pack(),
                )
            ],
        ]
    )
