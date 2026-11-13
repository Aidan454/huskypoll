"""Database schema rules: PRAGMAs, constraints, triggers and timestamps.

Run with: python -m pytest -q tests/test_db_schema.py
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import text

from app.database import services as svc
from app.database.models import Poll, User
from tests.helpers import _fails


def test_pragmas_are_set(db):
    assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1
    assert db.execute(text("PRAGMA journal_mode")).scalar() == "wal"


def test_user_needs_an_identifier(db):
    _fails(db, "INSERT INTO users (created_at) VALUES ('2027-01-01')", match="has_identifier")


def test_netid_stored_lowercase(db):
    u, _ = svc.find_or_create_user(db, net_id="  ABC12345 ")
    assert u.net_id == "abc12345"
    _fails(db, "INSERT INTO users (net_id, created_at) VALUES ('ABC12345', '2027-01-01')",
           match="net_id_format")


def test_check_constraints_reject_bad_values(db, course_setup):
    _prof, _course, _s1, _s2, q = course_setup
    _fails(db, "UPDATE course_instructors SET role = 'boss'", match="role")
    _fails(db, "UPDATE enrollments SET status = 'gone'", match="status")
    _fails(db, "UPDATE questions SET type = 'essay' WHERE id = :id", {"id": q.id}, match="type")


def test_poll_status_needs_timestamps(db, course_setup):
    _prof, course, _s1, _s2, q = course_setup
    sess = svc.get_or_create_session(db, course, on_date=dt.date(2027, 2, 1))
    _fails(db, "INSERT INTO polls (session_id, question_id, status, position, show_results, created_at) "
               "VALUES (:s, :q, 'open', 0, 0, '2027-01-01')", {"s": sess.id, "q": q.id}, match="opened_has_time")


def test_poll_duration_must_be_positive(db, course_setup):
    prof, course, *_rest, q = course_setup
    poll = svc.open_poll(db, course, q, prof, duration_seconds=60)
    _fails(db, "UPDATE polls SET duration_seconds = 0 WHERE id = :id", {"id": poll.id},
           match="duration_positive")

    draft = Poll(session_id=poll.session_id, question_id=q.id, status="draft", position=99)
    db.add(draft)
    db.flush()
    _fails(db, "UPDATE polls SET closes_at = '2027-01-01' WHERE id = :id", {"id": draft.id},
           match="closes_needs_open")  # a deadline only makes sense once the poll was opened


def test_db_rejects_response_to_closed_poll_even_without_service(db, course_setup):
    prof, course, _s1, s2, q = course_setup
    poll = svc.open_poll(db, course, q, prof)
    svc.close_poll(db, poll, prof)
    _fails(db, "INSERT INTO responses (poll_id, user_id, submitted_at, updated_at) "
               "VALUES (:p, :u, '2027-01-01', '2027-01-01')", {"p": poll.id, "u": s2.id}, match="not open")


def test_option_must_belong_to_poll_question(db, course_setup):
    prof, course, s1, _s2, q = course_setup
    other = svc.create_question(db, prof, type="mc_single", body_md="other", options=[("x", True), ("y", False)])
    poll = svc.open_poll(db, course, q, prof)
    resp = svc.submit_response(db, poll, s1, option_ids=[q.options[0].id])
    db.execute(text("DELETE FROM response_choices WHERE response_id = :r"), {"r": resp.id})
    _fails(db, "INSERT INTO response_choices VALUES (:r, :o)", {"r": resp.id, "o": other.options[0].id},
           match="does not belong")
    db.execute(text("INSERT INTO response_choices VALUES (:r, :o)"), {"r": resp.id, "o": q.options[0].id})
    _fails(db, "INSERT INTO response_choices VALUES (:r, :o)", {"r": resp.id, "o": q.options[1].id},
           match="only one choice")


def test_one_response_per_student_per_poll(db, course_setup):
    prof, course, s1, _s2, q = course_setup
    poll = svc.open_poll(db, course, q, prof)
    svc.submit_response(db, poll, s1, option_ids=[q.options[0].id])
    _fails(db, "INSERT INTO responses (poll_id, user_id, submitted_at, updated_at) "
               "VALUES (:p, :u, '2027-01-01', '2027-01-01')", {"p": poll.id, "u": s1.id}, match="UNIQUE")


def test_access_code_unique_only_among_open_polls(db, course_setup):
    prof, course, _s1, _s2, q = course_setup
    p1 = svc.open_poll(db, course, q, prof)
    p2 = svc.open_poll(db, course, q, prof)
    _fails(db, "UPDATE polls SET access_code = :c WHERE id = :id", {"c": p1.access_code, "id": p2.id})
    svc.close_poll(db, p1, prof)
    db.execute(text("UPDATE polls SET access_code = :c WHERE id = :id"), {"c": p1.access_code, "id": p2.id})


def test_event_log_is_append_only(db, course_setup):
    _fails(db, "UPDATE event_log SET event_type = 'x'", match="append-only")


def test_timestamps_are_utc_aware(db, course_setup):
    prof, _course, *_ = course_setup
    db.expire_all()
    assert db.get(User, prof.id).created_at.tzinfo == dt.UTC


def test_db_requires_netid_once_logged_in(db):
    _fails(db, "INSERT INTO users (email, created_at, last_login_at) "
               "VALUES ('a.b@uconn.edu', '2027-01-01', '2027-01-01')", match="logged_in_has_net_id")
