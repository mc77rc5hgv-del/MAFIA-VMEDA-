from aiogram import Router

from app.bot.handlers.group.game import router as game_router

router = Router(name="group")
router.include_router(game_router)
