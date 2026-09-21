from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.game import (
    DayVoteCallback,
    GameLobbyCallback,
    NightActionCallback,
    RevengeCallback,
    lobby_keyboard,
)
from app.config import Settings
from app.game.engine import GameEngine
from app.game.models import ActionType, GamePhase, GamePlayer, NightAction
from app.services.game_flow import GameFlowService
from app.services.messaging import MessagingService
from app.services.registry import GameRegistry
from app.texts.events import LOBBY_CREATED

router = Router(name="callbacks.game")


async def _refresh_lobby(message: Message, count: int, settings: Settings) -> None:
    await message.edit_text(
        LOBBY_CREATED.format(
            count=count,
            minimum=settings.min_players,
            maximum=settings.max_players,
        ),
        reply_markup=lobby_keyboard(),
    )


@router.callback_query(GameLobbyCallback.filter(F.action == "join"))
async def join_lobby(
    query: CallbackQuery,
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
        session = registry.get(chat_id)
        if session is None:
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
        await _refresh_lobby(query.message, len(session.players), settings)
        await query.answer("Вы зарегистрированы!")


@router.callback_query(GameLobbyCallback.filter(F.action == "leave"))
async def leave_lobby(
    query: CallbackQuery,
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
        session = registry.get(chat_id)
        if session is None:
            await query.answer("Регистрация уже закрыта.", show_alert=True)
            return
        try:
            engine.remove_player(session, query.from_user.id)
        except ValueError as error:
            await query.answer(str(error), show_alert=True)
            return
        await _refresh_lobby(query.message, len(session.players), settings)
        await query.answer("Вы вышли из регистрации.")


@router.callback_query(GameLobbyCallback.filter(F.action == "players"))
async def lobby_players(query: CallbackQuery, registry: GameRegistry) -> None:
    if not isinstance(query.message, Message):
        await query.answer()
        return
    session = registry.get(query.message.chat.id)
    if session is None or not session.players:
        await query.answer("В лобби пока никого нет.", show_alert=True)
        return
    names = "\n".join(player.display_name for player in session.players.values())
    await query.answer(names[:190], show_alert=True)


@router.callback_query(GameLobbyCallback.filter(F.action == "start"))
async def start_lobby(
    query: CallbackQuery,
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
        session = registry.get(chat_id)
        if session is None:
            await query.answer("Регистрация уже закрыта.", show_alert=True)
            return
        if session.created_by != query.from_user.id:
            await query.answer("Запустить игру может создатель лобби.", show_alert=True)
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
        assignments = engine.start(session)
        failed = await messaging.send_roles(session.players.values(), assignments)
        if failed:
            registry.remove(chat_id)
            await query.message.edit_text(
                "Игра отменена: не удалось отправить роли всем участникам. "
                "Проверьте личные сообщения с ботом и создайте новое лобби."
            )
            await query.answer("Не удалось начать игру.", show_alert=True)
            return
        await query.message.edit_text("✅ Регистрация завершена. Игра запускается…")
        await flow.begin_game(session)
        await query.answer("Игра началась!")


@router.callback_query(NightActionCallback.filter())
async def submit_night_action(
    query: CallbackQuery,
    callback_data: NightActionCallback,
    registry: GameRegistry,
    engine: GameEngine,
) -> None:
    lock = await registry.lock_for(callback_data.chat_id)
    async with lock:
        session = registry.get(callback_data.chat_id)
        if session is None:
            await query.answer("Эта игра уже завершена.", show_alert=True)
            return
        try:
            engine.submit_night_action(
                session,
                NightAction(
                    actor_id=query.from_user.id,
                    target_id=callback_data.target_id,
                    action_type=ActionType(callback_data.action),
                    phase_number=callback_data.phase_number,
                ),
            )
        except ValueError as error:
            await query.answer(str(error), show_alert=True)
            return
    await query.answer("Ночное действие принято. Его можно изменить до конца ночи.")


@router.callback_query(DayVoteCallback.filter())
async def submit_day_vote(
    query: CallbackQuery,
    callback_data: DayVoteCallback,
    registry: GameRegistry,
    engine: GameEngine,
) -> None:
    lock = await registry.lock_for(callback_data.chat_id)
    async with lock:
        session = registry.get(callback_data.chat_id)
        if session is None:
            await query.answer("Эта игра уже завершена.", show_alert=True)
            return
        if callback_data.phase_number != session.phase_number:
            await query.answer("Это голосование уже завершено.", show_alert=True)
            return
        target_id = callback_data.target_id or None
        try:
            engine.submit_day_vote(session, query.from_user.id, target_id)
        except ValueError as error:
            await query.answer(str(error), show_alert=True)
            return
    await query.answer("Ваш голос принят.")


@router.callback_query(RevengeCallback.filter())
async def submit_revenge(
    query: CallbackQuery,
    callback_data: RevengeCallback,
    registry: GameRegistry,
    flow: GameFlowService,
) -> None:
    session = registry.get(callback_data.chat_id)
    if session is None or session.pending_revenge_by != query.from_user.id:
        await query.answer("Этот выбор больше недоступен.", show_alert=True)
        return
    await flow.resolve_revenge(
        callback_data.chat_id,
        query.from_user.id,
        callback_data.target_id or None,
    )
    await query.answer("Выбор принят.")
