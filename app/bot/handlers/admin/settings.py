from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.filters import AdminFilter
from app.config import Settings

router = Router(name="admin.settings")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))


@router.message(Command("settings"), AdminFilter())
async def show_settings(message: Message, settings: Settings) -> None:
    await message.answer(
        "⚙️ <b>Настройки Мафии ВМедА</b>\n"
        f"Игроков: <b>{settings.min_players}–{settings.max_players}</b>\n"
        f"Ночь: <b>{settings.night_seconds} сек.</b>\n"
        f"Обсуждение: <b>{settings.discussion_seconds} сек.</b>\n"
        f"Голосование: <b>{settings.voting_seconds} сек.</b>\n"
        f"Выбор после приговора: <b>{settings.verdict_seconds} сек.</b>\n\n"
        "Значения задаются переменными окружения сервиса."
    )
