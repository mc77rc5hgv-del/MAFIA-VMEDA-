from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.bot.keyboards.menu import (
    PrivateMenuCallback,
    private_back_keyboard,
    private_game_keyboard,
    private_games_keyboard,
    private_home_keyboard,
)
from app.config import Settings
from app.database.repositories import AdminStore
from app.game.models import GamePhase, GameSession
from app.game.roles import get_role_definition
from app.services.messaging import MessagingService
from app.services.registry import GameRegistry
from app.texts.roles import roles_text
from app.texts.rules import RULES_TEXT

router = Router(name="private.start")
router.message.filter(F.chat.type == "private")

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

HOME_TEXT = (
    "🎓 <b>Мафия ВМедА</b>\n\n"
    "Личные сообщения активированы. Здесь можно посмотреть свою игру, роль, "
    "ночные действия и правила.\n\n"
    "Чтобы начать новую партию, добавьте бота в группу и отправьте /game."
)


@router.message(CommandStart())
@router.message(Command("menu"))
async def start_private(
    message: Message,
    registry: GameRegistry,
    admin_store: AdminStore,
    settings: Settings,
) -> None:
    if message.from_user is not None:
        await admin_store.register_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
        )
    payload = (message.text or "").split(maxsplit=1)
    if len(payload) == 2 and payload[1].startswith("game_") and message.from_user is not None:
        session = registry.get_by_token(payload[1].removeprefix("game_"))
        if session is not None and message.from_user.id in session.players:
            text, keyboard = await _game_view(message.bot, message.from_user.id, session)
            await message.answer(text, reply_markup=keyboard)
            return
    bot_user = await message.bot.get_me()
    await message.answer(
        HOME_TEXT,
        reply_markup=private_home_keyboard(
            bot_user.username,
            show_admin=(
                message.from_user is not None and message.from_user.id == settings.bot_admin_id
            ),
        ),
    )


@router.message(Command("roles"))
async def show_roles(message: Message) -> None:
    await message.answer(roles_text(), reply_markup=private_back_keyboard())


@router.message(Command("rules"))
async def show_rules(message: Message) -> None:
    await message.answer(RULES_TEXT, reply_markup=private_back_keyboard())


@router.callback_query(PrivateMenuCallback.filter())
async def navigate_private_menu(
    query: CallbackQuery,
    callback_data: PrivateMenuCallback,
    registry: GameRegistry,
    messaging: MessagingService,
    settings: Settings,
) -> None:
    if not isinstance(query.message, Message):
        await query.answer()
        return

    if callback_data.action == "home":
        bot_user = await query.bot.get_me()
        await _edit_menu(
            query,
            HOME_TEXT,
            private_home_keyboard(
                bot_user.username,
                show_admin=query.from_user.id == settings.bot_admin_id,
            ),
        )
        return
    if callback_data.action == "roles":
        await _edit_menu(query, roles_text(), private_back_keyboard())
        return
    if callback_data.action == "rules":
        await _edit_menu(query, RULES_TEXT, private_back_keyboard())
        return
    if callback_data.action == "games":
        await _show_games(query, registry)
        return
    if callback_data.action in {"game", "actions"}:
        session = registry.get_by_token(callback_data.game)
        if session is None or query.from_user.id not in session.players:
            await query.answer("Эта игра уже завершена.", show_alert=True)
            return
        if callback_data.action == "actions":
            if session.phase is not GamePhase.NIGHT:
                await query.answer("Ночные действия сейчас недоступны.", show_alert=True)
                return
            sent = await messaging.send_night_prompts_for_player(session, query.from_user.id)
            if sent == 0:
                await query.answer("У вашей роли нет ночного действия.", show_alert=True)
            else:
                await query.answer("Кнопки действий отправлены ниже.")
            return
        await _show_game(query, session)
        return

    await query.answer("Неизвестный раздел.", show_alert=True)


async def _show_games(query: CallbackQuery, registry: GameRegistry) -> None:
    games = registry.for_player(query.from_user.id)
    if not games:
        await _edit_menu(
            query,
            "🎮 <b>Моя игра</b>\n\nСейчас вы не участвуете в активной партии.",
            private_back_keyboard(),
        )
        return
    if len(games) == 1:
        await _show_game(query, games[0])
        return

    titled_games: list[tuple[GameSession, str]] = []
    for session in games:
        title = f"Группа {session.chat_id}"
        with suppress(TelegramBadRequest):
            chat = await query.bot.get_chat(session.chat_id)
            title = chat.title or title
        titled_games.append((session, title))
    await _edit_menu(
        query,
        "🎮 <b>Ваши активные игры</b>\n\nВыберите группу:",
        private_games_keyboard(titled_games),
    )


async def _show_game(query: CallbackQuery, session: GameSession) -> None:
    text, keyboard = await _game_view(query.bot, query.from_user.id, session)
    await _edit_menu(query, text, keyboard)


async def _game_view(
    bot: Bot,
    user_id: int,
    session: GameSession,
) -> tuple[str, InlineKeyboardMarkup]:
    player = session.players[user_id]
    title = f"Группа {session.chat_id}"
    with suppress(TelegramBadRequest):
        chat = await bot.get_chat(session.chat_id)
        title = chat.title or title

    role = "ещё не назначена"
    has_actions = False
    if player.role is not None:
        definition = get_role_definition(player.role)
        role = definition.name
        has_actions = bool(definition.night_actions)

    state = "🟢 Вы в игре" if player.alive else "💀 Вы выбыли"
    if player.user_id in session.day_blocked:
        state = "❄️ Вы заблокированы до следующей ночи"
    remaining = ""
    if session.phase_deadline is not None:
        seconds = max(0, int((session.phase_deadline - datetime.now(UTC)).total_seconds()))
        remaining = f"\n⏱ Осталось: <b>{seconds} сек.</b>"

    return (
        "🎮 <b>Текущая игра</b>\n\n"
        f"🏷 {escape(title)}\n"
        f"🎭 Роль: <b>{escape(role)}</b>\n"
        f"🌗 Фаза: <b>{PHASE_NAMES[session.phase]}</b>\n"
        f"{state}{remaining}\n\n"
        f"Живых игроков: <b>{len(session.alive_players)}/{len(session.players)}</b>",
        private_game_keyboard(
            session,
            show_actions=(player.alive and session.phase is GamePhase.NIGHT and has_actions),
        ),
    )


async def _edit_menu(
    query: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    if not isinstance(query.message, Message):
        await query.answer()
        return
    with suppress(TelegramBadRequest):
        await query.message.edit_text(text, reply_markup=reply_markup)
    await query.answer()
