from datetime import UTC, datetime

from app.database.repositories import StatisticsStore
from app.database.session import create_engine, create_schema, create_session_factory
from app.game.models import Faction, GamePhase, GamePlayer, GameSession, RoleKey


async def test_statistics_are_recorded_once_per_game(tmp_path) -> None:
    database_path = tmp_path / "statistics.db"
    engine = create_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    await create_schema(engine)
    store = StatisticsStore(create_session_factory(engine))
    game = GameSession(
        chat_id=-1002,
        created_by=1,
        phase=GamePhase.FINISHED,
        winner=Faction.TOWN,
        finished_at=datetime.now(UTC),
    )
    game.players = {
        1: GamePlayer(1, "Мирный", role=RoleKey.CIVILIAN),
        2: GamePlayer(2, "Мафия", role=RoleKey.MAFIA_BOSS, alive=False),
    }

    await store.record_finished_game(game)
    await store.record_finished_game(game)

    town = await store.profile(game.chat_id, 1)
    mafia = await store.profile(game.chat_id, 2)
    assert town is not None and (town.games_played, town.games_won) == (1, 1)
    assert mafia is not None and (mafia.games_played, mafia.games_won) == (1, 0)
    assert [entry.display_name for entry in await store.top(game.chat_id)] == [
        "Мирный",
        "Мафия",
    ]
    await engine.dispose()
