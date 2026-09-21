from aiogram import Router

from app.bot.handlers.private.start import router as start_router

router = Router(name="private")
router.include_router(start_router)
