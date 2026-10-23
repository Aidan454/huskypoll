"""netid must be 3 letters and 5 digits

Revision ID: 86019a53103a
Revises: 7d7350be1874
Create Date: 2026-10-08 21:18:54.124032

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '86019a53103a'
down_revision: str | Sequence[str] | None = '7d7350be1874'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NETID_GLOB = "[a-z][a-z][a-z][0-9][0-9][0-9][0-9][0-9]"  # copied, not imported


def upgrade() -> None:
    """Require users.net_id to be a UConn NetID: 3 letters + 5 digits (e.g. abc12345)."""
    conn = op.get_bind()
    # Lowercase/trim first; then refuse to continue if any NetID still doesn't fit,
    # listing them so they can be fixed (or the user removed) by hand.
    conn.execute(sa.text("UPDATE users SET net_id = lower(trim(net_id)) WHERE net_id IS NOT NULL"))
    bad = conn.execute(sa.text(
        f"SELECT id, net_id FROM users WHERE net_id IS NOT NULL AND net_id NOT GLOB '{NETID_GLOB}'"
    )).fetchall()
    if bad:
        listing = ", ".join(f"user {i}: '{n}'" for i, n in bad[:20])
        raise RuntimeError(
            f"{len(bad)} NetID(s) are not 3 letters + 5 digits, so the rule can't be added: {listing}. "
            "Fix them (UPDATE users SET net_id = ... WHERE id = ...) or, for a demo database, "
            "delete it and run seed-demo again."
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("net_id", existing_type=sa.VARCHAR(length=32),
                              type_=sa.String(length=8), existing_nullable=True)
        batch_op.drop_constraint(op.f("ck_users_net_id_lower"), type_="check")
        batch_op.create_check_constraint("net_id_format", f"net_id IS NULL OR net_id GLOB '{NETID_GLOB}'")


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_users_net_id_format"), type_="check")
        batch_op.create_check_constraint("net_id_lower", "net_id IS NULL OR net_id = lower(net_id)")
        batch_op.alter_column("net_id", existing_type=sa.String(length=8),
                              type_=sa.VARCHAR(length=32), existing_nullable=True)
