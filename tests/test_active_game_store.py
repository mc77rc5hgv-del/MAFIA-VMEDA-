from app.database.repositories import ActiveGameStore
from app.database.session import create_engine, create_schema, create_session_factory
from app.game.models import GamePlayer, GameSession


async def test_active_game_store_saves_restores_and_deletes(tmp_path) -> None:
    database_path = tmp_path / "games.db"
    engine = create_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    await create_schema(engine)
    store = ActiveGameStore(create_session_factory(engine))
    game = GameSession(chat_id=-1001, created_by=7)
    game.players[7] = GamePlayer(7, "Создатель", ready=True)

    await store.save(game)
    restored = await store.load_all()

    assert len(restored) == 1
    assert restored[0].game_id == game.game_id
    assert restored[0].players[7].ready is True

    await store.delete(game.chat_id)
    assert await store.load_all() == []
    await engine.dispose()
