from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards.game import lobby_keyboard
from app.config import Settings
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


def _players_text(registry: GameRegistry, chat_id: int) -> str:
    session = registry.get(chat_id)
    if session is None:
        return "Сейчас в группе нет активной игры."
    if not session.players:
        return "В лобби пока никого нет."
    names = "\n".join(
        f"{index}. {player.display_name}"
        for index, player in enumerate(session.players.values(), start=1)
    )
    return f"👥 <b>Участники ({len(session.players)}):</b>\n{names}"


@router.message(Command("game"))
async def create_game(
    message: Message,
    registry: GameRegistry,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    lock = await registry.lock_for(message.chat.id)
    async with lock:
        if registry.get(message.chat.id) is not None:
            await message.answer("В этой группе уже есть активная игра.")
            return
        registry.create(message.chat.id, message.from_user.id)
        await message.answer(
            LOBBY_CREATED.format(
                count=0,
                minimum=settings.min_players,
                maximum=settings.max_players,
            ),
            reply_markup=lobby_keyboard(),
        )


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
        if session.created_by != message.from_user.id:
            await message.answer("Запустить партию может создатель лобби.")
            return
        if len(session.players) < settings.min_players:
            await message.answer(f"Нужно минимум {settings.min_players} игрока.")
            return
        if session.phase is not GamePhase.LOBBY:
            await message.answer("Партия уже запущена.")
            return
        assignments = engine.start(session)
        failed = await messaging.send_roles(session.players.values(), assignments)
        if failed:
            registry.remove(message.chat.id)
            await message.answer(
                "Не удалось отправить роли всем участникам. Игра отменена; "
                "проверьте личные сообщения с ботом и создайте новую регистрацию."
            )
            return
        await flow.begin_game(session)


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
