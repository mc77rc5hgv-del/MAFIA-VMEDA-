from __future__ import annotations

import asyncio
import json
import os

from aiogram import Bot
from aiogram.types import (
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    ChatAdministratorRights,
)


async def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is missing")

    bot = Bot(token)
    try:
        await bot.set_my_name(name="Мафия ВМедА")
        await bot.set_my_short_description(
            short_description="Бесплатная «Мафия ВМедА» для групп от 4 до 50 игроков."
        )
        await bot.set_my_description(
            description=(
                "Неофициальный игровой бот «Мафия ВМедА». Добавьте бота в группу, "
                "выдайте права на удаление сообщений и ограничение участников, затем "
                "откройте регистрацию командой /game. Роли и действия приходят в личный чат."
            )
        )
        await bot.set_my_default_administrator_rights(
            rights=ChatAdministratorRights(
                is_anonymous=False,
                can_manage_chat=True,
                can_delete_messages=True,
                can_manage_video_chats=False,
                can_restrict_members=True,
                can_promote_members=False,
                can_change_info=False,
                can_invite_users=True,
                can_post_stories=False,
                can_edit_stories=False,
                can_delete_stories=False,
                can_send_welcome_messages=False,
                can_pin_messages=True,
                can_manage_topics=False,
            ),
            for_channels=False,
        )
        info = await bot.get_me()
        description = await bot.get_my_description()
        short_description = await bot.get_my_short_description()
        group_commands = await bot.get_my_commands(scope=BotCommandScopeAllGroupChats())
        private_commands = await bot.get_my_commands(scope=BotCommandScopeAllPrivateChats())
        photos = await bot.get_user_profile_photos(info.id, limit=1)
        webhook = await bot.get_webhook_info()
        default_rights = await bot.get_my_default_administrator_rights(for_channels=False)
        print(
            json.dumps(
                {
                    "username": info.username,
                    "name": info.full_name,
                    "can_join_groups": info.can_join_groups,
                    "description": description.description,
                    "short_description": short_description.short_description,
                    "group_commands": [command.command for command in group_commands],
                    "private_commands": [command.command for command in private_commands],
                    "has_profile_photo": photos.total_count > 0,
                    "webhook_url": webhook.url,
                    "default_admin_rights": {
                        "can_delete_messages": default_rights.can_delete_messages,
                        "can_restrict_members": default_rights.can_restrict_members,
                        "can_pin_messages": default_rights.can_pin_messages,
                    },
                },
                ensure_ascii=True,
            )
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
