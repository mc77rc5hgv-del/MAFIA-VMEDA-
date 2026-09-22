from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models import PlayerPreference


class PlayerNameStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def get(self, telegram_id: int) -> str | None:
        async with self.session_factory() as database:
            preference = await database.get(PlayerPreference, telegram_id)
            return preference.game_name if preference is not None else None

    async def set(self, telegram_id: int, game_name: str) -> None:
        async with self.session_factory() as database:
            preference = await database.get(PlayerPreference, telegram_id)
            if preference is None:
                database.add(PlayerPreference(telegram_id=telegram_id, game_name=game_name))
            else:
                preference.game_name = game_name
                preference.updated_at = datetime.now(UTC)
            await database.commit()


def normalize_game_name(value: str) -> str:
    name = " ".join(value.split())
    if not 2 <= len(name) <= 32:
        raise ValueError("Имя должно содержать от 2 до 32 символов.")
    if name.startswith("/"):
        raise ValueError("Имя не должно начинаться с команды.")
    return name


def unique_game_name(name: str, user_id: int, existing_names: list[str]) -> str:
    occupied = {item.casefold() for item in existing_names}
    if name.casefold() not in occupied:
        return name
    suffix = str(user_id)[-4:]
    base = name[: max(2, 32 - len(suffix) - 3)].rstrip()
    return f"{base} · {suffix}"
