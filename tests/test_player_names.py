import pytest

from app.database.repositories import PlayerNameStore, normalize_game_name, unique_game_name
from app.database.session import create_engine, create_schema, create_session_factory


async def test_player_name_is_persisted_and_can_be_changed(tmp_path) -> None:
    database_path = tmp_path / "names.db"
    engine = create_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    await create_schema(engine)
    store = PlayerNameStore(create_session_factory(engine))

    assert await store.get(10) is None
    await store.set(10, "Александр")
    assert await store.get(10) == "Александр"
    await store.set(10, "Саня")
    assert await store.get(10) == "Саня"

    await engine.dispose()


def test_player_name_is_normalized_and_validated() -> None:
    assert normalize_game_name("  Доктор   Иванов  ") == "Доктор Иванов"

    with pytest.raises(ValueError, match="от 2 до 32"):
        normalize_game_name("Я")
    with pytest.raises(ValueError, match="команды"):
        normalize_game_name("/stopgame")


def test_duplicate_player_name_gets_stable_short_suffix() -> None:
    name = unique_game_name("Александр", 1326779223, ["александр", "Мария"])

    assert name == "Александр · 9223"
    assert len(name) <= 32
