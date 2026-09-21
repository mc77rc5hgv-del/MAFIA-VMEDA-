from __future__ import annotations

import asyncio

from app.game.models import GameSession


class GameRegistry:
    """Concurrency-safe active game registry used by the first MVP."""

    def __init__(self) -> None:
        self._games: dict[int, GameSession] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()

    async def lock_for(self, chat_id: int) -> asyncio.Lock:
        async with self._registry_lock:
            return self._locks.setdefault(chat_id, asyncio.Lock())

    def get(self, chat_id: int) -> GameSession | None:
        return self._games.get(chat_id)

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
