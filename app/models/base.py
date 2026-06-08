from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func


def _utcnow() -> datetime:
    """Return timezone-aware UTC now. Used as the onupdate callable."""
    return datetime.now(timezone.utc)


class TimestampMixin:
    """
    Adds created_at and updated_at to any SQLAlchemy model.
    onupdate=_utcnow is a Python callable — works on both MySQL and SQLite.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=_utcnow,
        nullable=False,
    )