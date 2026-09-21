import random

from app.game.action_resolver import ActionResolver
from app.game.models import (
    ActionType,
    GamePhase,
    GamePlayer,
    GameSession,
    NightAction,
    RoleKey,
)


def player(user_id: int, role: RoleKey) -> GamePlayer:
    return GamePlayer(user_id=user_id, display_name=str(user_id), role=role)


def test_doctor_saves_single_attack_target() -> None:
    session = GameSession(chat_id=-100, created_by=1, phase=GamePhase.NIGHT, phase_number=1)
    session.players = {
        1: player(1, RoleKey.MAFIA_BOSS),
        2: player(2, RoleKey.DOCTOR),
        3: player(3, RoleKey.CIVILIAN),
        4: player(4, RoleKey.COMMISSIONER),
    }
    session.night_actions = {
        1: NightAction(1, 3, ActionType.MAFIA_VOTE, 1),
        2: NightAction(2, 3, ActionType.HEAL, 1),
    }

    result = ActionResolver(rng=random.Random(1)).resolve(session)

    assert result.deaths == set()
    assert result.saved == {3}
    assert session.players[3].alive


def test_blocked_actor_action_is_ignored() -> None:
    session = GameSession(chat_id=-100, created_by=1, phase=GamePhase.NIGHT, phase_number=2)
    session.players = {
        1: player(1, RoleKey.MANIAC),
        2: player(2, RoleKey.SNOW_WHITE),
        3: player(3, RoleKey.CIVILIAN),
        4: player(4, RoleKey.MAFIA_BOSS),
    }
    session.night_actions = {
        1: NightAction(1, 3, ActionType.MANIAC_KILL, 2),
        2: NightAction(2, 1, ActionType.BLOCK, 2),
    }

    result = ActionResolver(rng=random.Random(1)).resolve(session)

    assert result.blocked == {1}
    assert result.deaths == set()


def test_advocate_masks_inspection() -> None:
    session = GameSession(chat_id=-100, created_by=1, phase=GamePhase.NIGHT, phase_number=1)
    session.players = {
        1: player(1, RoleKey.COMMISSIONER),
        2: player(2, RoleKey.LAWYER),
        3: player(3, RoleKey.MAFIA_BOSS),
        4: player(4, RoleKey.CIVILIAN),
    }
    session.advocate_ward_id = 3
    session.night_actions = {1: NightAction(1, 3, ActionType.INSPECT, 1)}

    result = ActionResolver(rng=random.Random(1)).resolve(session)

    assert result.investigations[1] is RoleKey.CIVILIAN


def test_mafia_boss_breaks_tied_mafia_vote() -> None:
    session = GameSession(chat_id=-100, created_by=1, phase=GamePhase.NIGHT, phase_number=1)
    session.players = {
        1: player(1, RoleKey.MAFIA_BOSS),
        2: player(2, RoleKey.MAFIA),
        3: player(3, RoleKey.CIVILIAN),
        4: player(4, RoleKey.DOCTOR),
    }
    session.night_actions = {
        1: NightAction(1, 4, ActionType.MAFIA_VOTE, 1),
        2: NightAction(2, 3, ActionType.MAFIA_VOTE, 1),
    }

    result = ActionResolver(rng=random.Random(1)).resolve(session)

    assert result.deaths == {4}
