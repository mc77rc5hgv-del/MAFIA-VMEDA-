from aiogram import Router

from app.bot.handlers.callbacks.game import router as game_router

router = Router(name="callbacks")
router.include_router(game_router)
