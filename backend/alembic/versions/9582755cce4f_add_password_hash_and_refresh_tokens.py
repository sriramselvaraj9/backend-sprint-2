"""add_password_hash_and_refresh_tokens

Revision ID: 9582755cce4f
Revises: defbc8d4965b
Create Date: 2026-10-06 16:31:24.138316

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9582755cce4f"
down_revision: str | Sequence[str] | None = "defbc8d4965b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "password_hash",
            sa.String(length=255),
            server_default="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "password_hash")
