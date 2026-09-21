from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable

from app.game.models import GameSession
from app.services.registry import GameRegistry


class RecoveryService:
    """Boundary for persistent recovery; repository integration follows in stage two."""

    def __init__(
        self,
        registry: GameRegistry,
        loader: Callable[[], Awaitable[Iterable[GameSession]]] | None = None,
    ) -> None:
        self.registry = registry
        self.loader = loader

    async def restore(self) -> int:
        if self.loader is None:
            return 0
        restored = 0
        for session in await self.loader():
            if self.registry.get(session.chat_id) is None:
                self.registry.restore(session)
                restored += 1
        return restored
