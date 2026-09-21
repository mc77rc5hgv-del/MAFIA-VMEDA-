from __future__ import annotations

import random
from collections import Counter, defaultdict

from app.game.models import (
    ActionType,
    GameSession,
    NightAction,
    ResolutionResult,
    RoleKey,
)
from app.game.roles import get_role_definition


class ActionResolver:
    """Resolves all night actions as one deterministic game step."""

    def __init__(
        self,
        lucky_survival_chance: float = 0.35,
        rng: random.Random | None = None,
    ) -> None:
        self.lucky_survival_chance = lucky_survival_chance
        self.rng = rng or random.SystemRandom()

    def resolve(self, session: GameSession) -> ResolutionResult:
        result = ResolutionResult()
        actions = [
            action
            for action in session.night_actions.values()
            if self._valid_action(session, action)
        ]

        result.blocked = {
            action.target_id for action in actions if action.action_type is ActionType.BLOCK
        }
        active_actions = [action for action in actions if action.actor_id not in result.blocked]

        protected: set[int] = set()
        if session.advocate_ward_id is not None:
            lawyer = next(
                (
                    player
                    for player in session.alive_players
                    if player.role is RoleKey.LAWYER and player.user_id not in result.blocked
                ),
                None,
            )
            if lawyer is not None:
                protected.add(session.advocate_ward_id)
        healed = {
            action.target_id for action in active_actions if action.action_type is ActionType.HEAL
        }

        visits: dict[int, list[int]] = defaultdict(list)
        for action in active_actions:
            visits[action.target_id].append(action.actor_id)
            if action.action_type is ActionType.HEAL and action.actor_id == action.target_id:
                session.require_player(action.actor_id).metadata["self_heal_used"] = True

        mafia_target = self._mafia_target(session, active_actions)
        attacks: list[int] = []
        if mafia_target is not None:
            attacks.append(mafia_target)
        attacks.extend(
            action.target_id
            for action in active_actions
            if action.action_type in {ActionType.MANIAC_KILL, ActionType.COMMISSIONER_SHOT}
        )

        attack_counts = Counter(attacks)
        for target_id, count in attack_counts.items():
            target = session.require_player(target_id)
            if target_id in healed and count == 1:
                result.saved.add(target_id)
                continue
            if target.role is RoleKey.LUCKY and self.rng.random() < self.lucky_survival_chance:
                result.saved.add(target_id)
                continue
            result.deaths.add(target_id)

        for action in active_actions:
            if action.action_type is ActionType.INSPECT:
                target = session.require_player(action.target_id)
                shown_role = target.role or RoleKey.CIVILIAN
                if action.target_id in protected:
                    shown_role = RoleKey.CIVILIAN
                result.investigations[action.actor_id] = shown_role
            elif action.action_type is ActionType.WATCH:
                result.witnesses[action.actor_id] = [
                    visitor_id
                    for visitor_id in visits[action.target_id]
                    if visitor_id != action.actor_id
                ]

        for user_id in result.deaths:
            session.require_player(user_id).alive = False

        if result.deaths:
            names = ", ".join(
                session.require_player(user_id).display_name for user_id in result.deaths
            )
            result.public_events.append(f"Ночью погибли: {names}")
        else:
            result.public_events.append("Этой ночью никто не погиб.")
        return result

    @staticmethod
    def _mafia_target(session: GameSession, actions: list[NightAction]) -> int | None:
        mafia_votes = [action for action in actions if action.action_type is ActionType.MAFIA_VOTE]
        votes = Counter(action.target_id for action in mafia_votes)
        if not votes:
            return None
        highest = max(votes.values())
        candidates = {target for target, count in votes.items() if count == highest}
        boss_vote = next(
            (
                action.target_id
                for action in mafia_votes
                if session.require_player(action.actor_id).role is RoleKey.MAFIA_BOSS
            ),
            None,
        )
        if boss_vote in candidates:
            return boss_vote
        return min(candidates)

    @staticmethod
    def _valid_action(session: GameSession, action: NightAction) -> bool:
        if action.phase_number != session.phase_number:
            return False
        actor = session.players.get(action.actor_id)
        target = session.players.get(action.target_id)
        if (
            actor is None
            or target is None
            or not actor.alive
            or not target.alive
            or actor.role is None
        ):
            return False
        return action.action_type in get_role_definition(actor.role).night_actions
