from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    bot_token: str = Field(default="", validation_alias="BOT_TOKEN")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./mafia_vmeda.db",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    bot_admin_id: int = Field(default=1326779223, validation_alias="BOT_ADMIN_ID")
    min_players: int = Field(default=4, ge=4, validation_alias="MIN_PLAYERS")
    max_players: int = Field(default=50, ge=4, le=50, validation_alias="MAX_PLAYERS")
    night_seconds: int = Field(default=60, ge=10, validation_alias="NIGHT_SECONDS")
    discussion_seconds: int = Field(default=120, ge=10, validation_alias="DISCUSSION_SECONDS")
    voting_seconds: int = Field(default=60, ge=10, validation_alias="VOTING_SECONDS")
    verdict_seconds: int = Field(default=30, ge=5, validation_alias="VERDICT_SECONDS")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        return value

    @property
    def config_dir(self) -> Path:
        return Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
