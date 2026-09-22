from aiogram import Router

from app.bot.handlers.private.admin import router as admin_router
from app.bot.handlers.private.start import router as start_router

router = Router(name="private")
router.include_router(admin_router)
router.include_router(start_router)
