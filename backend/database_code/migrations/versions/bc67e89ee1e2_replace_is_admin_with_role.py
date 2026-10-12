"""replace is_admin with role

Revision ID: bc67e89ee1e2
Revises: fc300242a1a6
Create Date: 2026-10-12 09:35:24.398824

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc67e89ee1e2'
down_revision: Union[str, Sequence[str], None] = 'fc300242a1a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ROLES = "'admin', 'instructor', 'ta', 'student', 'guest'"  # copied, not imported


def upgrade() -> None:
    """users.is_admin (yes/no) -> users.role (admin / instructor / ta / student / guest).

    Existing accounts get the highest role their data supports: admins stay admins,
    course owners/instructors become instructors, TAs become TAs, anyone on a roster
    becomes a student, everyone else a guest.
    """
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("role", sa.String(length=16), nullable=False, server_default="guest"))

    op.execute("""
        UPDATE users SET role = CASE
            WHEN is_admin = 1 THEN 'admin'
            WHEN EXISTS (SELECT 1 FROM course_instructors ci
                         WHERE ci.user_id = users.id AND ci.role IN ('owner', 'instructor')) THEN 'instructor'
            WHEN EXISTS (SELECT 1 FROM course_instructors ci
                         WHERE ci.user_id = users.id AND ci.role = 'ta') THEN 'ta'
            WHEN EXISTS (SELECT 1 FROM enrollments e WHERE e.user_id = users.id) THEN 'student'
            ELSE 'guest'
        END
    """)

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_users_is_admin"), type_="check")
        batch_op.drop_column("is_admin")
        batch_op.create_check_constraint("role", f"role IN ({ROLES})")


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.execute("UPDATE users SET is_admin = (role = 'admin')")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_users_role"), type_="check")
        batch_op.drop_column("role")
        batch_op.create_check_constraint("is_admin", "is_admin IN (0, 1)")
