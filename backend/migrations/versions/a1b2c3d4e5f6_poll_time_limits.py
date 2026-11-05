"""poll time limits

Revision ID: a1b2c3d4e5f6
Revises: c4d5e6f7a8b9
Create Date: 2026-10-30 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = 'c4d5e6f7a8b9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# SQLite can only add a CHECK constraint by rebuilding the whole table, and the
# rename in that rebuild fails while triggers and views still point at `polls`.
# So drop them first and recreate them afterwards. These are frozen copies of
# the DDL in app/database/triggers.py as of this revision (like the initial
# migration, this file must not change when triggers.py is edited later).
_POLLED = "EXISTS (SELECT 1 FROM polls WHERE polls.question_id = {qid} AND polls.status <> 'draft')"

_TRIGGERS: dict[str, str] = {
    "trg_polls_lock_question_on_open": """
CREATE TRIGGER trg_polls_lock_question_on_open
AFTER UPDATE OF status ON polls
WHEN NEW.status = 'open'
BEGIN
    UPDATE questions SET is_locked = 1 WHERE id = NEW.question_id AND is_locked = 0;
END""",
    "trg_polls_lock_question_on_insert": """
CREATE TRIGGER trg_polls_lock_question_on_insert
AFTER INSERT ON polls
WHEN NEW.status <> 'draft'
BEGIN
    UPDATE questions SET is_locked = 1 WHERE id = NEW.question_id AND is_locked = 0;
END""",
    "trg_questions_locked_no_edit": """
CREATE TRIGGER trg_questions_locked_no_edit
BEFORE UPDATE ON questions
WHEN OLD.is_locked = 1 AND (
       NEW.is_locked = 0
    OR NEW.type IS NOT OLD.type
    OR NEW.body_md IS NOT OLD.body_md
    OR NEW.body_media_id IS NOT OLD.body_media_id
)
BEGIN
    SELECT RAISE(ABORT, 'question is locked because it has been polled; copy it to make changes');
END""",
    "trg_question_options_locked_insert": """
CREATE TRIGGER trg_question_options_locked_insert
BEFORE INSERT ON question_options
WHEN (SELECT is_locked FROM questions WHERE id = NEW.question_id) = 1
BEGIN
    SELECT RAISE(ABORT, 'cannot add choices to a locked question; copy it to make changes');
END""",
    "trg_question_options_locked_update": """
CREATE TRIGGER trg_question_options_locked_update
BEFORE UPDATE OF question_id, position, text_md, media_id ON question_options
WHEN (SELECT is_locked FROM questions WHERE id = OLD.question_id) = 1
BEGIN
    SELECT RAISE(ABORT, 'cannot change choices of a locked question (is_correct may still change)');
END""",
    "trg_question_options_locked_delete": f"""
CREATE TRIGGER trg_question_options_locked_delete
BEFORE DELETE ON question_options
WHEN {_POLLED.format(qid="OLD.question_id")}
BEGIN
    SELECT RAISE(ABORT, 'cannot delete choices of a question that has been polled');
END""",
    "trg_responses_poll_open_insert": """
CREATE TRIGGER trg_responses_poll_open_insert
BEFORE INSERT ON responses
WHEN (SELECT status FROM polls WHERE id = NEW.poll_id) IS NOT 'open'
BEGIN
    SELECT RAISE(ABORT, 'poll is not open');
END""",
    "trg_responses_poll_open_update": """
CREATE TRIGGER trg_responses_poll_open_update
BEFORE UPDATE OF text_answer, numeric_answer, poll_id, user_id ON responses
WHEN (SELECT status FROM polls WHERE id = NEW.poll_id) IS NOT 'open'
BEGIN
    SELECT RAISE(ABORT, 'poll is not open');
END""",
    "trg_response_choices_poll_open": """
CREATE TRIGGER trg_response_choices_poll_open
BEFORE INSERT ON response_choices
WHEN (SELECT p.status FROM responses r JOIN polls p ON p.id = r.poll_id
      WHERE r.id = NEW.response_id) IS NOT 'open'
BEGIN
    SELECT RAISE(ABORT, 'poll is not open');
END""",
    "trg_response_choices_option_matches": """
CREATE TRIGGER trg_response_choices_option_matches
BEFORE INSERT ON response_choices
WHEN (SELECT question_id FROM question_options WHERE id = NEW.option_id)
     IS NOT (SELECT p.question_id FROM responses r JOIN polls p ON p.id = r.poll_id
             WHERE r.id = NEW.response_id)
BEGIN
    SELECT RAISE(ABORT, 'option does not belong to this poll''s question');
END""",
    "trg_response_choices_single_answer": """
CREATE TRIGGER trg_response_choices_single_answer
BEFORE INSERT ON response_choices
WHEN (SELECT q.type FROM responses r
        JOIN polls p ON p.id = r.poll_id
        JOIN questions q ON q.id = p.question_id
      WHERE r.id = NEW.response_id) = 'mc_single'
 AND EXISTS (SELECT 1 FROM response_choices WHERE response_id = NEW.response_id)
BEGIN
    SELECT RAISE(ABORT, 'single-answer question accepts only one choice');
END""",
    "trg_event_log_no_update": """
CREATE TRIGGER trg_event_log_no_update
BEFORE UPDATE ON event_log
WHEN NEW.id IS NOT OLD.id
  OR NEW.occurred_at IS NOT OLD.occurred_at
  OR NEW.event_type IS NOT OLD.event_type
  OR NEW.ip_address IS NOT OLD.ip_address
  OR NEW.details_json IS NOT OLD.details_json
  OR (NEW.user_id IS NOT OLD.user_id AND NEW.user_id IS NOT NULL)
  OR (NEW.course_id IS NOT OLD.course_id AND NEW.course_id IS NOT NULL)
  OR (NEW.poll_id IS NOT OLD.poll_id AND NEW.poll_id IS NOT NULL)
BEGIN
    SELECT RAISE(ABORT, 'event_log is append-only');
END""",
}

_VIEWS: dict[str, str] = {
    "v_poll_scores": """
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
WHERE e.status = 'active'""",
    "v_poll_option_counts": """
CREATE VIEW v_poll_option_counts AS
SELECT
    p.id        AS poll_id,
    o.id        AS option_id,
    o.position,
    o.is_correct,
    COUNT(rc.response_id) AS votes
FROM polls p
JOIN question_options o     ON o.question_id = p.question_id
LEFT JOIN responses r       ON r.poll_id = p.id
LEFT JOIN response_choices rc ON rc.response_id = r.id AND rc.option_id = o.id
GROUP BY p.id, o.id""",
}

_DROP_DDL = [f"DROP VIEW IF EXISTS {name}" for name in _VIEWS] + [
    f"DROP TRIGGER IF EXISTS {name}" for name in _TRIGGERS
]
_CREATE_DDL = [sql.strip() for sql in _TRIGGERS.values()] + [
    sql.strip() for sql in _VIEWS.values()
]


def _drop_schema_objects() -> None:
    for statement in _DROP_DDL:
        op.execute(statement)


def _create_schema_objects() -> None:
    for statement in _CREATE_DDL:
        op.execute(statement)


def upgrade() -> None:
    """Optional time limit per poll: the configured duration and its deadline."""
    _drop_schema_objects()
    with op.batch_alter_table('polls', schema=None) as batch_op:
        batch_op.add_column(sa.Column('duration_seconds', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('closes_at', sa.DateTime(), nullable=True))
        batch_op.create_check_constraint(
            'ck_polls_duration_positive',
            'duration_seconds IS NULL OR duration_seconds > 0',
        )
        batch_op.create_check_constraint(
            'ck_polls_closes_needs_open',
            'closes_at IS NULL OR opened_at IS NOT NULL',
        )
    op.create_index(
        'ix_polls_open_closes_at',
        'polls',
        ['closes_at'],
        unique=False,
        sqlite_where=sa.text("status = 'open'"),
    )
    _create_schema_objects()


def downgrade() -> None:
    """Drop the time limit."""
    _drop_schema_objects()
    op.drop_index('ix_polls_open_closes_at', table_name='polls')
    with op.batch_alter_table('polls', schema=None) as batch_op:
        batch_op.drop_constraint('ck_polls_closes_needs_open', type_='check')
        batch_op.drop_constraint('ck_polls_duration_positive', type_='check')
        batch_op.drop_column('closes_at')
        batch_op.drop_column('duration_seconds')
    _create_schema_objects()
