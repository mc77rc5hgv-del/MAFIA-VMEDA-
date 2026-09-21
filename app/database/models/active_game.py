from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import JSON, BigInteger, DateTime, Uuid
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class ActiveGame(Base):
    __tablename__ = "active_games"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    game_id: Mapped[UUID] = mapped_column(Uuid, unique=True, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(MutableDict.as_mutable(JSON))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
