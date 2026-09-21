from app.game.models import GamePhase, GameSession


class InvalidPhaseTransition(ValueError):
    pass


ALLOWED_TRANSITIONS: dict[GamePhase, set[GamePhase]] = {
    GamePhase.LOBBY: {GamePhase.ASSIGNING, GamePhase.CANCELLED},
    GamePhase.ASSIGNING: {GamePhase.NIGHT, GamePhase.CANCELLED},
    GamePhase.NIGHT: {GamePhase.DAWN, GamePhase.CANCELLED},
    GamePhase.DAWN: {GamePhase.DISCUSSION, GamePhase.FINISHED, GamePhase.CANCELLED},
    GamePhase.DISCUSSION: {GamePhase.VOTING, GamePhase.CANCELLED},
    GamePhase.VOTING: {GamePhase.VERDICT, GamePhase.NIGHT, GamePhase.CANCELLED},
    GamePhase.VERDICT: {GamePhase.NIGHT, GamePhase.FINISHED, GamePhase.CANCELLED},
    GamePhase.FINISHED: set(),
    GamePhase.CANCELLED: set(),
}


class GameStateMachine:
    def transition(self, session: GameSession, target: GamePhase) -> None:
        if target not in ALLOWED_TRANSITIONS[session.phase]:
            raise InvalidPhaseTransition(
                f"Переход {session.phase.value} -> {target.value} запрещён"
            )
        session.phase = target
        if target is GamePhase.NIGHT:
            session.phase_number += 1
            session.night_actions.clear()
            session.day_votes.clear()
            session.day_blocked.clear()
            session.pending_revenge_by = None
