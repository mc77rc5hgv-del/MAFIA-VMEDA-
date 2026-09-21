from app.game.models import RoleKey
from app.game.roles import ROLE_DEFINITIONS


def roles_text() -> str:
    lines = ["🎭 <b>Роли Мафии ВМедА</b>"]
    for role in RoleKey:
        definition = ROLE_DEFINITIONS[role]
        lines.append(f"\n<b>{definition.name}</b> — {definition.description}")
    return "\n".join(lines)
