from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class PlayerPreference(Base):
    __tablename__ = "player_preferences"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    game_name: Mapped[str] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
