"""fix participation points at one

Revision ID: c4d5e6f7a8b9
Revises: bc67e89ee1e2
Create Date: 2026-10-26 12:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: str | Sequence[str] | None = 'bc67e89ee1e2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Every poll is now worth a fixed 1 point for answering."""
    op.execute("UPDATE courses SET points_participation = 1")


def downgrade() -> None:
    """The old per-course values cannot be restored."""
