import random
from pathlib import Path

import pytest

from app.game.models import RoleKey
from app.game.role_allocator import RoleAllocator, RoleBalanceConfig

CONFIG_PATH = Path(__file__).parents[1] / "app" / "config" / "role_balance.yaml"


@pytest.fixture
def allocator() -> RoleAllocator:
    return RoleAllocator(RoleBalanceConfig.from_yaml(CONFIG_PATH), random.Random(42))


@pytest.mark.parametrize("player_count", [4, 8, 13, 20, 50])
def test_deck_size_matches_player_count(allocator: RoleAllocator, player_count: int) -> None:
    deck = allocator.build_deck(player_count)
    assert len(deck) == player_count
    assert deck.count(RoleKey.MAFIA_BOSS) == 1


def test_all_roles_are_available_in_large_game(allocator: RoleAllocator) -> None:
    deck = allocator.build_deck(50)
    assert set(RoleKey).issubset(set(deck))


def test_rejects_player_count_outside_limits(allocator: RoleAllocator) -> None:
    with pytest.raises(ValueError):
        allocator.build_deck(3)
    with pytest.raises(ValueError):
        allocator.build_deck(51)


def test_assignment_has_every_user_once(allocator: RoleAllocator) -> None:
    user_ids = list(range(1, 16))
    assignment = allocator.assign(user_ids)
    assert set(assignment) == set(user_ids)
    assert len(assignment) == len(user_ids)
