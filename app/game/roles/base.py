from dataclasses import dataclass

from app.game.models import ActionType, Faction, RoleKey


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    key: RoleKey
    name: str
    faction: Faction
    description: str
    night_actions: tuple[ActionType, ...] = ()
