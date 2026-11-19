import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.film import Film
    from app.models.user import User


class Review(Base):
    """
    SQLAlchemy 2.0 ORM model for Reviews.
    References both Film and User via ForeignKeys.
    """

    __tablename__ = "reviews"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # Foreign Keys referencing Film and User tables
    film_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("films.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Review content
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Database-generated created_at timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships: Review -> Film, Review -> User
    film: Mapped["Film"] = relationship("Film", back_populates="reviews")
    user: Mapped["User"] = relationship("User", back_populates="reviews")
