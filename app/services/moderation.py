import asyncio
from collections.abc import Iterable
from contextlib import suppress
from datetime import datetime

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import ChatPermissions

from app.game.models import GamePhase, GameSession

MUTED_PERMISSIONS = ChatPermissions(can_send_messages=False)
OPEN_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_react_to_messages=True,
    can_invite_users=True,
)


class ModerationService:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self._restriction_limit = asyncio.Semaphore(8)

    async def ensure_bot_permissions(self, chat_id: int) -> None:
        bot_user = await self.bot.get_me()
        member = await self.bot.get_chat_member(chat_id, bot_user.id)
        if member.status is ChatMemberStatus.CREATOR:
            return
        missing: list[str] = []
        if member.status is not ChatMemberStatus.ADMINISTRATOR:
            missing.append("назначить бота администратором")
        else:
            if not getattr(member, "can_restrict_members", False):
                missing.append("ограничивать участников")
            if not getattr(member, "can_delete_messages", False):
                missing.append("удалять сообщения")
        if missing:
            raise ValueError("Боту нужны права: " + ", ".join(missing) + ".")

    async def lock_chat_for_game(self, session: GameSession) -> None:
        if session.original_chat_permissions is None:
            chat = await self.bot.get_chat(session.chat_id)
            permissions = chat.permissions or OPEN_PERMISSIONS
            session.original_chat_permissions = permissions.model_dump()
        if not session.original_player_permissions:
            await self._snapshot_player_permissions(session)
        await self._set_chat_permissions(session.chat_id, MUTED_PERMISSIONS)

    async def mute_player(self, chat_id: int, user_id: int) -> None:
        await self._restrict(chat_id, user_id, MUTED_PERMISSIONS)

    async def allow_player(self, session: GameSession, user_id: int) -> None:
        permissions, until_date = self._original_player_permissions(session, user_id)
        await self._restrict(
            session.chat_id,
            user_id,
            permissions,
            until_date=until_date,
        )

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        while True:
            try:
                await self.bot.delete_message(chat_id, message_id)
                return
            except TelegramRetryAfter as error:
                await asyncio.sleep(error.retry_after)
            except (TelegramBadRequest, TelegramForbiddenError):
                return

    async def set_night_permissions(self, session: GameSession) -> None:
        await self._apply_many(
            self.mute_player(session.chat_id, player.user_id) for player in session.players.values()
        )

    async def set_day_permissions(self, session: GameSession) -> None:
        operations = []
        for player in session.players.values():
            if self.can_user_speak(session, player.user_id):
                operations.append(self.allow_player(session, player.user_id))
            else:
                operations.append(self.mute_player(session.chat_id, player.user_id))
        await self._apply_many(operations)

    async def restore_permissions(self, session: GameSession) -> None:
        if session.original_chat_permissions is None:
            return
        permissions = self._original_permissions(session)
        with suppress(TelegramBadRequest, TelegramForbiddenError):
            await self._set_chat_permissions(session.chat_id, permissions)
        await self._apply_many(
            self.allow_player(session, player.user_id) for player in session.players.values()
        )

    async def _restrict(
        self,
        chat_id: int,
        user_id: int,
        permissions: ChatPermissions,
        *,
        until_date: int | None = None,
    ) -> None:
        async with self._restriction_limit:
            while True:
                try:
                    await self.bot.restrict_chat_member(
                        chat_id,
                        user_id,
                        permissions=permissions,
                        until_date=until_date,
                        use_independent_chat_permissions=True,
                    )
                    return
                except TelegramRetryAfter as error:
                    await asyncio.sleep(error.retry_after)

    async def _set_chat_permissions(
        self,
        chat_id: int,
        permissions: ChatPermissions,
    ) -> None:
        while True:
            try:
                await self.bot.set_chat_permissions(
                    chat_id,
                    permissions=permissions,
                    use_independent_chat_permissions=True,
                )
                return
            except TelegramRetryAfter as error:
                await asyncio.sleep(error.retry_after)

    async def _snapshot_player_permissions(self, session: GameSession) -> None:
        async def snapshot(user_id: int) -> tuple[int, dict[str, bool | int | None]]:
            member = await self.bot.get_chat_member(session.chat_id, user_id)
            base_permissions = self._original_permissions(session)
            values: dict[str, bool | int | None]
            if member.status is ChatMemberStatus.RESTRICTED:
                values = {
                    name: getattr(member, name, None) for name in ChatPermissions.model_fields
                }
            else:
                values = base_permissions.model_dump()
            until_date = getattr(member, "until_date", None)
            if isinstance(until_date, datetime):
                values["until_date"] = int(until_date.timestamp())
            elif isinstance(until_date, int):
                values["until_date"] = until_date
            else:
                values["until_date"] = None
            return user_id, values

        snapshots = await asyncio.gather(
            *(snapshot(player.user_id) for player in session.players.values())
        )
        session.original_player_permissions = dict(snapshots)

    @staticmethod
    def can_user_speak(session: GameSession, user_id: int) -> bool:
        if session.phase is GamePhase.LOBBY:
            return True
        player = session.players.get(user_id)
        if player is None or not player.alive or user_id in session.day_blocked:
            return False
        return session.phase in {
            GamePhase.DISCUSSION,
            GamePhase.VOTING,
            GamePhase.VERDICT,
        }

    @staticmethod
    def _original_permissions(session: GameSession) -> ChatPermissions:
        if session.original_chat_permissions is None:
            return OPEN_PERMISSIONS
        return ChatPermissions.model_validate(session.original_chat_permissions)

    @classmethod
    def _original_player_permissions(
        cls,
        session: GameSession,
        user_id: int,
    ) -> tuple[ChatPermissions, int | None]:
        values = session.original_player_permissions.get(user_id)
        if values is None:
            return cls._original_permissions(session), None
        permissions = ChatPermissions.model_validate(values)
        until_date = values.get("until_date")
        return permissions, int(until_date) if until_date is not None else None

    @staticmethod
    async def _apply_many(operations: Iterable[object]) -> None:
        async def safely(operation: object) -> None:
            with suppress(TelegramBadRequest, TelegramForbiddenError):
                await operation  # type: ignore[misc]

        await asyncio.gather(*(safely(operation) for operation in operations))
