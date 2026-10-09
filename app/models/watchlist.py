import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.film import Film
    from app.models.user import User


class Watchlist(Base):
    """
    SQLAlchemy 2.0 ORM model for Watchlist.
    Represents User <-> Film many-to-many relationship.
    """

    __tablename__ = "watchlist"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # Foreign Keys referencing User and Film tables
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    film_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("films.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Database-generated created_at timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships: Watchlist -> User, Watchlist -> Film
    user: Mapped["User"] = relationship("User", back_populates="watchlist")
    film: Mapped["Film"] = relationship("Film", back_populates="watchlist")

    # Prevent duplicate entries for the same user and film
    __table_args__ = (UniqueConstraint("user_id", "film_id", name="uq_user_film_watchlist"),)
