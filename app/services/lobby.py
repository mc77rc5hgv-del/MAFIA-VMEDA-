from contextlib import suppress

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from app.bot.keyboards.game import lobby_keyboard
from app.config import Settings
from app.game.models import GameSession
from app.texts.events import LOBBY_CREATED


async def refresh_lobby(bot: Bot, game: GameSession, settings: Settings) -> None:
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
