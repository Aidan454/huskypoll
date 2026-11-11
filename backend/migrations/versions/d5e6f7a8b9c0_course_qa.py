"""Add course questions and replies, independent of polls."""
import sqlalchemy as sa
from alembic import op

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade():
    for table, parent, target in (("course_questions", "course_id", "courses.id"),
                                  ("course_replies", "question_id", "course_questions.id")):
        op.create_table(table,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(parent, sa.Integer(), sa.ForeignKey(target, ondelete="CASCADE"), nullable=False),
            sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint("length(trim(body)) BETWEEN 1 AND 2000", name="body_length"))
        op.create_index(f"ix_{table}_{parent}", table, [parent])


def downgrade():
    op.drop_table("course_replies")
    op.drop_table("course_questions")
