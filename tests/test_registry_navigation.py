from app.game.models import GamePlayer
from app.services.registry import GameRegistry


def test_registry_returns_only_games_joined_by_player() -> None:
    registry = GameRegistry()
    first = registry.create(-1001, 1)
    second = registry.create(-1002, 2)
    first.players[10] = GamePlayer(10, "Курсант")
    second.players[20] = GamePlayer(20, "Другой курсант")

    assert registry.for_player(10) == (first,)
    assert registry.for_player(999) == ()
