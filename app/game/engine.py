from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from app.game.action_resolver import ActionResolver
from app.game.models import (
    ActionType,
    DayResolutionResult,
    Faction,
    GamePhase,
    GamePlayer,
    GameSession,
    NightAction,
    ResolutionResult,
    RoleKey,
)
from app.game.role_allocator import RoleAllocator
from app.game.state_machine import GameStateMachine
from app.game.win_checker import WinChecker


class GameEngine:
    def __init__(
        self,
        allocator: RoleAllocator,
        resolver: ActionResolver | None = None,
        win_checker: WinChecker | None = None,
        state_machine: GameStateMachine | None = None,
    ) -> None:
        self.allocator = allocator
        self.resolver = resolver or ActionResolver()
        self.win_checker = win_checker or WinChecker()
        self.state_machine = state_machine or GameStateMachine()

    def add_player(self, session: GameSession, player: GamePlayer) -> None:
        if session.phase is not GamePhase.LOBBY:
            raise ValueError("Регистрация уже завершена")
        if player.user_id in session.players:
            raise ValueError("Игрок уже зарегистрирован")
        if len(session.players) >= self.allocator.config.max_players:
            raise ValueError("Достигнут лимит игроков")
        session.players[player.user_id] = player

    def remove_player(self, session: GameSession, user_id: int) -> None:
        if session.phase is not GamePhase.LOBBY:
            raise ValueError("После старта партии обычный выход недоступен")
        if user_id not in session.players:
            raise ValueError("Игрок не зарегистрирован")
        del session.players[user_id]

    def start(self, session: GameSession) -> dict[int, RoleKey]:
        assignments = self.allocator.assign(list(session.players))
        self.state_machine.transition(session, GamePhase.ASSIGNING)
        for user_id, role in assignments.items():
            session.players[user_id].role = role
            session.players[user_id].metadata["starting_role"] = role.value
        lawyer_id = next(
            (user_id for user_id, role in assignments.items() if role is RoleKey.LAWYER),
            None,
        )
        if lawyer_id is not None:
            possible_wards = [user_id for user_id in session.players if user_id != lawyer_id]
            session.advocate_ward_id = self.allocator.rng.choice(possible_wards)
            session.players[lawyer_id].metadata["ward_id"] = session.advocate_ward_id
        session.started_at = datetime.now(UTC)
        self.state_machine.transition(session, GamePhase.NIGHT)
        return assignments

    def submit_night_action(self, session: GameSession, action: NightAction) -> None:
        if session.phase is not GamePhase.NIGHT:
            raise ValueError("Сейчас не ночь")
        if action.phase_number != session.phase_number:
            raise ValueError("Кнопка относится к завершённой фазе")
        actor = session.require_player(action.actor_id)
        target = session.require_player(action.target_id)
        if not actor.alive:
            raise ValueError("Погибший игрок не может действовать")
        if not target.alive:
            raise ValueError("Нельзя выбрать погибшего игрока")
        if actor.role is None:
            raise ValueError("Роль игрока не назначена")
        from app.game.roles import get_role_definition

        if action.action_type not in get_role_definition(actor.role).night_actions:
            raise ValueError("Эта способность недоступна вашей роли")
        if action.actor_id == action.target_id:
            if action.action_type is not ActionType.HEAL:
                raise ValueError("Этой способностью нельзя выбрать себя")
            if actor.metadata.get("self_heal_used"):
                raise ValueError("Самолечение уже использовано")
        if action.action_type is ActionType.MAFIA_VOTE:
            target_role = target.role
            target_is_mafia = (
                target_role is not None
                and get_role_definition(target_role).faction is Faction.MAFIA
            )
            if target_is_mafia:
                raise ValueError("Мафия не может выбрать своего участника")
        session.night_actions[action.actor_id] = action

    def resolve_night(self, session: GameSession) -> ResolutionResult:
        if session.phase is not GamePhase.NIGHT:
            raise ValueError("Нельзя рассчитать ночь вне ночной фазы")
        result = self.resolver.resolve(session)
        session.day_blocked = set(result.blocked)
        result.role_changes.update(self._apply_inheritance(session))
        self.state_machine.transition(session, GamePhase.DAWN)
        win = self.win_checker.check(session)
        if win.finished:
            session.winner = win.winner
            session.finished_at = datetime.now(UTC)
            self.state_machine.transition(session, GamePhase.FINISHED)
        else:
            self.state_machine.transition(session, GamePhase.DISCUSSION)
        return result

    def start_voting(self, session: GameSession) -> None:
        if session.phase is not GamePhase.DISCUSSION:
            raise ValueError("Голосование можно начать только после обсуждения")
        self.state_machine.transition(session, GamePhase.VOTING)

    def submit_day_vote(
        self,
        session: GameSession,
        voter_id: int,
        target_id: int | None,
    ) -> None:
        if session.phase is not GamePhase.VOTING:
            raise ValueError("Сейчас дневное голосование не проводится")
        voter = session.require_player(voter_id)
        if not voter.alive:
            raise ValueError("Погибший игрок не может голосовать")
        if voter_id in session.day_blocked:
            raise ValueError("Белоснежка лишила вас дневной активности")
        if target_id is not None:
            target = session.require_player(target_id)
            if not target.alive:
                raise ValueError("Нельзя голосовать против погибшего игрока")
        session.day_votes[voter_id] = target_id

    def resolve_day_vote(self, session: GameSession) -> DayResolutionResult:
        if session.phase is not GamePhase.VOTING:
            raise ValueError("Нельзя завершить голосование вне дневной фазы")
        result = DayResolutionResult()
        self.state_machine.transition(session, GamePhase.VERDICT)

        counts = Counter(target for target in session.day_votes.values() if target is not None)
        if not counts:
            result.public_events.append("Голосование завершилось без казни.")
            self._finish_verdict(session, result)
            return result

        highest = max(counts.values())
        leaders = {target for target, count in counts.items() if count == highest}
        if len(leaders) > 1:
            result.tied_candidates = leaders
            result.public_events.append("Голоса разделились поровну. Никто не казнён.")
            self._finish_verdict(session, result)
            return result

        lynched_id = leaders.pop()
        lynched = session.require_player(lynched_id)
        lynched.alive = False
        result.lynched_user_id = lynched_id
        result.public_events.append(f"Днём казнён: {lynched.display_name}")
        result.role_changes.update(self._apply_inheritance(session))

        if lynched.role is RoleKey.SUICIDE:
            self._finish_game(session, RoleKey.SUICIDE)
            return result
        if lynched.role is RoleKey.BEST_FRIEND:
            session.pending_revenge_by = lynched_id
            result.pending_revenge_by = lynched_id
            return result

        win = self.win_checker.check(session)
        if win.finished:
            self._finish_game(session, win.winner)
            return result
        self._finish_verdict(session, result)
        return result

    def resolve_revenge(
        self,
        session: GameSession,
        best_friend_id: int,
        target_id: int | None,
    ) -> DayResolutionResult:
        if session.phase is not GamePhase.VERDICT or session.pending_revenge_by != best_friend_id:
            raise ValueError("Сейчас выбор Лучшего друга не ожидается")
        result = DayResolutionResult(lynched_user_id=best_friend_id)
        if target_id is not None:
            target = session.require_player(target_id)
            if not target.alive:
                raise ValueError("Нельзя забрать с собой погибшего игрока")
            target.alive = False
            result.revenge_user_id = target_id
            result.public_events.append(f"Лучший друг забрал с собой игрока: {target.display_name}")
            result.role_changes.update(self._apply_inheritance(session))
        session.pending_revenge_by = None
        self._finish_verdict(session, result)
        return result

    def _finish_verdict(
        self,
        session: GameSession,
        result: DayResolutionResult,
    ) -> None:
        win = self.win_checker.check(session)
        if win.finished:
            self._finish_game(session, win.winner)
        else:
            self.state_machine.transition(session, GamePhase.NIGHT)

    def _finish_game(self, session: GameSession, winner: Faction | RoleKey | None) -> None:
        session.winner = winner
        session.finished_at = datetime.now(UTC)
        self.state_machine.transition(session, GamePhase.FINISHED)

    @staticmethod
    def _apply_inheritance(session: GameSession) -> dict[int, RoleKey]:
        changes: dict[int, RoleKey] = {}
        alive = session.alive_players
        if not any(player.role is RoleKey.MAFIA_BOSS for player in alive):
            successor = next(
                (
                    player
                    for player in sorted(alive, key=lambda item: item.user_id)
                    if player.role is RoleKey.MAFIA
                ),
                None,
            )
            if successor is not None:
                successor.role = RoleKey.MAFIA_BOSS
                changes[successor.user_id] = RoleKey.MAFIA_BOSS

        if not any(player.role is RoleKey.COMMISSIONER for player in alive):
            successor = next(
                (
                    player
                    for player in sorted(alive, key=lambda item: item.user_id)
                    if player.role is RoleKey.WARRANT_OFFICER
                ),
                None,
            )
            if successor is not None:
                successor.role = RoleKey.COMMISSIONER
                changes[successor.user_id] = RoleKey.COMMISSIONER
        return changes
