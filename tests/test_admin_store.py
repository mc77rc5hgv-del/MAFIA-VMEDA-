from datetime import UTC, datetime

from app.database.repositories import AdminStore, StatisticsStore
from app.database.session import create_engine, create_schema, create_session_factory
from app.game.models import Faction, GamePhase, GamePlayer, GameSession, RoleKey


async def test_admin_store_combines_registered_historical_and_active_users(tmp_path) -> None:
    database_path = tmp_path / "admin.db"
    engine = create_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    await create_schema(engine)
    session_factory = create_session_factory(engine)
    admin_store = AdminStore(session_factory)
    statistics = StatisticsStore(session_factory)

    await admin_store.register_user(1, "owner", "Владелец")
    await admin_store.register_user(1, "new_owner", "Новый владелец")
    finished = GameSession(
        chat_id=-1001,
        created_by=2,
        phase=GamePhase.FINISHED,
        winner=Faction.TOWN,
        finished_at=datetime.now(UTC),
    )
    finished.players = {
        2: GamePlayer(2, "Игрок из истории", role=RoleKey.CIVILIAN),
    }
    await statistics.record_finished_game(finished)

    active = GameSession(chat_id=-1002, created_by=3, phase=GamePhase.NIGHT)
    active.players = {
        3: GamePlayer(3, "Активный игрок", username="active"),
    }

    users = await admin_store.list_users((active,))
    by_id = {user.telegram_id: user for user in users}
    summary = await admin_store.summary((active,))

    assert set(by_id) == {1, 2, 3}
    assert by_id[1].username == "new_owner"
    assert by_id[1].display_name == "Новый владелец"
    assert (by_id[2].games_played, by_id[2].games_won) == (1, 1)
    assert by_id[3].active_games == 1
    assert summary.users == 3
    assert summary.completed_games == 1
    assert summary.active_games == 1
    assert summary.groups == 2
    assert summary.participations == 1
    assert summary.wins == 1
    await engine.dispose()
