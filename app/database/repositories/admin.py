from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models import BugReport, Game, GameParticipant, PlayerStatistic, User
from app.game.models import GameSession


@dataclass(frozen=True, slots=True)
class AdminUser:
    telegram_id: int
    display_name: str
    username: str | None
    games_played: int
    games_won: int
    first_seen: datetime | None
    last_seen: datetime | None
    active_games: int


@dataclass(frozen=True, slots=True)
class AdminSummary:
    users: int
    completed_games: int
    active_games: int
    groups: int
    participations: int
    wins: int
    reports: int


class AdminStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def register_user(
        self,
        telegram_id: int,
        username: str | None,
        display_name: str,
    ) -> None:
        async with self.session_factory() as database:
            user = await database.get(User, telegram_id)
            if user is None:
                database.add(
                    User(
                        telegram_id=telegram_id,
                        username=username,
                        display_name=display_name,
                    )
                )
            else:
                user.username = username
                user.display_name = display_name
                user.updated_at = datetime.now(UTC)
            try:
                await database.commit()
            except IntegrityError:
                await database.rollback()
                user = await database.get(User, telegram_id)
                if user is not None:
                    user.username = username
                    user.display_name = display_name
                    user.updated_at = datetime.now(UTC)
                    await database.commit()

    async def list_users(
        self,
        active_games: Iterable[GameSession] = (),
    ) -> list[AdminUser]:
        games = tuple(active_games)
        async with self.session_factory() as database:
            stored_users = (await database.scalars(select(User))).all()
            statistic_rows = (
                await database.execute(
                    select(
                        PlayerStatistic.user_id,
                        func.max(PlayerStatistic.display_name),
                        func.sum(PlayerStatistic.games_played),
                        func.sum(PlayerStatistic.games_won),
                        func.max(PlayerStatistic.updated_at),
                    ).group_by(PlayerStatistic.user_id)
                )
            ).all()

        users: dict[int, dict[str, object]] = {}
        for user in stored_users:
            users[user.telegram_id] = {
                "display_name": user.display_name,
                "username": user.username,
                "games_played": 0,
                "games_won": 0,
                "first_seen": user.created_at,
                "last_seen": user.updated_at,
                "active_games": 0,
            }
        for user_id, display_name, games_played, games_won, updated_at in statistic_rows:
            record = users.setdefault(
                user_id,
                {
                    "display_name": display_name,
                    "username": None,
                    "games_played": 0,
                    "games_won": 0,
                    "first_seen": None,
                    "last_seen": updated_at,
                    "active_games": 0,
                },
            )
            record["games_played"] = int(games_played or 0)
            record["games_won"] = int(games_won or 0)
            if _timestamp(updated_at) > _timestamp(record["last_seen"]):
                record["last_seen"] = updated_at

        for game in games:
            for player in game.players.values():
                record = users.setdefault(
                    player.user_id,
                    {
                        "display_name": player.display_name,
                        "username": player.username,
                        "games_played": 0,
                        "games_won": 0,
                        "first_seen": player.joined_at,
                        "last_seen": player.joined_at,
                        "active_games": 0,
                    },
                )
                record["display_name"] = player.display_name
                record["username"] = player.username or record["username"]
                record["active_games"] = int(record["active_games"]) + 1
                if _timestamp(player.joined_at) > _timestamp(record["last_seen"]):
                    record["last_seen"] = player.joined_at

        result = [
            AdminUser(
                telegram_id=user_id,
                display_name=str(record["display_name"]),
                username=str(record["username"]) if record["username"] else None,
                games_played=int(record["games_played"]),
                games_won=int(record["games_won"]),
                first_seen=record["first_seen"]
                if isinstance(record["first_seen"], datetime)
                else None,
                last_seen=record["last_seen"]
                if isinstance(record["last_seen"], datetime)
                else None,
                active_games=int(record["active_games"]),
            )
            for user_id, record in users.items()
        ]
        return sorted(
            result, key=lambda user: (_timestamp(user.last_seen), user.telegram_id), reverse=True
        )

    async def summary(
        self,
        active_games: Iterable[GameSession] = (),
    ) -> AdminSummary:
        games = tuple(active_games)
        users = await self.list_users(games)
        async with self.session_factory() as database:
            completed_games = await database.scalar(select(func.count()).select_from(Game)) or 0
            participations = (
                await database.scalar(select(func.count()).select_from(GameParticipant)) or 0
            )
            wins = await database.scalar(select(func.sum(PlayerStatistic.games_won))) or 0
            reports = await database.scalar(select(func.count()).select_from(BugReport)) or 0
            completed_chat_ids = set(
                (await database.scalars(select(Game.chat_id).distinct())).all()
            )
        group_ids = completed_chat_ids | {game.chat_id for game in games}
        return AdminSummary(
            users=len(users),
            completed_games=int(completed_games),
            active_games=len(games),
            groups=len(group_ids),
            participations=int(participations),
            wins=int(wins),
            reports=int(reports),
        )


def _timestamp(value: object) -> float:
    if not isinstance(value, datetime):
        return float("-inf")
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()
