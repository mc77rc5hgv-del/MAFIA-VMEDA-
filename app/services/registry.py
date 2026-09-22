from __future__ import annotations

import asyncio
from typing import Protocol

from app.game.models import GameSession


class GameStore(Protocol):
    async def save(self, game: GameSession) -> None: ...

    async def delete(self, chat_id: int) -> None: ...


class GameRegistry:
    """Concurrency-safe active game registry backed by durable snapshots."""

    def __init__(self, store: GameStore | None = None) -> None:
        self._games: dict[int, GameSession] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()
        self._store = store

    async def lock_for(self, chat_id: int) -> asyncio.Lock:
        async with self._registry_lock:
            return self._locks.setdefault(chat_id, asyncio.Lock())

    def get(self, chat_id: int) -> GameSession | None:
        return self._games.get(chat_id)

    def get_by_token(self, token: str) -> GameSession | None:
        return next(
            (game for game in self._games.values() if game.callback_token == token),
            None,
        )

    def create(self, chat_id: int, created_by: int) -> GameSession:
        if chat_id in self._games:
            raise ValueError("В этой группе уже есть активная игра")
        session = GameSession(chat_id=chat_id, created_by=created_by)
        self._games[chat_id] = session
        return session

    def remove(self, chat_id: int) -> GameSession | None:
        return self._games.pop(chat_id, None)

    def restore(self, session: GameSession) -> None:
        if session.chat_id in self._games:
            raise ValueError("Для группы уже восстановлена активная игра")
        self._games[session.chat_id] = session

    def all(self) -> tuple[GameSession, ...]:
        return tuple(self._games.values())

    def for_player(self, user_id: int) -> tuple[GameSession, ...]:
        return tuple(game for game in self._games.values() if user_id in game.players)

    async def persist(self, session: GameSession) -> None:
        if self._store is not None:
            await self._store.save(session)

    async def discard(self, chat_id: int) -> GameSession | None:
        session = self.remove(chat_id)
        if self._store is not None:
            await self._store.delete(chat_id)
        return session
