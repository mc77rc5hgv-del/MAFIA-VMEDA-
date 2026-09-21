import random
from pathlib import Path

import pytest

from app.game.action_resolver import ActionResolver
from app.game.engine import GameEngine
from app.game.models import (
    ActionType,
    GamePhase,
    GamePlayer,
    GameSession,
    NightAction,
    RoleKey,
)
from app.game.role_allocator import RoleAllocator, RoleBalanceConfig

CONFIG_PATH = Path(__file__).parents[1] / "app" / "config" / "role_balance.yaml"


def make_engine() -> GameEngine:
    allocator = RoleAllocator(RoleBalanceConfig.from_yaml(CONFIG_PATH), random.Random(7))
    return GameEngine(
        allocator,
        resolver=ActionResolver(lucky_survival_chance=0, rng=random.Random(7)),
    )


def player(user_id: int, role: RoleKey, *, alive: bool = True) -> GamePlayer:
    return GamePlayer(user_id, str(user_id), role=role, alive=alive)


def test_doctor_can_self_heal_only_once() -> None:
    engine = make_engine()
    session = GameSession(chat_id=-100, created_by=1, phase=GamePhase.NIGHT, phase_number=1)
    session.players = {
        1: player(1, RoleKey.DOCTOR),
        2: player(2, RoleKey.MAFIA_BOSS),
        3: player(3, RoleKey.CIVILIAN),
    }
    engine.submit_night_action(session, NightAction(1, 1, ActionType.HEAL, 1))
    engine.resolve_night(session)

    assert session.players[1].metadata["self_heal_used"] is True
    session.phase = GamePhase.NIGHT
    session.phase_number = 2
    with pytest.raises(ValueError, match="Самолечение"):
        engine.submit_night_action(session, NightAction(1, 1, ActionType.HEAL, 2))


def test_mafia_boss_and_commissioner_are_inherited_after_night() -> None:
    engine = make_engine()
    session = GameSession(chat_id=-100, created_by=1, phase=GamePhase.NIGHT, phase_number=1)
    session.players = {
        1: player(1, RoleKey.MAFIA_BOSS),
        2: player(2, RoleKey.MAFIA),
        3: player(3, RoleKey.COMMISSIONER),
        4: player(4, RoleKey.WARRANT_OFFICER),
        5: player(5, RoleKey.MANIAC),
        6: player(6, RoleKey.CIVILIAN),
    }
    session.night_actions = {
        1: NightAction(1, 3, ActionType.MAFIA_VOTE, 1),
        5: NightAction(5, 1, ActionType.MANIAC_KILL, 1),
    }

    result = engine.resolve_night(session)

    assert result.role_changes == {2: RoleKey.MAFIA_BOSS, 4: RoleKey.COMMISSIONER}
    assert session.players[2].role is RoleKey.MAFIA_BOSS
    assert session.players[4].role is RoleKey.COMMISSIONER


def test_snow_white_target_cannot_vote_next_day() -> None:
    engine = make_engine()
    session = GameSession(chat_id=-100, created_by=1, phase=GamePhase.VOTING)
    session.players = {
        1: player(1, RoleKey.CIVILIAN),
        2: player(2, RoleKey.SNOW_WHITE),
        3: player(3, RoleKey.MAFIA_BOSS),
    }
    session.day_blocked = {1}

    with pytest.raises(ValueError, match="Белоснежка"):
        engine.submit_day_vote(session, 1, 3)


def test_tied_day_vote_executes_nobody_and_starts_new_night() -> None:
    engine = make_engine()
    session = GameSession(chat_id=-100, created_by=1, phase=GamePhase.VOTING)
    session.players = {
        1: player(1, RoleKey.MAFIA_BOSS),
        2: player(2, RoleKey.CIVILIAN),
        3: player(3, RoleKey.DOCTOR),
        4: player(4, RoleKey.CIVILIAN),
    }
    session.day_votes = {1: 2, 2: 1}

    result = engine.resolve_day_vote(session)

    assert result.tied_candidates == {1, 2}
    assert all(item.alive for item in session.players.values())
    assert session.phase is GamePhase.NIGHT


def test_suicide_wins_only_from_day_execution() -> None:
    engine = make_engine()
    session = GameSession(chat_id=-100, created_by=1, phase=GamePhase.VOTING)
    session.players = {
        1: player(1, RoleKey.SUICIDE),
        2: player(2, RoleKey.MAFIA_BOSS),
        3: player(3, RoleKey.CIVILIAN),
    }
    session.day_votes = {2: 1, 3: 1}

    result = engine.resolve_day_vote(session)

    assert result.lynched_user_id == 1
    assert session.winner is RoleKey.SUICIDE
    assert session.phase is GamePhase.FINISHED


def test_best_friend_chooses_revenge_target_after_execution() -> None:
    engine = make_engine()
    session = GameSession(chat_id=-100, created_by=1, phase=GamePhase.VOTING)
    session.players = {
        1: player(1, RoleKey.BEST_FRIEND),
        2: player(2, RoleKey.MAFIA_BOSS),
        3: player(3, RoleKey.CIVILIAN),
        4: player(4, RoleKey.DOCTOR),
    }
    session.day_votes = {2: 1, 3: 1, 4: 1}

    vote_result = engine.resolve_day_vote(session)

    assert vote_result.pending_revenge_by == 1
    assert session.phase is GamePhase.VERDICT

    revenge_result = engine.resolve_revenge(session, 1, 2)

    assert revenge_result.revenge_user_id == 2
    assert not session.players[2].alive
    assert session.phase is GamePhase.FINISHED
