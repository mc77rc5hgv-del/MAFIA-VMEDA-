from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models import ActiveGame
from app.game.models import GameSession
from app.game.serialization import session_from_dict, session_to_dict


class ActiveGameStore:
    """Durable snapshots for every active game mutation."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def save(self, game: GameSession) -> None:
        async with self.session_factory() as database:
            row = await database.get(ActiveGame, game.chat_id)
            payload = session_to_dict(game)
            if row is None:
                database.add(
                    ActiveGame(chat_id=game.chat_id, game_id=game.game_id, payload=payload)
                )
            else:
                row.game_id = game.game_id
                row.payload = payload
            await database.commit()

    async def delete(self, chat_id: int) -> None:
        async with self.session_factory() as database:
            row = await database.get(ActiveGame, chat_id)
            if row is not None:
                await database.delete(row)
                await database.commit()

    async def load_all(self) -> list[GameSession]:
        async with self.session_factory() as database:
            rows = (await database.scalars(select(ActiveGame))).all()
            return [session_from_dict(row.payload) for row in rows]
