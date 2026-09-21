from aiogram import Dispatcher

from app.bot.handlers.admin import router as admin_router
from app.bot.handlers.callbacks import router as callbacks_router
from app.bot.handlers.group import router as group_router
from app.bot.handlers.private import router as private_router


def build_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(private_router)
    dispatcher.include_router(admin_router)
    dispatcher.include_router(group_router)
    dispatcher.include_router(callbacks_router)
    return dispatcher
