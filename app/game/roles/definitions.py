from app.game.models import ActionType, Faction, RoleKey
from app.game.roles.base import RoleDefinition

ROLE_DEFINITIONS: dict[RoleKey, RoleDefinition] = {
    RoleKey.CIVILIAN: RoleDefinition(
        RoleKey.CIVILIAN,
        "Гражданский",
        Faction.TOWN,
        "Днём обсуждает события и голосует против подозреваемых.",
    ),
    RoleKey.MAFIA_BOSS: RoleDefinition(
        RoleKey.MAFIA_BOSS,
        "Глава мафии",
        Faction.MAFIA,
        "Руководит коллективным ночным убийством мафии.",
        (ActionType.MAFIA_VOTE,),
    ),
    RoleKey.MAFIA: RoleDefinition(
        RoleKey.MAFIA,
        "Мафия",
        Faction.MAFIA,
        "Голосует за ночную жертву и наследует руководство после смерти главы.",
        (ActionType.MAFIA_VOTE,),
    ),
    RoleKey.COMMISSIONER: RoleDefinition(
        RoleKey.COMMISSIONER,
        "Комиссар",
        Faction.TOWN,
        "Ночью проверяет роль игрока или совершает выстрел.",
        (ActionType.INSPECT, ActionType.COMMISSIONER_SHOT),
    ),
    RoleKey.WARRANT_OFFICER: RoleDefinition(
        RoleKey.WARRANT_OFFICER,
        "Прапорщик",
        Faction.TOWN,
        "Получает проверки Комиссара и занимает его место после гибели.",
    ),
    RoleKey.DOCTOR: RoleDefinition(
        RoleKey.DOCTOR,
        "Дохтор",
        Faction.TOWN,
        "Лечит выбранного игрока; один раз за игру может вылечить себя.",
        (ActionType.HEAL,),
    ),
    RoleKey.MANIAC: RoleDefinition(
        RoleKey.MANIAC,
        "Маньяк",
        Faction.NEUTRAL,
        "Каждую ночь убивает одного игрока и побеждает в одиночку.",
        (ActionType.MANIAC_KILL,),
    ),
    RoleKey.SNOW_WHITE: RoleDefinition(
        RoleKey.SNOW_WHITE,
        "Белоснежка",
        Faction.TOWN,
        "Блокирует действие цели ночью и её активность следующим днём.",
        (ActionType.BLOCK,),
    ),
    RoleKey.LAWYER: RoleDefinition(
        RoleKey.LAWYER,
        "Адвокат",
        Faction.MAFIA,
        "Автоматически скрывает случайного подопечного от проверки Комиссара.",
    ),
    RoleKey.SUICIDE: RoleDefinition(
        RoleKey.SUICIDE,
        "Самоубийца",
        Faction.NEUTRAL,
        "Побеждает, если его казнят на дневном голосовании.",
    ),
    RoleKey.HOMELESS: RoleDefinition(
        RoleKey.HOMELESS,
        "Бомж",
        Faction.TOWN,
        "Наблюдает за целью и видит её ночных посетителей.",
        (ActionType.WATCH,),
    ),
    RoleKey.LUCKY: RoleDefinition(
        RoleKey.LUCKY,
        "Счастливчик",
        Faction.TOWN,
        "Имеет шанс пережить ночное покушение.",
    ),
    RoleKey.BEST_FRIEND: RoleDefinition(
        RoleKey.BEST_FRIEND,
        "Лучший друг",
        Faction.TOWN,
        "После собственной дневной казни забирает с собой выбранного игрока.",
    ),
}


def get_role_definition(role: RoleKey) -> RoleDefinition:
    return ROLE_DEFINITIONS[role]
