from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models import BugReport, Game, GameParticipant, PlayerStatistic
from app.game.models import Faction, GamePlayer, GameSession, RoleKey
from app.game.roles import get_role_definition


@dataclass(frozen=True, slots=True)
class PlayerStanding:
    display_name: str
    games_played: int
    games_won: int


class StatisticsStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def record_finished_game(self, game: GameSession) -> None:
        async with self.session_factory() as database:
            if await database.get(Game, game.game_id) is not None:
                return
            database.add(
                Game(
                    id=game.game_id,
                    chat_id=game.chat_id,
                    created_by=game.created_by,
                    phase=game.phase.value,
                    winner=_winner_value(game),
                    created_at=game.created_at,
                    started_at=game.started_at,
                    finished_at=game.finished_at,
                )
            )
            for player in game.players.values():
                database.add(
                    GameParticipant(
                        game_id=game.game_id,
                        user_id=player.user_id,
                        role=player.role.value if player.role is not None else None,
                        alive=player.alive,
                        joined_at=player.joined_at,
                    )
                )
                statistic = await database.get(
                    PlayerStatistic,
                    {"chat_id": game.chat_id, "user_id": player.user_id},
                )
                if statistic is None:
                    statistic = PlayerStatistic(
                        chat_id=game.chat_id,
                        user_id=player.user_id,
                        display_name=player.display_name,
                        games_played=0,
                        games_won=0,
                    )
                    database.add(statistic)
                statistic.display_name = player.display_name
                statistic.games_played += 1
                if _is_winner(player, game.winner):
                    statistic.games_won += 1
            await database.commit()

    async def profile(self, chat_id: int, user_id: int) -> PlayerStanding | None:
        async with self.session_factory() as database:
            row = await database.get(
                PlayerStatistic,
                {"chat_id": chat_id, "user_id": user_id},
            )
            return _standing(row) if row is not None else None

    async def top(self, chat_id: int, limit: int = 10) -> list[PlayerStanding]:
        async with self.session_factory() as database:
            query = (
                select(PlayerStatistic)
                .where(PlayerStatistic.chat_id == chat_id)
                .order_by(desc(PlayerStatistic.games_won), desc(PlayerStatistic.games_played))
                .limit(limit)
            )
            return [_standing(row) for row in (await database.scalars(query)).all()]

    async def add_report(self, chat_id: int, user_id: int, text: str) -> int:
        async with self.session_factory() as database:
            report = BugReport(chat_id=chat_id, user_id=user_id, text=text)
            database.add(report)
            await database.commit()
            await database.refresh(report)
            return report.id


def _winner_value(game: GameSession) -> str | None:
    if game.winner is None:
        return None
    kind = "faction" if isinstance(game.winner, Faction) else "role"
    return f"{kind}:{game.winner.value}"


def _is_winner(player: GamePlayer, winner: Faction | RoleKey | None) -> bool:
    if winner is None or player.role is None:
        return False
    if isinstance(winner, Faction):
        return get_role_definition(player.role).faction is winner
    return player.role is winner


def _standing(row: PlayerStatistic) -> PlayerStanding:
    return PlayerStanding(row.display_name, row.games_played, row.games_won)
