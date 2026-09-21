from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
)

from app.bot import build_dispatcher
from app.config import get_settings
from app.database.session import create_engine, create_schema
from app.game.action_resolver import ActionResolver
from app.game.engine import GameEngine
from app.game.role_allocator import RoleAllocator, RoleBalanceConfig
from app.game.timers import GameTimerManager
from app.services.game_flow import GameFlowService
from app.services.messaging import MessagingService
from app.services.moderation import ModerationService
from app.services.recovery import RecoveryService
from app.services.registry import GameRegistry


async def configure_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Активировать личные сообщения"),
            BotCommand(command="roles", description="Описание ролей"),
            BotCommand(command="rules", description="Правила игры"),
        ],
        scope=BotCommandScopeAllPrivateChats(),
    )
    await bot.set_my_commands(
        [
            BotCommand(command="game", description="Создать игровое лобби"),
            BotCommand(command="players", description="Участники игры"),
            BotCommand(command="startgame", description="Запустить партию"),
            BotCommand(command="leave", description="Покинуть регистрацию"),
            BotCommand(command="stopgame", description="Остановить игру"),
            BotCommand(command="roles", description="Описание ролей"),
            BotCommand(command="rules", description="Правила игры"),
            BotCommand(command="settings", description="Настройки группы"),
        ],
        scope=BotCommandScopeAllGroupChats(),
    )


async def main() -> None:
    settings = get_settings()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN не задан. Скопируйте .env.example в .env и добавьте токен.")

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = build_dispatcher()

    balance = RoleBalanceConfig.from_yaml(settings.config_dir / "role_balance.yaml")
    engine = GameEngine(
        allocator=RoleAllocator(balance),
        resolver=ActionResolver(),
    )
    registry = GameRegistry()
    messaging = MessagingService(bot)
    moderation = ModerationService(bot)
    timers = GameTimerManager()
    flow = GameFlowService(
        bot,
        registry,
        engine,
        messaging,
        moderation,
        timers,
        settings,
    )

    database_engine = create_engine(settings.database_url)
    await create_schema(database_engine)
    await RecoveryService(registry).restore()
    await configure_commands(bot)

    try:
        await dispatcher.start_polling(
            bot,
            registry=registry,
            engine=engine,
            messaging=messaging,
            flow=flow,
            settings=settings,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        await database_engine.dispose()
        await bot.session.close()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
