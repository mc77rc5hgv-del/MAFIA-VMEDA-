from dataclasses import dataclass

from app.game.models import Faction, GameSession, RoleKey


@dataclass(frozen=True, slots=True)
class GameStatistics:
    total_players: int
    alive_players: int
    phases_played: int
    winner: Faction | RoleKey | None


class StatisticsService:
    @staticmethod
    def summarize(session: GameSession) -> GameStatistics:
        return GameStatistics(
            total_players=len(session.players),
            alive_players=len(session.alive_players),
            phases_played=session.phase_number,
            winner=session.winner,
        )
