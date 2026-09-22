from app.config.settings import Settings


def test_railway_postgres_url_is_converted_for_async_sqlalchemy() -> None:
    settings = Settings(DATABASE_URL="postgresql://user:password@host:5432/database")

    assert settings.database_url == ("postgresql+asyncpg://user:password@host:5432/database")


def test_async_database_url_is_preserved() -> None:
    url = "postgresql+asyncpg://user:password@host:5432/database"

    settings = Settings(DATABASE_URL=url)

    assert settings.database_url == url


def test_default_bot_admin_is_the_configured_owner() -> None:
    settings = Settings(bot_token="test")

    assert settings.bot_admin_id == 1326779223
