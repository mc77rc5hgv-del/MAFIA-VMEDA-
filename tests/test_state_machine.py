import pytest

from app.game.models import GamePhase, GameSession
from app.game.state_machine import GameStateMachine, InvalidPhaseTransition


def test_valid_start_transition_increments_night_number() -> None:
    session = GameSession(chat_id=-100, created_by=1)
    machine = GameStateMachine()

    machine.transition(session, GamePhase.ASSIGNING)
    machine.transition(session, GamePhase.NIGHT)

    assert session.phase is GamePhase.NIGHT
    assert session.phase_number == 1


def test_invalid_transition_is_rejected() -> None:
    session = GameSession(chat_id=-100, created_by=1)
    with pytest.raises(InvalidPhaseTransition):
        GameStateMachine().transition(session, GamePhase.VOTING)
