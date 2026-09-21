from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="admin.settings")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))


@router.message(Command("settings"))
async def settings_placeholder(message: Message) -> None:
    await message.answer(
        "⚙️ Настройки группы появятся на следующем этапе. "
        "Сейчас используются безопасные значения по умолчанию."
    )
