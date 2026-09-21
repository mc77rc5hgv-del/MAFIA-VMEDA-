from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.game.models import (
    ActionType,
    Faction,
    GamePhase,
    GamePlayer,
    GameSession,
    NightAction,
    RoleKey,
)


def session_to_dict(session: GameSession) -> dict[str, Any]:
    winner_type: str | None = None
    winner_value: str | None = None
    if isinstance(session.winner, Faction):
        winner_type = "faction"
        winner_value = session.winner.value
    elif isinstance(session.winner, RoleKey):
        winner_type = "role"
        winner_value = session.winner.value

    return {
        "game_id": str(session.game_id),
        "chat_id": session.chat_id,
        "created_by": session.created_by,
        "phase": session.phase.value,
        "phase_number": session.phase_number,
        "players": [
            {
                "user_id": player.user_id,
                "display_name": player.display_name,
                "username": player.username,
                "role": player.role.value if player.role is not None else None,
                "alive": player.alive,
                "ready": player.ready,
                "joined_at": player.joined_at.isoformat(),
                "missed_nights": player.missed_nights,
                "metadata": player.metadata,
            }
            for player in session.players.values()
        ],
        "night_actions": [
            {
                "actor_id": action.actor_id,
                "target_id": action.target_id,
                "action_type": action.action_type.value,
                "phase_number": action.phase_number,
            }
            for action in session.night_actions.values()
        ],
        "day_votes": {str(user_id): target_id for user_id, target_id in session.day_votes.items()},
        "day_blocked": list(session.day_blocked),
        "advocate_ward_id": session.advocate_ward_id,
        "pending_revenge_by": session.pending_revenge_by,
        "created_at": session.created_at.isoformat(),
        "started_at": _datetime_value(session.started_at),
        "finished_at": _datetime_value(session.finished_at),
        "winner_type": winner_type,
        "winner_value": winner_value,
        "phase_deadline": _datetime_value(session.phase_deadline),
        "main_message_id": session.main_message_id,
    }


def session_from_dict(data: dict[str, Any]) -> GameSession:
    players = {
        int(item["user_id"]): GamePlayer(
            user_id=int(item["user_id"]),
            display_name=str(item["display_name"]),
            username=item.get("username"),
            role=RoleKey(item["role"]) if item.get("role") else None,
            alive=bool(item.get("alive", True)),
            ready=bool(item.get("ready", False)),
            joined_at=datetime.fromisoformat(item["joined_at"]),
            missed_nights=int(item.get("missed_nights", 0)),
            metadata=dict(item.get("metadata", {})),
        )
        for item in data.get("players", [])
    }
    actions = {
        int(item["actor_id"]): NightAction(
            actor_id=int(item["actor_id"]),
            target_id=int(item["target_id"]),
            action_type=ActionType(item["action_type"]),
            phase_number=int(item["phase_number"]),
        )
        for item in data.get("night_actions", [])
    }
    winner: Faction | RoleKey | None = None
    if data.get("winner_type") == "faction":
        winner = Faction(data["winner_value"])
    elif data.get("winner_type") == "role":
        winner = RoleKey(data["winner_value"])

    return GameSession(
        game_id=UUID(data["game_id"]),
        chat_id=int(data["chat_id"]),
        created_by=int(data["created_by"]),
        phase=GamePhase(data["phase"]),
        phase_number=int(data.get("phase_number", 0)),
        players=players,
        night_actions=actions,
        day_votes={int(key): value for key, value in data.get("day_votes", {}).items()},
        day_blocked={int(user_id) for user_id in data.get("day_blocked", [])},
        advocate_ward_id=data.get("advocate_ward_id"),
        pending_revenge_by=data.get("pending_revenge_by"),
        created_at=datetime.fromisoformat(data["created_at"]),
        started_at=_parse_datetime(data.get("started_at")),
        finished_at=_parse_datetime(data.get("finished_at")),
        winner=winner,
        phase_deadline=_parse_datetime(data.get("phase_deadline")),
        main_message_id=data.get("main_message_id"),
    )


def _datetime_value(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
