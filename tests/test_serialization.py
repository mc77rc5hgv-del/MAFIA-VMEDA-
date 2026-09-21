from datetime import UTC, datetime, timedelta

from app.game.models import (
    ActionType,
    GamePhase,
    GamePlayer,
    GameSession,
    NightAction,
    RoleKey,
)
from app.game.serialization import session_from_dict, session_to_dict


def test_active_game_snapshot_round_trip() -> None:
    deadline = datetime.now(UTC) + timedelta(seconds=45)
    game = GameSession(
        chat_id=-1001234567890,
        created_by=10,
        phase=GamePhase.NIGHT,
        phase_number=3,
        phase_deadline=deadline,
        main_message_id=555,
    )
    game.players = {
        10: GamePlayer(10, "Курсант", role=RoleKey.DOCTOR, ready=True),
        20: GamePlayer(20, "Начальник", role=RoleKey.MAFIA_BOSS),
    }
    game.night_actions[10] = NightAction(10, 20, ActionType.HEAL, 3)
    game.day_blocked = {20}

    restored = session_from_dict(session_to_dict(game))

    assert restored.game_id == game.game_id
    assert restored.phase is GamePhase.NIGHT
    assert restored.phase_deadline == deadline
    assert restored.main_message_id == 555
    assert restored.players[10].ready is True
    assert restored.players[10].role is RoleKey.DOCTOR
    assert restored.night_actions[10].action_type is ActionType.HEAL
    assert restored.day_blocked == {20}
