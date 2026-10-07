"""Raw-SQL triggers and views.

These enforce rules that a plain CHECK constraint cannot express, so the
database stays consistent even if a bug in the API forgets a check:

  * Opening a poll locks its question; a locked question's wording, type,
    picture and choices can no longer change (copy it instead). Answers and
    explanations stay editable so an instructor can add or fix the answer
    key after class and regrade.
  * Students can only submit or change an answer while the poll is open.
  * A chosen option must belong to the poll's question, and a single-answer
    question accepts only one choice.
  * The event log is append-only (rows can be purged, never edited).

Used by models.py (on create_all) and by the Alembic migration.
"""

# "Has this question been asked?" - true once any poll using it left draft.
_POLLED = "EXISTS (SELECT 1 FROM polls WHERE polls.question_id = {qid} AND polls.status <> 'draft')"

TRIGGERS: dict[str, str] = {
    # --- question locking -------------------------------------------------
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
    "trg_question_options_locked_insert": f"""
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
    # --- responses only while the poll is open -----------------------------
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
    # --- choice must belong to the poll's question --------------------------
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
    # --- audit log is append-only -----------------------------------------
    # The only update allowed is the database itself clearing a link
    # (ON DELETE SET NULL) when the user, course or poll it points to is deleted.
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

VIEWS: dict[str, str] = {
    # One row per active student x closed poll in their course: did they answer,
    # were they right, points earned and possible. The HuskyCT export sums this.
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
    # Live bar chart: how many students picked each option of each poll.
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

DDL_STATEMENTS: list[str] = [sql.strip() for sql in TRIGGERS.values()] + [
    sql.strip() for sql in VIEWS.values()
]

DROP_STATEMENTS: list[str] = [f"DROP VIEW IF EXISTS {name}" for name in VIEWS] + [
    f"DROP TRIGGER IF EXISTS {name}" for name in TRIGGERS
]
