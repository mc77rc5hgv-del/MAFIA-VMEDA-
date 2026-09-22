from datetime import UTC, datetime
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.bot.handlers.callbacks.game import _refresh_lobby
from app.bot.keyboards.game import lobby_keyboard
from app.bot.middlewares import GameChatGuardMiddleware
from app.config import Settings
from app.database.repositories import StatisticsStore
from app.game.engine import GameEngine
from app.game.models import GamePhase
from app.services.game_flow import GameFlowService
from app.services.messaging import MessagingService
from app.services.registry import GameRegistry
from app.texts.events import LOBBY_CREATED
from app.texts.roles import roles_text
from app.texts.rules import RULES_TEXT

router = Router(name="group.game")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))
router.message.outer_middleware(GameChatGuardMiddleware())


def _players_text(registry: GameRegistry, chat_id: int) -> str:
    session = registry.get(chat_id)
    if session is None:
        return "Сейчас в группе нет активной игры."
    if not session.players:
        return "В лобби пока никого нет."
    names = "\n".join(
        f"{index}. {'✅' if player.ready else '⏳'} {escape(player.display_name)}"
        for index, player in enumerate(session.players.values(), start=1)
    )
    return f"👥 <b>Участники ({len(session.players)}):</b>\n{names}"


@router.message(CommandStart())
@router.message(Command("game", "menu"))
async def create_game(
    message: Message,
    registry: GameRegistry,
    settings: Settings,
    flow: GameFlowService,
) -> None:
    if message.from_user is None:
        return
    lock = await registry.lock_for(message.chat.id)
    async with lock:
        existing = registry.get(message.chat.id)
        if existing is not None:
            if existing.phase is GamePhase.LOBBY:
                await _refresh_lobby(message.bot, existing, settings)
                await registry.persist(existing)
            else:
                await flow.repost_current(existing)
            return
        session = registry.create(message.chat.id, message.from_user.id)
        bot_user = await message.bot.get_me()
        lobby_text = LOBBY_CREATED.format(
            count=0,
            ready=0,
            minimum=settings.min_players,
            maximum=settings.max_players,
        )
        lobby_message = await message.answer(
            lobby_text,
            reply_markup=lobby_keyboard(session, bot_user.username),
        )
        session.main_message_id = lobby_message.message_id
        session.main_message_text = lobby_text
        await registry.persist(session)


@router.message(Command("players"))
async def show_players(message: Message, registry: GameRegistry) -> None:
    await message.answer(_players_text(registry, message.chat.id))


@router.message(Command("roles"))
async def show_roles(message: Message) -> None:
    await message.answer(roles_text())


@router.message(Command("rules"))
async def show_rules(message: Message) -> None:
    await message.answer(RULES_TEXT)


@router.message(Command("leave"))
async def leave_game(message: Message, registry: GameRegistry, engine: GameEngine) -> None:
    if message.from_user is None:
        return
    lock = await registry.lock_for(message.chat.id)
    async with lock:
        session = registry.get(message.chat.id)
        if session is None:
            await message.answer("Активной игры нет.")
            return
        try:
            engine.remove_player(session, message.from_user.id)
        except ValueError as error:
            await message.answer(str(error))
            return
        await registry.persist(session)
        await message.answer(f"{message.from_user.full_name} покинул регистрацию.")


@router.message(Command("startgame"))
async def start_game_command(
    message: Message,
    registry: GameRegistry,
    engine: GameEngine,
    messaging: MessagingService,
    flow: GameFlowService,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    lock = await registry.lock_for(message.chat.id)
    async with lock:
        session = registry.get(message.chat.id)
        if session is None:
            await message.answer("Сначала создайте игру командой /game.")
            return
        member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        is_admin = member.status in {
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }
        if session.created_by != message.from_user.id and not is_admin:
            await message.answer("Запустить партию может создатель или администратор.")
            return
        if len(session.players) < settings.min_players:
            await message.answer(f"Нужно минимум {settings.min_players} игрока.")
            return
        if session.phase is not GamePhase.LOBBY:
            await message.answer("Партия уже запущена.")
            return
        not_ready = [player for player in session.players.values() if not player.ready]
        if not_ready:
            names = ", ".join(escape(player.display_name) for player in not_ready[:8])
            await message.answer(f"Сначала подтвердите готовность всех игроков: {names}")
            return
        try:
            await flow.ensure_moderation_ready(message.chat.id)
        except ValueError as error:
            await message.answer(str(error))
            return
        assignments = engine.start(session)
        await registry.persist(session)
        failed = await messaging.send_roles(session.players.values(), assignments)
        if failed:
            await registry.discard(message.chat.id)
            await message.answer(
                "Не удалось отправить роли всем участникам. Игра отменена; "
                "проверьте личные сообщения с ботом и создайте новую регистрацию."
            )
            return
        try:
            await flow.begin_game(session)
        except ValueError as error:
            await message.answer(str(error))


@router.message(Command("status"))
async def show_status(message: Message, registry: GameRegistry) -> None:
    session = registry.get(message.chat.id)
    if session is None:
        await message.answer("Сейчас в группе нет активной игры.")
        return
    phase_names = {
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
    remaining = ""
    if session.phase_deadline is not None:
        seconds = max(0, int((session.phase_deadline - datetime.now(UTC)).total_seconds()))
        remaining = f"\nДо конца фазы: <b>{seconds} сек.</b>"
    await message.answer(
        f"🎭 Фаза: <b>{phase_names[session.phase]}</b>\n"
        f"Игроков: <b>{len(session.players)}</b>, в игре: "
        f"<b>{len(session.alive_players)}</b>{remaining}"
    )


@router.message(Command("profile"))
async def show_profile(message: Message, statistics: StatisticsStore) -> None:
    if message.from_user is None:
        return
    profile = await statistics.profile(message.chat.id, message.from_user.id)
    if profile is None:
        await message.answer("Завершённых партий в этой группе пока нет.")
        return
    win_rate = round(profile.games_won * 100 / profile.games_played)
    await message.answer(
        f"🎖 <b>{escape(profile.display_name)}</b>\n"
        f"Партий: <b>{profile.games_played}</b>\n"
        f"Побед: <b>{profile.games_won}</b> ({win_rate}%)"
    )


@router.message(Command("top"))
async def show_top(message: Message, statistics: StatisticsStore) -> None:
    standings = await statistics.top(message.chat.id)
    if not standings:
        await message.answer("Рейтинг появится после первой завершённой партии.")
        return
    lines = ["🏆 <b>Рейтинг группы</b>"]
    for index, standing in enumerate(standings, start=1):
        lines.append(
            f"{index}. {escape(standing.display_name)} — "
            f"{standing.games_won}/{standing.games_played} побед"
        )
    await message.answer("\n".join(lines))


@router.message(Command("report"))
async def submit_report(message: Message, statistics: StatisticsStore) -> None:
    if message.from_user is None:
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Опишите проблему после команды: /report текст ошибки")
        return
    report_id = await statistics.add_report(
        message.chat.id,
        message.from_user.id,
        parts[1].strip()[:4000],
    )
    await message.answer(f"✅ Сообщение сохранено. Номер обращения: <b>#{report_id}</b>.")


@router.message(Command("stopgame"))
async def stop_game(
    message: Message,
    registry: GameRegistry,
    bot: Bot,
    flow: GameFlowService,
) -> None:
    if message.from_user is None:
        return
    lock = await registry.lock_for(message.chat.id)
    async with lock:
        session = registry.get(message.chat.id)
        if session is None:
            await message.answer("Активной игры нет.")
            return
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        is_admin = member.status in {
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }
        if session.created_by != message.from_user.id and not is_admin:
            await message.answer("Остановить игру может создатель лобби или администратор.")
            return
        session.phase = GamePhase.CANCELLED
        await flow.cancel_game(session)
        await message.answer("🛑 Игра остановлена.")


@router.message()
async def consume_group_message() -> None:
    """Keep the group router active so the game chat guard sees regular messages."""
