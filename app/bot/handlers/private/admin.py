from __future__ import annotations

from contextlib import suppress
from datetime import datetime
from html import escape
from math import ceil

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.bot.keyboards.admin import (
    AdminPanelCallback,
    admin_back_keyboard,
    admin_home_keyboard,
    admin_user_keyboard,
    admin_users_keyboard,
)
from app.config import Settings
from app.database.repositories import AdminStore, AdminUser
from app.game.models import GamePhase
from app.services.registry import GameRegistry

router = Router(name="private.admin")
router.message.filter(F.chat.type == "private")

USERS_PER_PAGE = 8
PHASE_NAMES = {
    GamePhase.LOBBY: "регистрация",
    GamePhase.ASSIGNING: "раздача ролей",
    GamePhase.NIGHT: "ночь",
    GamePhase.DAWN: "утро",
    GamePhase.DISCUSSION: "обсуждение",
    GamePhase.VOTING: "голосование",
    GamePhase.VERDICT: "приговор",
    GamePhase.FINISHED: "завершена",
    GamePhase.CANCELLED: "отменена",
}


@router.message(Command("admin"))
async def open_admin_panel(
    message: Message,
    settings: Settings,
    admin_store: AdminStore,
    registry: GameRegistry,
) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None, settings):
        return
    await message.answer(
        await _home_text(admin_store, registry),
        reply_markup=admin_home_keyboard(),
    )


@router.callback_query(AdminPanelCallback.filter())
async def navigate_admin_panel(
    query: CallbackQuery,
    callback_data: AdminPanelCallback,
    settings: Settings,
    admin_store: AdminStore,
    registry: GameRegistry,
) -> None:
    if not _is_owner(query.from_user.id, settings):
        await query.answer("Нет доступа.", show_alert=True)
        return
    if not isinstance(query.message, Message):
        await query.answer()
        return

    action = callback_data.action
    if action == "home":
        await _edit(
            query,
            await _home_text(admin_store, registry),
            admin_home_keyboard(),
        )
        return
    if action == "stats":
        await _edit(
            query,
            await _statistics_text(admin_store, registry),
            admin_back_keyboard(),
        )
        return
    if action == "users":
        await _show_users(query, callback_data.page, admin_store, registry)
        return
    if action == "user":
        await _show_user(
            query,
            callback_data.user_id,
            callback_data.page,
            admin_store,
            registry,
        )
        return
    if action == "games":
        await _edit(query, await _active_games_text(query, registry), admin_back_keyboard())
        return
    await query.answer("Неизвестный раздел.", show_alert=True)


async def _home_text(admin_store: AdminStore, registry: GameRegistry) -> str:
    summary = await admin_store.summary(registry.all())
    return (
        "🛡 <b>Админ-панель Мафии ВМедА</b>\n\n"
        f"👥 Пользователей: <b>{summary.users}</b>\n"
        f"🎮 Активных игр: <b>{summary.active_games}</b>\n"
        f"🏁 Завершённых партий: <b>{summary.completed_games}</b>\n\n"
        "Панель доступна только владельцу бота."
    )


async def _statistics_text(admin_store: AdminStore, registry: GameRegistry) -> str:
    summary = await admin_store.summary(registry.all())
    return (
        "📊 <b>Общая статистика</b>\n\n"
        f"👥 Пользователей: <b>{summary.users}</b>\n"
        f"🏘 Групп: <b>{summary.groups}</b>\n"
        f"🎮 Активных игр: <b>{summary.active_games}</b>\n"
        f"🏁 Завершённых партий: <b>{summary.completed_games}</b>\n"
        f"🎭 Участий в партиях: <b>{summary.participations}</b>\n"
        f"🏆 Побед игроков: <b>{summary.wins}</b>\n"
        f"🐞 Сообщений об ошибках: <b>{summary.reports}</b>"
    )


async def _show_users(
    query: CallbackQuery,
    requested_page: int,
    admin_store: AdminStore,
    registry: GameRegistry,
) -> None:
    all_users = await admin_store.list_users(registry.all())
    total_pages = max(1, ceil(len(all_users) / USERS_PER_PAGE))
    page = min(max(requested_page, 0), total_pages - 1)
    start = page * USERS_PER_PAGE
    users = all_users[start : start + USERS_PER_PAGE]
    lines = [
        "👥 <b>Пользователи бота</b>",
        f"Всего: <b>{len(all_users)}</b> · Страница <b>{page + 1}/{total_pages}</b>",
        "",
    ]
    for index, user in enumerate(users, start=start + 1):
        username = f" @{escape(user.username)}" if user.username else ""
        active = " · 🟢 в игре" if user.active_games else ""
        lines.append(
            f"{index}. <b>{escape(user.display_name[:45])}</b>{username}\n"
            f"   <code>{user.telegram_id}</code> · игр {user.games_played} · "
            f"побед {user.games_won}{active}"
        )
    if not users:
        lines.append("Пользователей пока нет.")
    await _edit(
        query,
        "\n".join(lines),
        admin_users_keyboard(users, page=page, total_pages=total_pages),
    )


async def _show_user(
    query: CallbackQuery,
    user_id: int,
    page: int,
    admin_store: AdminStore,
    registry: GameRegistry,
) -> None:
    user = next(
        (
            item
            for item in await admin_store.list_users(registry.all())
            if item.telegram_id == user_id
        ),
        None,
    )
    if user is None:
        await query.answer("Пользователь не найден.", show_alert=True)
        return
    await _edit(query, _user_text(user), admin_user_keyboard(page))


def _user_text(user: AdminUser) -> str:
    username = f"@{escape(user.username)}" if user.username else "не указан"
    win_rate = round(user.games_won * 100 / user.games_played) if user.games_played else 0
    active = f"да, партий: {user.active_games}" if user.active_games else "нет"
    return (
        "👤 <b>Карточка пользователя</b>\n\n"
        f"Имя: <b>{escape(user.display_name)}</b>\n"
        f"Username: <b>{username}</b>\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Первое появление: <b>{_date(user.first_seen)}</b>\n"
        f"Последняя активность: <b>{_date(user.last_seen)}</b>\n"
        f"Сейчас в игре: <b>{active}</b>\n\n"
        f"Партий: <b>{user.games_played}</b>\n"
        f"Побед: <b>{user.games_won}</b>\n"
        f"Процент побед: <b>{win_rate}%</b>"
    )


async def _active_games_text(query: CallbackQuery, registry: GameRegistry) -> str:
    games = registry.all()
    if not games:
        return "🎮 <b>Активные игры</b>\n\nСейчас активных игр нет."
    lines = [f"🎮 <b>Активные игры ({len(games)})</b>", ""]
    for game in games[:20]:
        title = f"Группа {game.chat_id}"
        with suppress(TelegramBadRequest):
            chat = await query.bot.get_chat(game.chat_id)
            title = chat.title or title
        lines.append(
            f"• <b>{escape(title[:50])}</b>\n"
            f"  {PHASE_NAMES[game.phase]} · игроков {len(game.players)} · "
            f"живы {len(game.alive_players)}"
        )
    if len(games) > 20:
        lines.append(f"\nИ ещё: {len(games) - 20}")
    return "\n".join(lines)


async def _edit(
    query: CallbackQuery,
    text: str,
    keyboard: InlineKeyboardMarkup,
) -> None:
    if not isinstance(query.message, Message):
        await query.answer()
        return
    with suppress(TelegramBadRequest):
        await query.message.edit_text(text, reply_markup=keyboard)
    await query.answer()


def _is_owner(user_id: int | None, settings: Settings) -> bool:
    return user_id == settings.bot_admin_id


def _date(value: datetime | None) -> str:
    return value.strftime("%d.%m.%Y %H:%M") if value is not None else "нет данных"
