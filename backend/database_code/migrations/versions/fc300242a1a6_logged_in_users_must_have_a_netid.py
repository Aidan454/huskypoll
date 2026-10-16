"""logged-in users must have a netid

Revision ID: fc300242a1a6
Revises: 86019a53103a
Create Date: 2026-10-08 21:23:57.788538

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fc300242a1a6'
down_revision: Union[str, Sequence[str], None] = '86019a53103a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Anyone who has logged in must have a NetID (roster-only rows may still lack one)."""
    conn = op.get_bind()
    bad = conn.execute(sa.text(
        "SELECT id, email FROM users WHERE last_login_at IS NOT NULL AND net_id IS NULL"
    )).fetchall()
    if bad:
        listing = ", ".join(f"user {i} ({e})" for i, e in bad[:20])
        raise RuntimeError(
            f"{len(bad)} logged-in user(s) have no NetID, so the rule can't be added: {listing}. "
            "Set their net_id, or for a demo database delete it and run seed-demo again."
        )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_check_constraint("logged_in_has_net_id", "last_login_at IS NULL OR net_id IS NOT NULL")


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_users_logged_in_has_net_id"), type_="check")
