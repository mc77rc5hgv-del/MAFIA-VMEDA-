from contextlib import suppress
from datetime import UTC, datetime

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.game import (
    CODE_ACTIONS,
    DayPageCallback,
    DayVoteCallback,
    DiscussionCallback,
    GameLobbyCallback,
    GamePanelCallback,
    NightActionCallback,
    NightPageCallback,
    RevengeCallback,
    RevengePageCallback,
    day_vote_keyboard,
    lobby_keyboard,
    night_target_keyboard,
    revenge_keyboard,
)
from app.config import Settings
from app.game.engine import GameEngine
from app.game.models import GamePhase, GamePlayer, GameSession, NightAction
from app.services.game_flow import GameFlowService
from app.services.messaging import MessagingService
from app.services.registry import GameRegistry
from app.texts.events import LOBBY_CREATED

router = Router(name="callbacks.game")

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


async def _refresh_lobby(
    bot: Bot,
    game: GameSession,
    settings: Settings,
) -> None:
    bot_user = await bot.get_me()
    ready = sum(player.ready for player in game.players.values())
    text = LOBBY_CREATED.format(
        count=len(game.players),
        ready=ready,
        minimum=settings.min_players,
        maximum=settings.max_players,
    )
    if game.main_message_id is not None:
        with suppress(TelegramBadRequest):
            await bot.delete_message(game.chat_id, game.main_message_id)
    message = await bot.send_message(
        game.chat_id,
        text,
        reply_markup=lobby_keyboard(game, bot_user.username),
    )
    game.main_message_id = message.message_id
    game.main_message_text = text


async def _can_manage_game(query: CallbackQuery, session: GameSession) -> bool:
    if query.from_user.id == session.created_by:
        return True
    member = await query.bot.get_chat_member(session.chat_id, query.from_user.id)
    return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}


@router.callback_query(GameLobbyCallback.filter(F.action == "join"))
async def join_lobby(
    query: CallbackQuery,
    callback_data: GameLobbyCallback,
    registry: GameRegistry,
    engine: GameEngine,
    messaging: MessagingService,
    settings: Settings,
) -> None:
    if not isinstance(query.message, Message):
        await query.answer()
        return
    if not await messaging.can_message(query.from_user.id):
        await query.answer(
            "Сначала откройте личный чат с ботом и нажмите Start.",
            show_alert=True,
        )
        return
    chat_id = query.message.chat.id
    lock = await registry.lock_for(chat_id)
    async with lock:
        session = registry.get_by_token(callback_data.game)
        if (
            session is None
            or session.chat_id != chat_id
            or callback_data.phase != session.phase_number
        ):
            await query.answer("Регистрация уже закрыта.", show_alert=True)
            return
        try:
            engine.add_player(
                session,
                GamePlayer(
                    user_id=query.from_user.id,
                    display_name=query.from_user.full_name,
                    username=query.from_user.username,
                ),
            )
        except ValueError as error:
            await query.answer(str(error), show_alert=True)
            return
        await _refresh_lobby(query.bot, session, settings)
        await registry.persist(session)
        await query.answer("Вы зарегистрированы!")


@router.callback_query(GameLobbyCallback.filter(F.action == "leave"))
async def leave_lobby(
    query: CallbackQuery,
    callback_data: GameLobbyCallback,
    registry: GameRegistry,
    engine: GameEngine,
    settings: Settings,
) -> None:
    if not isinstance(query.message, Message):
        await query.answer()
        return
    chat_id = query.message.chat.id
    lock = await registry.lock_for(chat_id)
    async with lock:
        session = registry.get_by_token(callback_data.game)
        if (
            session is None
            or session.chat_id != chat_id
            or callback_data.phase != session.phase_number
        ):
            await query.answer("Регистрация уже закрыта.", show_alert=True)
            return
        try:
            engine.remove_player(session, query.from_user.id)
        except ValueError as error:
            await query.answer(str(error), show_alert=True)
            return
        await _refresh_lobby(query.bot, session, settings)
        await registry.persist(session)
        await query.answer("Вы вышли из регистрации.")


@router.callback_query(GameLobbyCallback.filter(F.action == "players"))
async def lobby_players(
    query: CallbackQuery,
    callback_data: GameLobbyCallback,
    registry: GameRegistry,
) -> None:
    if not isinstance(query.message, Message):
        await query.answer()
        return
    session = registry.get_by_token(callback_data.game)
    if session is None or callback_data.phase != session.phase_number or not session.players:
        await query.answer("В лобби пока никого нет.", show_alert=True)
        return
    names = "\n".join(player.display_name for player in session.players.values())
    await query.answer(names[:190], show_alert=True)


@router.callback_query(GameLobbyCallback.filter(F.action == "ready"))
async def toggle_ready(
    query: CallbackQuery,
    callback_data: GameLobbyCallback,
    registry: GameRegistry,
    settings: Settings,
) -> None:
    if not isinstance(query.message, Message):
        await query.answer()
        return
    session = registry.get_by_token(callback_data.game)
    if (
        session is None
        or session.chat_id != query.message.chat.id
        or callback_data.phase != session.phase_number
    ):
        await query.answer("Регистрация уже закрыта.", show_alert=True)
        return
    lock = await registry.lock_for(session.chat_id)
    async with lock:
        player = session.players.get(query.from_user.id)
        if player is None:
            await query.answer("Сначала присоединитесь к игре.", show_alert=True)
            return
        player.ready = not player.ready
        await _refresh_lobby(query.bot, session, settings)
        await registry.persist(session)
    await query.answer("Готовность подтверждена." if player.ready else "Готовность снята.")


@router.callback_query(GameLobbyCallback.filter(F.action == "cancel"))
async def cancel_lobby(
    query: CallbackQuery,
    callback_data: GameLobbyCallback,
    registry: GameRegistry,
    flow: GameFlowService,
) -> None:
    if not isinstance(query.message, Message):
        await query.answer()
        return
    session = registry.get_by_token(callback_data.game)
    if (
        session is None
        or session.chat_id != query.message.chat.id
        or callback_data.phase != session.phase_number
    ):
        await query.answer("Эта игра уже завершена.", show_alert=True)
        return
    if not await _can_manage_game(query, session):
        await query.answer("Отменить игру может создатель или администратор.", show_alert=True)
        return
    session.phase = GamePhase.CANCELLED
    await query.message.edit_text("🛑 Игра отменена администратором.")
    await flow.cancel_game(session)
    await query.answer("Игра отменена.")


@router.callback_query(GameLobbyCallback.filter(F.action == "start"))
async def start_lobby(
    query: CallbackQuery,
    callback_data: GameLobbyCallback,
    registry: GameRegistry,
    engine: GameEngine,
    messaging: MessagingService,
    flow: GameFlowService,
    settings: Settings,
) -> None:
    if not isinstance(query.message, Message):
        await query.answer()
        return
    chat_id = query.message.chat.id
    lock = await registry.lock_for(chat_id)
    async with lock:
        session = registry.get_by_token(callback_data.game)
        if (
            session is None
            or session.chat_id != chat_id
            or callback_data.phase != session.phase_number
        ):
            await query.answer("Регистрация уже закрыта.", show_alert=True)
            return
        if not await _can_manage_game(query, session):
            await query.answer("Запустить игру может создатель или администратор.", show_alert=True)
            return
        if session.phase is not GamePhase.LOBBY:
            await query.answer("Партия уже запущена.", show_alert=True)
            return
        if len(session.players) < settings.min_players:
            await query.answer(
                f"Нужно минимум {settings.min_players} игрока.",
                show_alert=True,
            )
            return
        not_ready = [player for player in session.players.values() if not player.ready]
        if not_ready:
            await query.answer(
                f"Не готовы: {', '.join(player.display_name for player in not_ready[:5])}",
                show_alert=True,
            )
            return
        try:
            await flow.ensure_moderation_ready(chat_id)
        except ValueError as error:
            await query.answer(str(error), show_alert=True)
            return
        assignments = engine.start(session)
        await registry.persist(session)
        failed = await messaging.send_roles(session.players.values(), assignments)
        if failed:
            await registry.discard(chat_id)
            await query.message.edit_text(
                "Игра отменена: не удалось отправить роли всем участникам. "
                "Проверьте личные сообщения с ботом и создайте новое лобби."
            )
            await query.answer("Не удалось начать игру.", show_alert=True)
            return
        try:
            await flow.begin_game(session)
        except ValueError as error:
            await query.answer(str(error), show_alert=True)
            return
        await query.answer("Игра началась!")


@router.callback_query(DiscussionCallback.filter())
async def finish_discussion_early(
    query: CallbackQuery,
    callback_data: DiscussionCallback,
    registry: GameRegistry,
    flow: GameFlowService,
) -> None:
    if not isinstance(query.message, Message):
        await query.answer()
        return
    session = registry.get_by_token(callback_data.game)
    if (
        session is None
        or session.chat_id != query.message.chat.id
        or session.phase is not GamePhase.DISCUSSION
        or callback_data.phase != session.phase_number
    ):
        await query.answer("Обсуждение уже завершено.", show_alert=True)
        return
    if not await _can_manage_game(query, session):
        await query.answer(
            "Завершить обсуждение может создатель игры или администратор.",
            show_alert=True,
        )
        return
    await query.answer("Обсуждение завершено. Начинается голосование.")
    await flow.end_discussion_early(session.chat_id, session.phase_number)


@router.callback_query(GamePanelCallback.filter())
async def open_game_panel(
    query: CallbackQuery,
    callback_data: GamePanelCallback,
    registry: GameRegistry,
) -> None:
    session = registry.get_by_token(callback_data.game)
    if (
        session is None
        or callback_data.phase != session.phase_number
        or not isinstance(query.message, Message)
        or session.chat_id != query.message.chat.id
    ):
        await query.answer("Это меню уже устарело.", show_alert=True)
        return
    if callback_data.action == "status":
        remaining = ""
        if session.phase_deadline is not None:
            seconds = max(
                0,
                int((session.phase_deadline - datetime.now(UTC)).total_seconds()),
            )
            remaining = f" Осталось: {seconds} сек."
        await query.answer(
            f"Фаза: {PHASE_NAMES[session.phase]}. "
            f"Живы: {len(session.alive_players)}/{len(session.players)}.{remaining}",
            show_alert=True,
        )
        return
    if callback_data.action == "players":
        alive = ", ".join(player.display_name for player in session.alive_players)
        dead = ", ".join(
            player.display_name for player in session.players.values() if not player.alive
        )
        text = f"Живы ({len(session.alive_players)}): {alive or 'нет'}"
        if dead:
            text += f"\nВыбыли: {dead}"
        if len(text) > 190:
            text = text[:187] + "…"
        await query.answer(text, show_alert=True)
        return
    await query.answer("Неизвестный пункт меню.", show_alert=True)


@router.callback_query(NightActionCallback.filter())
async def submit_night_action(
    query: CallbackQuery,
    callback_data: NightActionCallback,
    registry: GameRegistry,
    engine: GameEngine,
) -> None:
    session = registry.get_by_token(callback_data.game)
    if session is None:
        await query.answer("Эта игра уже завершена.", show_alert=True)
        return
    lock = await registry.lock_for(session.chat_id)
    async with lock:
        session = registry.get_by_token(callback_data.game)
        if session is None:
            await query.answer("Эта игра уже завершена.", show_alert=True)
            return
        action_type = CODE_ACTIONS.get(callback_data.action)
        if action_type is None:
            await query.answer("Неизвестное действие.", show_alert=True)
            return
        try:
            engine.submit_night_action(
                session,
                NightAction(
                    actor_id=query.from_user.id,
                    target_id=callback_data.target,
                    action_type=action_type,
                    phase_number=callback_data.phase,
                ),
            )
        except ValueError as error:
            await query.answer(str(error), show_alert=True)
            return
        await registry.persist(session)
    await query.answer("Ночное действие принято. Его можно изменить до конца ночи.")


@router.callback_query(DayVoteCallback.filter())
async def submit_day_vote(
    query: CallbackQuery,
    callback_data: DayVoteCallback,
    registry: GameRegistry,
    engine: GameEngine,
) -> None:
    session = registry.get_by_token(callback_data.game)
    if session is None:
        await query.answer("Эта игра уже завершена.", show_alert=True)
        return
    lock = await registry.lock_for(session.chat_id)
    async with lock:
        session = registry.get_by_token(callback_data.game)
        if session is None:
            await query.answer("Эта игра уже завершена.", show_alert=True)
            return
        if callback_data.phase != session.phase_number:
            await query.answer("Это голосование уже завершено.", show_alert=True)
            return
        target_id = callback_data.target or None
        try:
            engine.submit_day_vote(session, query.from_user.id, target_id)
        except ValueError as error:
            await query.answer(str(error), show_alert=True)
            return
        await registry.persist(session)
    await query.answer("Ваш голос принят.")


@router.callback_query(RevengeCallback.filter())
async def submit_revenge(
    query: CallbackQuery,
    callback_data: RevengeCallback,
    registry: GameRegistry,
    flow: GameFlowService,
) -> None:
    session = registry.get_by_token(callback_data.game)
    if (
        session is None
        or callback_data.phase != session.phase_number
        or session.pending_revenge_by != query.from_user.id
    ):
        await query.answer("Этот выбор больше недоступен.", show_alert=True)
        return
    await flow.resolve_revenge(
        session.chat_id,
        query.from_user.id,
        callback_data.target or None,
    )
    await query.answer("Выбор принят.")


@router.callback_query(NightPageCallback.filter())
async def paginate_night_targets(
    query: CallbackQuery,
    callback_data: NightPageCallback,
    registry: GameRegistry,
) -> None:
    session = registry.get_by_token(callback_data.game)
    if (
        session is None
        or session.phase is not GamePhase.NIGHT
        or callback_data.phase != session.phase_number
        or not isinstance(query.message, Message)
    ):
        await query.answer("Эти кнопки устарели.", show_alert=True)
        return
    action = CODE_ACTIONS.get(callback_data.action)
    if action is None:
        await query.answer("Неизвестное действие.", show_alert=True)
        return
    await query.message.edit_reply_markup(
        reply_markup=night_target_keyboard(
            session,
            query.from_user.id,
            action,
            callback_data.page,
        )
    )
    await query.answer()


@router.callback_query(DayPageCallback.filter())
async def paginate_day_targets(
    query: CallbackQuery,
    callback_data: DayPageCallback,
    registry: GameRegistry,
) -> None:
    session = registry.get_by_token(callback_data.game)
    if (
        session is None
        or session.phase is not GamePhase.VOTING
        or callback_data.phase != session.phase_number
        or not isinstance(query.message, Message)
    ):
        await query.answer("Эти кнопки устарели.", show_alert=True)
        return
    await query.message.edit_reply_markup(
        reply_markup=day_vote_keyboard(session, callback_data.page)
    )
    await query.answer()


@router.callback_query(RevengePageCallback.filter())
async def paginate_revenge_targets(
    query: CallbackQuery,
    callback_data: RevengePageCallback,
    registry: GameRegistry,
) -> None:
    session = registry.get_by_token(callback_data.game)
    if (
        session is None
        or session.phase is not GamePhase.VERDICT
        or callback_data.phase != session.phase_number
        or session.pending_revenge_by != query.from_user.id
        or not isinstance(query.message, Message)
    ):
        await query.answer("Эти кнопки устарели.", show_alert=True)
        return
    await query.message.edit_reply_markup(
        reply_markup=revenge_keyboard(session, query.from_user.id, callback_data.page)
    )
    await query.answer()
