from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


class GameTimerManager:
    def __init__(self) -> None:
        self._tasks: dict[tuple[int, str], asyncio.Task[None]] = {}

    def schedule(
        self,
        chat_id: int,
        name: str,
        delay_seconds: float,
        callback: Callable[[], Awaitable[None]],
    ) -> None:
        self.cancel(chat_id, name)
        self._tasks[(chat_id, name)] = asyncio.create_task(
            self._run(chat_id, name, delay_seconds, callback)
        )

    def cancel(self, chat_id: int, name: str) -> None:
        task = self._tasks.pop((chat_id, name), None)
        if task is not None and task is not asyncio.current_task():
            task.cancel()

    def cancel_all(self, chat_id: int) -> None:
        keys = [key for key in self._tasks if key[0] == chat_id]
        for _, name in keys:
            self.cancel(chat_id, name)

    async def _run(
        self,
        chat_id: int,
        name: str,
        delay_seconds: float,
        callback: Callable[[], Awaitable[None]],
    ) -> None:
        try:
            await asyncio.sleep(delay_seconds)
            await callback()
        finally:
            self._tasks.pop((chat_id, name), None)
