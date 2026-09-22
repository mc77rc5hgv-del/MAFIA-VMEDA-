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
    BotCommandScopeChat,
)

from app.bot import build_dispatcher
from app.config import Settings, get_settings
from app.database.repositories import (
    ActiveGameStore,
    AdminStore,
    PlayerNameStore,
    StatisticsStore,
)
from app.database.session import create_engine, create_schema, create_session_factory
from app.game.action_resolver import ActionResolver
from app.game.engine import GameEngine
from app.game.role_allocator import RoleAllocator, RoleBalanceConfig
from app.game.timers import GameTimerManager
from app.services.game_flow import GameFlowService
from app.services.messaging import MessagingService
from app.services.moderation import ModerationService
from app.services.recovery import RecoveryService
from app.services.registry import GameRegistry


async def configure_commands(bot: Bot, settings: Settings) -> None:
    private_commands = [
        BotCommand(command="start", description="Активировать личные сообщения"),
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="name", description="Моё имя в игре"),
        BotCommand(command="roles", description="Описание ролей"),
        BotCommand(command="rules", description="Правила игры"),
    ]
    await bot.set_my_commands(
        private_commands,
        scope=BotCommandScopeAllPrivateChats(),
    )
    await bot.set_my_commands(
        [*private_commands, BotCommand(command="admin", description="Админ-панель")],
        scope=BotCommandScopeChat(chat_id=settings.bot_admin_id),
    )
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть игровое меню"),
            BotCommand(command="game", description="Создать игровое лобби"),
            BotCommand(command="menu", description="Поднять игровое меню"),
            BotCommand(command="name", description="Указать имя в игре"),
            BotCommand(command="players", description="Участники игры"),
            BotCommand(command="status", description="Фаза и оставшееся время"),
            BotCommand(command="profile", description="Профиль и статистика"),
            BotCommand(command="top", description="Рейтинг группы"),
            BotCommand(command="report", description="Сообщить об ошибке"),
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
    database_engine = create_engine(settings.database_url)
    await create_schema(database_engine)
    game_store = ActiveGameStore(create_session_factory(database_engine))
    statistics = StatisticsStore(create_session_factory(database_engine))
    admin_store = AdminStore(create_session_factory(database_engine))
    player_names = PlayerNameStore(create_session_factory(database_engine))
    registry = GameRegistry(game_store)
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
        statistics,
    )

    await RecoveryService(registry, game_store.load_all).restore()
    for restored_game in registry.all():
        await flow.resume(restored_game)
        for player in restored_game.players.values():
            await admin_store.register_user(
                player.user_id,
                player.username,
                player.display_name,
            )
    await configure_commands(bot, settings)

    try:
        await dispatcher.start_polling(
            bot,
            registry=registry,
            engine=engine,
            messaging=messaging,
            moderation=moderation,
            flow=flow,
            settings=settings,
            statistics=statistics,
            admin_store=admin_store,
            player_names=player_names,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        await database_engine.dispose()
        await bot.session.close()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
