"""convert_ids_to_uuid

Revision ID: defbc8d4965b
Revises: 5f8de0fcfe30

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "defbc8d4965b"
down_revision: str | Sequence[str] | None = "5f8de0fcfe30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema to use UUID for all primary and foreign keys."""
    # Drop existing tables with integer primary keys in reverse dependency order
    op.execute("DROP TABLE IF EXISTS watchlist CASCADE")
    op.execute("DROP TABLE IF EXISTS reviews CASCADE")
    op.execute("DROP TABLE IF EXISTS films CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")

    # 1. Recreate users with UUID primary key
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=20), server_default="user", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    # 2. Recreate films with UUID primary key
    op.create_table(
        "films",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("release_year", sa.Integer(), nullable=False),
        sa.Column("genre", sa.String(length=100), nullable=False),
        sa.Column("director", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_films_genre"), "films", ["genre"], unique=False)
    op.create_index(op.f("ix_films_release_year"), "films", ["release_year"], unique=False)
    op.create_index(op.f("ix_films_title"), "films", ["title"], unique=False)

    # 3. Recreate reviews with UUID primary key & foreign keys
    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("film_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["film_id"], ["films.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reviews_film_id"), "reviews", ["film_id"], unique=False)
    op.create_index(op.f("ix_reviews_user_id"), "reviews", ["user_id"], unique=False)

    # 4. Recreate watchlist with UUID primary key & foreign keys
    op.create_table(
        "watchlist",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("film_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["film_id"], ["films.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "film_id", name="uq_user_film_watchlist"),
    )
    op.create_index(op.f("ix_watchlist_film_id"), "watchlist", ["film_id"], unique=False)
    op.create_index(op.f("ix_watchlist_user_id"), "watchlist", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("watchlist")
    op.drop_table("reviews")
    op.drop_table("films")
    op.drop_table("users")
