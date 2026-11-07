"""Poll lifecycle, timed polls, question locking, responses and grading.

Run with: python -m pytest -q tests/test_database_polls.py
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import text

from app.database import services as svc
from app.database.models import EventLog, Response
from tests.helpers import _fails


def test_full_poll_flow_and_grading(db, course_setup):
    prof, course, s1, s2, q = course_setup
    poll = svc.open_poll(db, course, q, prof)
    assert poll.status == "open" and len(poll.access_code) == 5
    assert q.is_locked
    assert poll.session.is_auto  # session auto-created
    assert svc.find_open_poll_by_code(db, poll.access_code.lower()) is poll

    right = next(o for o in q.options if o.is_correct)
    wrong = next(o for o in q.options if not o.is_correct)
    r1 = svc.submit_response(db, poll, s1, option_ids=[wrong.id])
    assert r1.is_correct is False
    r1 = svc.submit_response(db, poll, s1, option_ids=[right.id])  # change answer while open
    assert r1.is_correct is True and len(r1.choices) == 1
    assert db.query(Response).filter_by(poll_id=poll.id).count() == 1

    svc.close_poll(db, poll, prof)
    with pytest.raises(svc.HuskyPollError, match="closed"):
        svc.submit_response(db, poll, s2, option_ids=[right.id])
    types = [e.event_type for e in db.query(EventLog).order_by(EventLog.id)]
    assert {"poll_open", "response_submit", "response_update", "poll_close"} <= set(types)


def test_reopen_closed_poll(db, course_setup):
    prof, course, s1, s2, q = course_setup
    right = next(o for o in q.options if o.is_correct)
    poll = svc.open_poll(db, course, q, prof)
    code = poll.access_code
    svc.submit_response(db, poll, s1, option_ids=[right.id])
    with pytest.raises(svc.HuskyPollError, match="only a closed poll"):
        svc.reopen_poll(db, poll, prof)
    svc.close_poll(db, poll, prof)
    with pytest.raises(svc.NotAllowed):
        svc.reopen_poll(db, poll, s1)

    svc.reopen_poll(db, poll, prof)
    assert (poll.status, poll.closed_at, poll.access_code) == ("open", None, code)
    assert svc.find_open_poll_by_code(db, code) is poll
    svc.submit_response(db, poll, s2, option_ids=[right.id])  # late students can answer now
    assert db.query(Response).filter_by(poll_id=poll.id).count() == 2  # earlier answer kept
    svc.close_poll(db, poll, prof)
    assert "poll_reopen" in {e.event_type for e in db.query(EventLog)}

    # If another open poll took the code meanwhile, the reopened poll gets a new one.
    other = svc.open_poll(db, course, q, prof)
    other.access_code = code
    db.flush()
    svc.reopen_poll(db, poll, prof)
    assert poll.access_code != code and poll.status == "open"

    svc.archive_course(db, course, prof)
    svc.close_poll(db, poll, prof)
    with pytest.raises(svc.HuskyPollError, match="archived"):
        svc.reopen_poll(db, poll, prof)


def test_timed_poll_has_a_deadline_and_refuses_late_answers(db, course_setup):
    prof, course, s1, _s2, q = course_setup
    poll = svc.open_poll(db, course, q, prof, duration_seconds=60)
    assert poll.duration_seconds == 60
    assert poll.closes_at - poll.opened_at == dt.timedelta(seconds=60)

    right = next(o for o in q.options if o.is_correct)
    svc.submit_response(db, poll, s1, option_ids=[right.id])

    poll.closes_at = svc.utcnow() - dt.timedelta(seconds=1)
    db.flush()
    with pytest.raises(svc.HuskyPollError, match="time is up"):
        svc.submit_response(db, poll, s1, option_ids=[right.id])

    # No duration means no timer, and nothing changes for existing polls.
    plain = svc.open_poll(db, course, q, prof)
    assert plain.duration_seconds is None and plain.closes_at is None


def test_extend_poll_adds_time_and_reopens_a_closed_poll(db, course_setup):
    prof, course, s1, _s2, q = course_setup
    poll = svc.open_poll(db, course, q, prof, duration_seconds=60)
    svc.close_poll(db, poll, prof)

    svc.extend_poll(db, poll, prof, 120)
    assert poll.status == "open" and poll.closed_at is None
    remaining = (poll.closes_at - svc.utcnow()).total_seconds()
    assert 118 <= remaining <= 121
    svc.submit_response(db, poll, s1, option_ids=[q.options[0].id])  # late students can answer now
    assert "poll_extended" in {e.event_type for e in db.query(EventLog)}

    with pytest.raises(svc.NotAllowed):
        svc.extend_poll(db, poll, s1, 60)

    plain = svc.open_poll(db, course, q, prof)
    with pytest.raises(svc.HuskyPollError, match="no timer"):
        svc.extend_poll(db, plain, prof, 60)


def test_not_enrolled_cannot_answer(db, course_setup):
    prof, course, _s1, _s2, q = course_setup
    outsider, _ = svc.find_or_create_user(db, net_id="out00001")
    poll = svc.open_poll(db, course, q, prof)
    with pytest.raises(svc.HuskyPollError, match="roster"):
        svc.submit_response(db, poll, outsider, option_ids=[q.options[0].id])


def test_only_instructors_open_polls(db, course_setup):
    _prof, course, s1, _s2, q = course_setup
    with pytest.raises(svc.HuskyPollError, match="instructor"):
        svc.open_poll(db, course, q, s1)


def test_locked_question_cannot_be_reworded_but_answer_can_change(db, course_setup):
    prof, course, _s1, _s2, q = course_setup
    _poll = svc.open_poll(db, course, q, prof)
    _fails(db, "UPDATE questions SET body_md = 'changed' WHERE id = :id", {"id": q.id}, match="locked")
    _fails(db, "UPDATE question_options SET text_md = 'x' WHERE question_id = :id", {"id": q.id}, match="locked")
    _fails(db, "INSERT INTO question_options (question_id, position, text_md, is_correct) VALUES (:id, 9, 'x', 0)",
           {"id": q.id}, match="locked")
    _fails(db, "DELETE FROM question_options WHERE question_id = :id", {"id": q.id}, match="polled")
    # Explanation and answer key stay editable:
    db.execute(text("UPDATE questions SET explanation_md = 'because' WHERE id = :id"), {"id": q.id})
    copy = svc.copy_question(db, q, prof)
    assert not copy.is_locked and copy.copied_from_id == q.id and len(copy.options) == 3


def test_add_answer_after_poll_and_regrade(db, course_setup):
    prof, course, s1, s2, _ = course_setup
    quick = svc.create_question(db, prof, type="mc_single", body_md="Quick in-lecture question",
                                options=[("A", False), ("B", False)])
    poll = svc.open_poll(db, course, quick, prof)
    svc.submit_response(db, poll, s1, option_ids=[quick.options[1].id])
    svc.submit_response(db, poll, s2, option_ids=[quick.options[0].id])
    assert all(r.is_correct is None for r in poll.responses)
    svc.close_poll(db, poll, prof)
    quick.options[1].is_correct = True  # instructor adds the answer after class
    db.flush()
    assert svc.regrade_poll(db, poll) == 2
    assert sorted(r.is_correct for r in poll.responses) == [False, True]


def test_mc_multi_numeric_free_text_grading(db, course_setup):
    prof, course, s1, s2, _ = course_setup
    multi = svc.create_question(db, prof, type="mc_multi", body_md="pick",
                                options=[("a", True), ("b", True), ("c", False)])
    num = svc.create_question(db, prof, type="numeric", body_md="pi?", numeric_answer=3.14, numeric_tolerance=0.01)
    free = svc.create_question(db, prof, type="free_text", body_md="LIFO?", text_answer="Stack")
    p = svc.open_poll(db, course, multi, prof)
    assert svc.submit_response(db, p, s1, option_ids=[multi.options[0].id, multi.options[1].id]).is_correct
    assert not svc.submit_response(db, p, s2, option_ids=[multi.options[0].id]).is_correct
    p = svc.open_poll(db, course, num, prof)
    assert svc.submit_response(db, p, s1, numeric_answer=3.145).is_correct
    assert not svc.submit_response(db, p, s2, numeric_answer=3.2).is_correct
    p = svc.open_poll(db, course, free, prof)
    assert svc.submit_response(db, p, s1, text_answer="  stack ").is_correct
