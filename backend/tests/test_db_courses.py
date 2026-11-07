"""Course lifecycle: archive, restore, delete and event-log retention.

Run with: python -m pytest -q tests/test_database_courses.py
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import text

from app.database import services as svc
from app.database.models import EventLog
from tests.helpers import _count, _fails


def test_delete_course_removes_course_data_keeps_questions_users_logs(db, course_setup):
    prof, course, s1, _s2, q = course_setup
    bank = svc.QuestionBank(owner_id=prof.id, course_id=course.id, name="bank")
    db.add(bank)
    db.flush()
    q.bank_id = bank.id
    poll = svc.open_poll(db, course, q, prof)
    svc.submit_response(db, poll, s1, option_ids=[q.options[1].id])
    svc.close_poll(db, poll, prof)
    cid, bank_id = course.id, bank.id

    summary = svc.delete_course(db, course, prof)
    assert summary["polls"] == 1 and summary["responses"] == 1 and summary["students"] == 2

    for table in ("courses", "enrollments", "course_instructors", "lecture_sessions", "polls",
                  "responses", "response_choices"):
        assert _count(db, table) == 0, table
    assert _count(db, "questions") == 1 and _count(db, "users") == 3
    assert db.execute(text("SELECT course_id FROM question_banks WHERE id = :b"), {"b": bank_id}).scalar() is None
    assert _count(db, "event_log", "course_id = :c", c=cid) == 0  # links cleared...
    assert _count(db, "event_log", "event_type = 'response_submit'") == 1  # ...entries kept
    assert _count(db, "event_log", "event_type = 'course_delete'") == 1
    # The log is still protected against real edits
    _fails(db, "UPDATE event_log SET event_type = 'x'", match="append-only")
    _fails(db, "UPDATE event_log SET user_id = 999 WHERE user_id IS NOT NULL", match="append-only")


def test_delete_course_with_logs(db, course_setup):
    prof, course, s1, _s2, q = course_setup
    poll = svc.open_poll(db, course, q, prof)
    svc.submit_response(db, poll, s1, option_ids=[q.options[1].id])
    svc.delete_course(db, course, prof, delete_logs=True)
    assert _count(db, "event_log", "event_type IN ('poll_open', 'response_submit', 'course_create')") == 0
    assert _count(db, "event_log", "event_type = 'course_delete'") == 1


def test_only_owner_can_delete_course(db, course_setup):
    _prof, course, s1, _s2, _q = course_setup
    ta, _ = svc.find_or_create_user(db, net_id="tas00001")
    svc.add_instructor(db, course, ta, role="ta")
    for user in (ta, s1):
        with pytest.raises(svc.HuskyPollError, match="owner"):
            svc.delete_course(db, course, user)
    assert _count(db, "courses") == 1


def test_archive_and_restore(db, course_setup):
    prof, course, s1, _s2, _q = course_setup
    svc.archive_course(db, course, prof)
    assert course.archived_at is not None
    svc.unarchive_course(db, course, prof)
    assert course.archived_at is None
    with pytest.raises(svc.HuskyPollError):
        svc.archive_course(db, course, s1)


def test_deleting_a_user_keeps_their_log_entries(db, course_setup):
    _prof, _course, s1, _s2, _q = course_setup
    svc.record_login(db, net_id="abc12345", email="ann.able@uconn.edu")
    db.delete(s1)
    db.flush()
    assert _count(db, "event_log", "event_type = 'login' AND user_id IS NULL") == 1


def test_counts_stay_correct_within_one_session(db, course_setup):
    """Regression: summaries and regrades must not rely on stale loaded collections."""
    prof, course, s1, s2, q = course_setup
    sess = svc.get_or_create_session(db, course, on_date=dt.date(2027, 2, 1))
    assert sess in course.sessions
    polls = []
    for _ in range(3):
        p = svc.open_poll(db, course, q, prof, lecture_session=sess)
        _ = p.responses  # load the (empty) collection before anyone answers
        svc.submit_response(db, p, s1, option_ids=[q.options[0].id])
        svc.submit_response(db, p, s2, option_ids=[q.options[1].id])
        svc.close_poll(db, p, prof)
        polls.append(p)
    assert [p.position for p in polls] == [0, 1, 2]
    q.options[0].is_correct, q.options[1].is_correct = True, False
    db.flush()
    assert svc.regrade_poll(db, polls[0]) == 2
    close_log = db.query(EventLog).filter_by(event_type="poll_close").first()
    assert close_log.details_json["responses"] == 2
    summary = svc.delete_course(db, course, prof)
    assert (summary["sessions"], summary["polls"], summary["responses"], summary["students"]) == (1, 3, 6, 2)
