"""Scope Q&A to lectures; preserve prior course discussions in a separate lecture."""
import sqlalchemy as sa
from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = ("e6f7a8b9c0d1", "d9e0f1a2b3c4")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("course_questions", sa.Column("session_id", sa.Integer(), nullable=True))
    db = op.get_bind()
    # Old course posts cannot be attributed to a real lecture retrospectively.
    # Preserve them, with their replies, in an explicitly labeled legacy discussion.
    courses = db.execute(sa.text("SELECT course_id, min(created_at) AS first_post FROM course_questions GROUP BY course_id")).all()
    for course_id, first_post in courses:
        result = db.execute(sa.text("""INSERT INTO lecture_sessions
            (course_id, title, session_date, started_at, is_auto)
            VALUES (:course, 'Earlier course Q&A', :date, :started, 0)"""),
            {"course": course_id, "date": str(first_post)[:10], "started": first_post})
        db.execute(sa.text("UPDATE course_questions SET session_id=:session WHERE course_id=:course"),
                   {"session": result.lastrowid, "course": course_id})
    with op.batch_alter_table("course_questions") as batch:
        batch.alter_column("session_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key("fk_course_questions_session_id_lecture_sessions", "lecture_sessions", ["session_id"], ["id"], ondelete="CASCADE")
        batch.create_index("ix_course_questions_session_id", ["session_id"])


def downgrade():
    with op.batch_alter_table("course_questions") as batch:
        batch.drop_index("ix_course_questions_session_id")
        batch.drop_constraint("fk_course_questions_session_id_lecture_sessions", type_="foreignkey")
        batch.drop_column("session_id")
