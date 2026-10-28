"""initial schema

Revision ID: 2c3b479f4768
Revises: 
Create Date: 2026-10-01 20:23:40.196484

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.database.models

# Triggers and views as they were at this revision. Copied, not imported,
# so this migration never changes when triggers.py is edited later.
DDL_STATEMENTS = [
    """CREATE TRIGGER trg_polls_lock_question_on_open
AFTER UPDATE OF status ON polls
WHEN NEW.status = 'open'
BEGIN
    UPDATE questions SET is_locked = 1 WHERE id = NEW.question_id AND is_locked = 0;
END""",
    """CREATE TRIGGER trg_polls_lock_question_on_insert
AFTER INSERT ON polls
WHEN NEW.status <> 'draft'
BEGIN
    UPDATE questions SET is_locked = 1 WHERE id = NEW.question_id AND is_locked = 0;
END""",
    """CREATE TRIGGER trg_questions_locked_no_edit
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
    """CREATE TRIGGER trg_question_options_locked_insert
BEFORE INSERT ON question_options
WHEN (SELECT is_locked FROM questions WHERE id = NEW.question_id) = 1
BEGIN
    SELECT RAISE(ABORT, 'cannot add choices to a locked question; copy it to make changes');
END""",
    """CREATE TRIGGER trg_question_options_locked_update
BEFORE UPDATE OF question_id, position, text_md, media_id ON question_options
WHEN (SELECT is_locked FROM questions WHERE id = OLD.question_id) = 1
BEGIN
    SELECT RAISE(ABORT, 'cannot change choices of a locked question (is_correct may still change)');
END""",
    """CREATE TRIGGER trg_question_options_locked_delete
BEFORE DELETE ON question_options
WHEN EXISTS (SELECT 1 FROM polls WHERE polls.question_id = OLD.question_id AND polls.status <> 'draft')
BEGIN
    SELECT RAISE(ABORT, 'cannot delete choices of a question that has been polled');
END""",
    """CREATE TRIGGER trg_responses_poll_open_insert
BEFORE INSERT ON responses
WHEN (SELECT status FROM polls WHERE id = NEW.poll_id) IS NOT 'open'
BEGIN
    SELECT RAISE(ABORT, 'poll is not open');
END""",
    """CREATE TRIGGER trg_responses_poll_open_update
BEFORE UPDATE OF text_answer, numeric_answer, poll_id, user_id ON responses
WHEN (SELECT status FROM polls WHERE id = NEW.poll_id) IS NOT 'open'
BEGIN
    SELECT RAISE(ABORT, 'poll is not open');
END""",
    """CREATE TRIGGER trg_response_choices_poll_open
BEFORE INSERT ON response_choices
WHEN (SELECT p.status FROM responses r JOIN polls p ON p.id = r.poll_id
      WHERE r.id = NEW.response_id) IS NOT 'open'
BEGIN
    SELECT RAISE(ABORT, 'poll is not open');
END""",
    """CREATE TRIGGER trg_response_choices_option_matches
BEFORE INSERT ON response_choices
WHEN (SELECT question_id FROM question_options WHERE id = NEW.option_id)
     IS NOT (SELECT p.question_id FROM responses r JOIN polls p ON p.id = r.poll_id
             WHERE r.id = NEW.response_id)
BEGIN
    SELECT RAISE(ABORT, 'option does not belong to this poll''s question');
END""",
    """CREATE TRIGGER trg_response_choices_single_answer
BEFORE INSERT ON response_choices
WHEN (SELECT q.type FROM responses r
        JOIN polls p ON p.id = r.poll_id
        JOIN questions q ON q.id = p.question_id
      WHERE r.id = NEW.response_id) = 'mc_single'
 AND EXISTS (SELECT 1 FROM response_choices WHERE response_id = NEW.response_id)
BEGIN
    SELECT RAISE(ABORT, 'single-answer question accepts only one choice');
END""",
    """CREATE TRIGGER trg_event_log_no_update
BEFORE UPDATE ON event_log
BEGIN
    SELECT RAISE(ABORT, 'event_log is append-only');
END""",
    """CREATE VIEW v_poll_scores AS
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
    (CASE WHEN r.id IS NULL THEN 0 ELSE c.points_participation END)
      + (CASE WHEN r.is_correct = 1 THEN c.points_correct ELSE 0 END) AS points,
    c.points_participation
      + (CASE WHEN (CASE q.type
                        WHEN 'numeric'   THEN q.numeric_answer IS NOT NULL
                        WHEN 'free_text' THEN q.text_answer IS NOT NULL
                        ELSE EXISTS (SELECT 1 FROM question_options o
                                     WHERE o.question_id = q.id AND o.is_correct = 1)
                    END) THEN c.points_correct ELSE 0 END) AS points_possible
FROM enrollments e
JOIN courses c          ON c.id = e.course_id
JOIN lecture_sessions s ON s.course_id = e.course_id
JOIN polls p            ON p.session_id = s.id AND p.status = 'closed'
JOIN questions q        ON q.id = p.question_id
LEFT JOIN responses r   ON r.poll_id = p.id AND r.user_id = e.user_id
WHERE e.status = 'active'""",
    """CREATE VIEW v_poll_option_counts AS
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
]

DROP_STATEMENTS = [
    "DROP VIEW IF EXISTS v_poll_scores",
    "DROP VIEW IF EXISTS v_poll_option_counts",
    "DROP TRIGGER IF EXISTS trg_polls_lock_question_on_open",
    "DROP TRIGGER IF EXISTS trg_polls_lock_question_on_insert",
    "DROP TRIGGER IF EXISTS trg_questions_locked_no_edit",
    "DROP TRIGGER IF EXISTS trg_question_options_locked_insert",
    "DROP TRIGGER IF EXISTS trg_question_options_locked_update",
    "DROP TRIGGER IF EXISTS trg_question_options_locked_delete",
    "DROP TRIGGER IF EXISTS trg_responses_poll_open_insert",
    "DROP TRIGGER IF EXISTS trg_responses_poll_open_update",
    "DROP TRIGGER IF EXISTS trg_response_choices_poll_open",
    "DROP TRIGGER IF EXISTS trg_response_choices_option_matches",
    "DROP TRIGGER IF EXISTS trg_response_choices_single_answer",
    "DROP TRIGGER IF EXISTS trg_event_log_no_update",
]

# revision identifiers, used by Alembic.
revision: str = '2c3b479f4768'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('net_id', sa.String(length=32), nullable=True),
    sa.Column('student_id', sa.String(length=16), nullable=True),
    sa.Column('email', sa.String(length=254), nullable=True),
    sa.Column('first_name', sa.String(length=100), nullable=True),
    sa.Column('last_name', sa.String(length=100), nullable=True),
    sa.Column('is_admin', sa.Boolean(create_constraint=True, name='is_admin'), nullable=False),
    sa.Column('created_at', app.database.models.UTCDateTime(), nullable=False),
    sa.Column('last_login_at', app.database.models.UTCDateTime(), nullable=True),
    sa.CheckConstraint('email IS NULL OR email = lower(email)', name=op.f('ck_users_email_lower')),
    sa.CheckConstraint('net_id IS NOT NULL OR email IS NOT NULL OR student_id IS NOT NULL', name=op.f('ck_users_has_identifier')),
    sa.CheckConstraint('net_id IS NULL OR net_id = lower(net_id)', name=op.f('ck_users_net_id_lower')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email')),
    sa.UniqueConstraint('net_id', name=op.f('uq_users_net_id')),
    sa.UniqueConstraint('student_id', name=op.f('uq_users_student_id'))
    )
    op.create_table('courses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('term', sa.String(length=32), nullable=False),
    sa.Column('subject', sa.String(length=16), nullable=False),
    sa.Column('catalog', sa.String(length=16), nullable=False),
    sa.Column('section', sa.String(length=16), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('join_code', sa.String(length=16), nullable=True),
    sa.Column('points_participation', sa.Float(), nullable=False),
    sa.Column('points_correct', sa.Float(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('created_at', app.database.models.UTCDateTime(), nullable=False),
    sa.Column('archived_at', app.database.models.UTCDateTime(), nullable=True),
    sa.CheckConstraint('points_participation >= 0 AND points_correct >= 0', name=op.f('ck_courses_points_nonneg')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_courses_created_by_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_courses')),
    sa.UniqueConstraint('join_code', name=op.f('uq_courses_join_code')),
    sa.UniqueConstraint('term', 'subject', 'catalog', 'section', name=op.f('uq_courses_term_subject_catalog_section'))
    )
    op.create_table('media',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('mime_type', sa.String(length=100), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=True),
    sa.Column('uploaded_by', sa.Integer(), nullable=True),
    sa.Column('created_at', app.database.models.UTCDateTime(), nullable=False),
    sa.CheckConstraint("mime_type LIKE 'image/%'", name=op.f('ck_media_image_only')),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], name=op.f('fk_media_uploaded_by_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_media')),
    sa.UniqueConstraint('sha256', name=op.f('uq_media_sha256'))
    )
    op.create_table('course_instructors',
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('added_at', app.database.models.UTCDateTime(), nullable=False),
    sa.CheckConstraint("role IN ('owner', 'instructor', 'ta')", name=op.f('ck_course_instructors_role')),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_course_instructors_course_id_courses'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_course_instructors_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('course_id', 'user_id', name=op.f('pk_course_instructors'))
    )
    with op.batch_alter_table('course_instructors', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_course_instructors_user_id'), ['user_id'], unique=False)

    op.create_table('enrollments',
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('section', sa.String(length=16), nullable=True),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('added_at', app.database.models.UTCDateTime(), nullable=False),
    sa.CheckConstraint("source IN ('import', 'manual', 'self')", name=op.f('ck_enrollments_source')),
    sa.CheckConstraint("status IN ('active', 'dropped')", name=op.f('ck_enrollments_status')),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_enrollments_course_id_courses'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_enrollments_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('course_id', 'user_id', name=op.f('pk_enrollments'))
    )
    with op.batch_alter_table('enrollments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_enrollments_user_id'), ['user_id'], unique=False)

    op.create_table('lecture_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=True),
    sa.Column('session_date', sa.Date(), nullable=False),
    sa.Column('started_at', app.database.models.UTCDateTime(), nullable=True),
    sa.Column('ended_at', app.database.models.UTCDateTime(), nullable=True),
    sa.Column('is_auto', sa.Boolean(create_constraint=True, name='is_auto'), nullable=False),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_lecture_sessions_course_id_courses'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lecture_sessions'))
    )
    with op.batch_alter_table('lecture_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lecture_sessions_course_id'), ['course_id', 'session_date'], unique=False)

    op.create_table('question_banks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', app.database.models.UTCDateTime(), nullable=False),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_question_banks_course_id_courses'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_question_banks_owner_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_question_banks'))
    )
    with op.batch_alter_table('question_banks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_question_banks_course_id'), ['course_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_question_banks_owner_id'), ['owner_id'], unique=False)

    op.create_table('questions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bank_id', sa.Integer(), nullable=True),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(length=16), nullable=False),
    sa.Column('body_md', sa.Text(), nullable=False),
    sa.Column('body_media_id', sa.Integer(), nullable=True),
    sa.Column('explanation_md', sa.Text(), nullable=True),
    sa.Column('explanation_media_id', sa.Integer(), nullable=True),
    sa.Column('text_answer', sa.Text(), nullable=True),
    sa.Column('numeric_answer', sa.Float(), nullable=True),
    sa.Column('numeric_tolerance', sa.Float(), nullable=True),
    sa.Column('copied_from_id', sa.Integer(), nullable=True),
    sa.Column('is_locked', sa.Boolean(create_constraint=True, name='is_locked'), nullable=False),
    sa.Column('created_at', app.database.models.UTCDateTime(), nullable=False),
    sa.Column('updated_at', app.database.models.UTCDateTime(), nullable=False),
    sa.CheckConstraint("body_md <> '' OR body_media_id IS NOT NULL", name=op.f('ck_questions_has_body')),
    sa.CheckConstraint("type = 'numeric' OR (numeric_answer IS NULL AND numeric_tolerance IS NULL)", name=op.f('ck_questions_numeric_fields_only_for_numeric')),
    sa.CheckConstraint("type IN ('mc_single', 'mc_multi', 'free_text', 'numeric')", name=op.f('ck_questions_type')),
    sa.CheckConstraint('numeric_tolerance IS NULL OR numeric_tolerance >= 0', name=op.f('ck_questions_tolerance_nonneg')),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], name=op.f('fk_questions_author_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['bank_id'], ['question_banks.id'], name=op.f('fk_questions_bank_id_question_banks'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['body_media_id'], ['media.id'], name=op.f('fk_questions_body_media_id_media'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['copied_from_id'], ['questions.id'], name=op.f('fk_questions_copied_from_id_questions'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['explanation_media_id'], ['media.id'], name=op.f('fk_questions_explanation_media_id_media'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_questions'))
    )
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_questions_author_id'), ['author_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_questions_bank_id'), ['bank_id'], unique=False)

    op.create_table('polls',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.Integer(), nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.Column('access_code', sa.String(length=16), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('show_results', sa.Boolean(create_constraint=True, name='show_results'), nullable=False),
    sa.Column('opened_by', sa.Integer(), nullable=True),
    sa.Column('opened_at', app.database.models.UTCDateTime(), nullable=True),
    sa.Column('closed_at', app.database.models.UTCDateTime(), nullable=True),
    sa.Column('created_at', app.database.models.UTCDateTime(), nullable=False),
    sa.CheckConstraint("status <> 'closed' OR closed_at IS NOT NULL", name=op.f('ck_polls_closed_has_time')),
    sa.CheckConstraint("status = 'draft' OR opened_at IS NOT NULL", name=op.f('ck_polls_opened_has_time')),
    sa.CheckConstraint("status IN ('draft', 'open', 'closed')", name=op.f('ck_polls_status')),
    sa.CheckConstraint('closed_at IS NULL OR closed_at >= opened_at', name=op.f('ck_polls_close_after_open')),
    sa.ForeignKeyConstraint(['opened_by'], ['users.id'], name=op.f('fk_polls_opened_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['question_id'], ['questions.id'], name=op.f('fk_polls_question_id_questions'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['session_id'], ['lecture_sessions.id'], name=op.f('fk_polls_session_id_lecture_sessions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_polls'))
    )
    with op.batch_alter_table('polls', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_polls_question_id'), ['question_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_polls_session_id'), ['session_id'], unique=False)
        batch_op.create_index('uq_polls_open_access_code', ['access_code'], unique=True, sqlite_where=sa.text("status = 'open'"))

    op.create_table('question_options',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('text_md', sa.Text(), nullable=False),
    sa.Column('media_id', sa.Integer(), nullable=True),
    sa.Column('is_correct', sa.Boolean(create_constraint=True, name='is_correct'), nullable=False),
    sa.CheckConstraint('position >= 0', name=op.f('ck_question_options_position_nonneg')),
    sa.ForeignKeyConstraint(['media_id'], ['media.id'], name=op.f('fk_question_options_media_id_media'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['question_id'], ['questions.id'], name=op.f('fk_question_options_question_id_questions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_question_options')),
    sa.UniqueConstraint('question_id', 'position', name=op.f('uq_question_options_question_id_position'))
    )
    op.create_table('event_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('occurred_at', app.database.models.UTCDateTime(), nullable=False),
    sa.Column('event_type', sa.String(length=32), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('course_id', sa.Integer(), nullable=True),
    sa.Column('poll_id', sa.Integer(), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('details_json', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_event_log_course_id_courses'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['poll_id'], ['polls.id'], name=op.f('fk_event_log_poll_id_polls'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_event_log_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_event_log'))
    )
    with op.batch_alter_table('event_log', schema=None) as batch_op:
        batch_op.create_index('ix_event_log_course_time', ['course_id', 'occurred_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_event_log_occurred_at'), ['occurred_at'], unique=False)
        batch_op.create_index('ix_event_log_user_time', ['user_id', 'occurred_at'], unique=False)

    op.create_table('responses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('poll_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('text_answer', sa.Text(), nullable=True),
    sa.Column('numeric_answer', sa.Float(), nullable=True),
    sa.Column('is_correct', sa.Boolean(create_constraint=True, name='is_correct'), nullable=True),
    sa.Column('submitted_at', app.database.models.UTCDateTime(), nullable=False),
    sa.Column('updated_at', app.database.models.UTCDateTime(), nullable=False),
    sa.ForeignKeyConstraint(['poll_id'], ['polls.id'], name=op.f('fk_responses_poll_id_polls'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_responses_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_responses')),
    sa.UniqueConstraint('poll_id', 'user_id', name=op.f('uq_responses_poll_id_user_id'))
    )
    with op.batch_alter_table('responses', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_responses_user_id'), ['user_id'], unique=False)

    op.create_table('response_choices',
    sa.Column('response_id', sa.Integer(), nullable=False),
    sa.Column('option_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['option_id'], ['question_options.id'], name=op.f('fk_response_choices_option_id_question_options'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['response_id'], ['responses.id'], name=op.f('fk_response_choices_response_id_responses'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('response_id', 'option_id', name=op.f('pk_response_choices'))
    )
    # ### end Alembic commands ###

    # Triggers and views (see app/database/triggers.py)
    for stmt in DDL_STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    """Downgrade schema."""
    for stmt in DROP_STATEMENTS:
        op.execute(stmt)
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('response_choices')
    with op.batch_alter_table('responses', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_responses_user_id'))

    op.drop_table('responses')
    with op.batch_alter_table('event_log', schema=None) as batch_op:
        batch_op.drop_index('ix_event_log_user_time')
        batch_op.drop_index(batch_op.f('ix_event_log_occurred_at'))
        batch_op.drop_index('ix_event_log_course_time')

    op.drop_table('event_log')
    op.drop_table('question_options')
    with op.batch_alter_table('polls', schema=None) as batch_op:
        batch_op.drop_index('uq_polls_open_access_code', sqlite_where=sa.text("status = 'open'"))
        batch_op.drop_index(batch_op.f('ix_polls_session_id'))
        batch_op.drop_index(batch_op.f('ix_polls_question_id'))

    op.drop_table('polls')
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_questions_bank_id'))
        batch_op.drop_index(batch_op.f('ix_questions_author_id'))

    op.drop_table('questions')
    with op.batch_alter_table('question_banks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_question_banks_owner_id'))
        batch_op.drop_index(batch_op.f('ix_question_banks_course_id'))

    op.drop_table('question_banks')
    with op.batch_alter_table('lecture_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lecture_sessions_course_id'))

    op.drop_table('lecture_sessions')
    with op.batch_alter_table('enrollments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_enrollments_user_id'))

    op.drop_table('enrollments')
    with op.batch_alter_table('course_instructors', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_course_instructors_user_id'))

    op.drop_table('course_instructors')
    op.drop_table('media')
    op.drop_table('courses')
    op.drop_table('users')
    # ### end Alembic commands ###
