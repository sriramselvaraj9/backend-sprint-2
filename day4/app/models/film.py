from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.review import Review
    from app.models.watchlist import Watchlist


class Film(Base):
    """
    SQLAlchemy 2.0 ORM model for Films.
    Represents movies available in the platform catalog.
    """
    __tablename__ = "films"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Core film attributes
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True) # "Letter I ➔ Inception ➔ Go directly to Row #42"t finds the record instantly.
    release_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    genre: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    director: Mapped[str] = mapped_column(String(255), nullable=False)

    # Database-generated created_at timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship: Film -> Reviews (film.reviews)
    reviews: Mapped[list["Review"]] = relationship(
        "Review",
        back_populates="film",
        cascade="all, delete-orphan",
    )

    # Relationship: Film -> Watchlist (film.watchlist)
    watchlist: Mapped[list["Watchlist"]] = relationship(
        "Watchlist",
        back_populates="film",
        cascade="all, delete-orphan",
    )
