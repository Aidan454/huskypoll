"""remove course section and correct-answer points

Revision ID: d9e0f1a2b3c4
Revises: a1b2c3d4e5f6
Create Date: 2026-11-06 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd9e0f1a2b3c4'
down_revision: str | Sequence[str] | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# SQLite rebuilds the whole courses table in batch mode, and the rename fails
# while a view still points at it. This is a frozen copy of the view in
# app/database/triggers.py as of this revision; it does not use either column.
_V_POLL_SCORES = """
CREATE VIEW v_poll_scores AS
SELECT
    e.course_id,
    e.user_id,
    s.id            AS session_id,
    s.session_date,
    p.id            AS poll_id,
    q.id            AS question_id,
    r.id            AS response_id,
    CASE WHEN r.id IS NULL THEN 0 ELSE 1 END AS answered,
    r.is_correct,
    CASE q.type
        WHEN 'numeric'   THEN q.numeric_answer IS NOT NULL
        WHEN 'free_text' THEN q.text_answer IS NOT NULL
        ELSE EXISTS (SELECT 1 FROM question_options o WHERE o.question_id = q.id AND o.is_correct = 1)
    END AS has_answer_key,
    (CASE WHEN r.id IS NULL THEN 0 ELSE c.points_participation END) AS points,
    c.points_participation AS points_possible
FROM enrollments e
JOIN courses c          ON c.id = e.course_id
JOIN lecture_sessions s ON s.course_id = e.course_id
JOIN polls p            ON p.session_id = s.id AND p.status = 'closed'
JOIN questions q        ON q.id = p.question_id
LEFT JOIN responses r   ON r.poll_id = p.id AND r.user_id = e.user_id
WHERE e.status = 'active'"""


def upgrade() -> None:
    """Drop courses.section and courses.points_correct."""
    op.execute("DROP VIEW IF EXISTS v_poll_scores")
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_courses_points_nonneg'), type_='check')
        batch_op.drop_constraint(op.f('uq_courses_term_subject_catalog_section'), type_='unique')
        batch_op.drop_column('section')
        batch_op.drop_column('points_correct')
        batch_op.create_check_constraint(op.f('ck_courses_points_nonneg'), 'points_participation >= 0')
        batch_op.create_unique_constraint(
            op.f('uq_courses_term_subject_catalog'), ['term', 'subject', 'catalog']
        )
    op.execute(_V_POLL_SCORES.strip())


def downgrade() -> None:
    """Restore the columns and the old identity rule (section values cannot be recovered)."""
    op.execute("DROP VIEW IF EXISTS v_poll_scores")
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('uq_courses_term_subject_catalog'), type_='unique')
        batch_op.drop_constraint(op.f('ck_courses_points_nonneg'), type_='check')
        batch_op.add_column(sa.Column('section', sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column('points_correct', sa.Float(), nullable=False, server_default='0'))
        batch_op.create_check_constraint(
            op.f('ck_courses_points_nonneg'), 'points_participation >= 0 AND points_correct >= 0'
        )
        batch_op.create_unique_constraint(
            op.f('uq_courses_term_subject_catalog_section'), ['term', 'subject', 'catalog', 'section']
        )
    op.execute(_V_POLL_SCORES.strip())
