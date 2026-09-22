from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class GamePhase(StrEnum):
    LOBBY = "lobby"
    ASSIGNING = "assigning"
    NIGHT = "night"
    DAWN = "dawn"
    DISCUSSION = "discussion"
    VOTING = "voting"
    VERDICT = "verdict"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class Faction(StrEnum):
    TOWN = "town"
    MAFIA = "mafia"
    NEUTRAL = "neutral"


class RoleKey(StrEnum):
    CIVILIAN = "civilian"
    MAFIA_BOSS = "mafia_boss"
    MAFIA = "mafia"
    COMMISSIONER = "commissioner"
    WARRANT_OFFICER = "warrant_officer"
    DOCTOR = "doctor"
    MANIAC = "maniac"
    SNOW_WHITE = "snow_white"
    LAWYER = "lawyer"
    SUICIDE = "suicide"
    HOMELESS = "homeless"
    LUCKY = "lucky"
    BEST_FRIEND = "best_friend"


class ActionType(StrEnum):
    MAFIA_VOTE = "mafia_vote"
    INSPECT = "inspect"
    COMMISSIONER_SHOT = "commissioner_shot"
    HEAL = "heal"
    MANIAC_KILL = "maniac_kill"
    BLOCK = "block"
    ADVOCATE_PROTECT = "advocate_protect"
    WATCH = "watch"
    REVENGE = "revenge"


@dataclass(slots=True)
class GamePlayer:
    user_id: int
    display_name: str
    username: str | None = None
    role: RoleKey | None = None
    alive: bool = True
    ready: bool = False
    joined_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    missed_nights: int = 0
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NightAction:
    actor_id: int
    target_id: int
    action_type: ActionType
    phase_number: int


@dataclass(slots=True)
class ResolutionResult:
    deaths: set[int] = field(default_factory=set)
    saved: set[int] = field(default_factory=set)
    blocked: set[int] = field(default_factory=set)
    investigations: dict[int, RoleKey] = field(default_factory=dict)
    witnesses: dict[int, list[int]] = field(default_factory=dict)
    role_changes: dict[int, RoleKey] = field(default_factory=dict)
    public_events: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DayResolutionResult:
    lynched_user_id: int | None = None
    revenge_user_id: int | None = None
    tied_candidates: set[int] = field(default_factory=set)
    pending_revenge_by: int | None = None
    role_changes: dict[int, RoleKey] = field(default_factory=dict)
    public_events: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GameSession:
    chat_id: int
    created_by: int
    game_id: UUID = field(default_factory=uuid4)
    phase: GamePhase = GamePhase.LOBBY
    phase_number: int = 0
    players: dict[int, GamePlayer] = field(default_factory=dict)
    night_actions: dict[int, NightAction] = field(default_factory=dict)
    day_votes: dict[int, int | None] = field(default_factory=dict)
    day_blocked: set[int] = field(default_factory=set)
    advocate_ward_id: int | None = None
    pending_revenge_by: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    winner: Faction | RoleKey | None = None
    phase_deadline: datetime | None = None
    main_message_id: int | None = None
    main_message_text: str | None = None
    original_chat_permissions: dict[str, bool | None] | None = None
    original_player_permissions: dict[int, dict[str, bool | int | None]] = field(
        default_factory=dict
    )

    @property
    def alive_players(self) -> list[GamePlayer]:
        return [player for player in self.players.values() if player.alive]

    @property
    def callback_token(self) -> str:
        """Compact game identifier that safely fits Telegram callback data."""
        return self.game_id.hex[:10]

    def require_player(self, user_id: int) -> GamePlayer:
        try:
            return self.players[user_id]
        except KeyError as error:
            raise ValueError("Игрок не участвует в этой партии") from error


@dataclass(frozen=True, slots=True)
class WinResult:
    finished: bool
    winner: Faction | RoleKey | None = None
    reason: str = ""
