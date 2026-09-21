from aiogram import Router

from app.bot.handlers.admin.settings import router as settings_router

router = Router(name="admin")
router.include_router(settings_router)
