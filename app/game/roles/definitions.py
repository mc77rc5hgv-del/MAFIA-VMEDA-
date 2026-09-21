from pathlib import Path

import yaml

from app.game.models import ActionType, Faction, RoleKey
from app.game.roles.base import RoleDefinition

_ROLE_TEXTS = yaml.safe_load(
    (Path(__file__).parents[2] / "config" / "role_texts.yaml").read_text(encoding="utf-8")
)


def _name(role: RoleKey) -> str:
    return str(_ROLE_TEXTS[role.value]["name"])


def _description(role: RoleKey) -> str:
    return str(_ROLE_TEXTS[role.value]["description"])


ROLE_DEFINITIONS: dict[RoleKey, RoleDefinition] = {
    RoleKey.CIVILIAN: RoleDefinition(
        RoleKey.CIVILIAN,
        _name(RoleKey.CIVILIAN),
        Faction.TOWN,
        _description(RoleKey.CIVILIAN),
    ),
    RoleKey.MAFIA_BOSS: RoleDefinition(
        RoleKey.MAFIA_BOSS,
        _name(RoleKey.MAFIA_BOSS),
        Faction.MAFIA,
        _description(RoleKey.MAFIA_BOSS),
        (ActionType.MAFIA_VOTE,),
    ),
    RoleKey.MAFIA: RoleDefinition(
        RoleKey.MAFIA,
        _name(RoleKey.MAFIA),
        Faction.MAFIA,
        _description(RoleKey.MAFIA),
        (ActionType.MAFIA_VOTE,),
    ),
    RoleKey.COMMISSIONER: RoleDefinition(
        RoleKey.COMMISSIONER,
        _name(RoleKey.COMMISSIONER),
        Faction.TOWN,
        _description(RoleKey.COMMISSIONER),
        (ActionType.INSPECT, ActionType.COMMISSIONER_SHOT),
    ),
    RoleKey.WARRANT_OFFICER: RoleDefinition(
        RoleKey.WARRANT_OFFICER,
        _name(RoleKey.WARRANT_OFFICER),
        Faction.TOWN,
        _description(RoleKey.WARRANT_OFFICER),
    ),
    RoleKey.DOCTOR: RoleDefinition(
        RoleKey.DOCTOR,
        _name(RoleKey.DOCTOR),
        Faction.TOWN,
        _description(RoleKey.DOCTOR),
        (ActionType.HEAL,),
    ),
    RoleKey.MANIAC: RoleDefinition(
        RoleKey.MANIAC,
        _name(RoleKey.MANIAC),
        Faction.NEUTRAL,
        _description(RoleKey.MANIAC),
        (ActionType.MANIAC_KILL,),
    ),
    RoleKey.SNOW_WHITE: RoleDefinition(
        RoleKey.SNOW_WHITE,
        _name(RoleKey.SNOW_WHITE),
        Faction.TOWN,
        _description(RoleKey.SNOW_WHITE),
        (ActionType.BLOCK,),
    ),
    RoleKey.LAWYER: RoleDefinition(
        RoleKey.LAWYER,
        _name(RoleKey.LAWYER),
        Faction.MAFIA,
        _description(RoleKey.LAWYER),
    ),
    RoleKey.SUICIDE: RoleDefinition(
        RoleKey.SUICIDE,
        _name(RoleKey.SUICIDE),
        Faction.NEUTRAL,
        _description(RoleKey.SUICIDE),
    ),
    RoleKey.HOMELESS: RoleDefinition(
        RoleKey.HOMELESS,
        _name(RoleKey.HOMELESS),
        Faction.TOWN,
        _description(RoleKey.HOMELESS),
        (ActionType.WATCH,),
    ),
    RoleKey.LUCKY: RoleDefinition(
        RoleKey.LUCKY,
        _name(RoleKey.LUCKY),
        Faction.TOWN,
        _description(RoleKey.LUCKY),
    ),
    RoleKey.BEST_FRIEND: RoleDefinition(
        RoleKey.BEST_FRIEND,
        _name(RoleKey.BEST_FRIEND),
        Faction.TOWN,
        _description(RoleKey.BEST_FRIEND),
    ),
}


def get_role_definition(role: RoleKey) -> RoleDefinition:
    return ROLE_DEFINITIONS[role]
