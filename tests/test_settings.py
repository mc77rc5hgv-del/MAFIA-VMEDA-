from app.config.settings import Settings


def test_railway_postgres_url_is_converted_for_async_sqlalchemy() -> None:
    settings = Settings(DATABASE_URL="postgresql://user:password@host:5432/database")

    assert settings.database_url == ("postgresql+asyncpg://user:password@host:5432/database")


def test_async_database_url_is_preserved() -> None:
    url = "postgresql+asyncpg://user:password@host:5432/database"

    settings = Settings(DATABASE_URL=url)

    assert settings.database_url == url
