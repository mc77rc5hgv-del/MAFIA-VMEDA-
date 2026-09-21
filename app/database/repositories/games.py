from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Game, GameParticipant
from app.game.models import GameSession


class GameRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_from_session(self, game: GameSession) -> None:
        row = Game(
            id=game.game_id,
            chat_id=game.chat_id,
            created_by=game.created_by,
            phase=game.phase.value,
            winner=str(game.winner) if game.winner is not None else None,
            created_at=game.created_at,
            started_at=game.started_at,
            finished_at=game.finished_at,
        )
        self.session.add(row)
        self.session.add_all(
            GameParticipant(
                game_id=game.game_id,
                user_id=player.user_id,
                role=player.role.value if player.role is not None else None,
                alive=player.alive,
                joined_at=player.joined_at,
            )
            for player in game.players.values()
        )
        await self.session.commit()

    async def active_for_chat(self, chat_id: int) -> Game | None:
        query = (
            select(Game)
            .where(Game.chat_id == chat_id)
            .where(Game.phase.not_in(("finished", "cancelled")))
            .order_by(Game.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(query)
