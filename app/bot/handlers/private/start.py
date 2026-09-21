from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.texts.roles import roles_text
from app.texts.rules import RULES_TEXT

router = Router(name="private.start")
router.message.filter(F.chat.type == "private")


@router.message(CommandStart())
async def start_private(message: Message) -> None:
    await message.answer(
        "🎓 <b>Мафия ВМедА</b>\n\n"
        "Личные сообщения активированы. Теперь вы можете вступать в игры в группах.\n\n"
        "Команды:\n"
        "/roles — персонажи\n"
        "/rules — правила"
    )


@router.message(Command("roles"))
async def show_roles(message: Message) -> None:
    await message.answer(roles_text())


@router.message(Command("rules"))
async def show_rules(message: Message) -> None:
    await message.answer(RULES_TEXT)
