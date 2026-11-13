"""The background timer that closes expired polls.

Run with: python -m pytest -q tests/test_db_timers.py
"""

from __future__ import annotations

import datetime as dt

from app.database import services as svc
from app.database.database import init_db, make_engine, make_session_factory
from app.database.models import EventLog, Poll
from app.timers import close_expired_polls


def test_timer_loop_closes_expired_polls(tmp_path):
    engine = make_engine(tmp_path / "timer.db")
    init_db(engine)
    Session = make_session_factory(engine)
    with Session() as db:
        prof, _ = svc.find_or_create_user(db, net_id="prf00001", first_name="Pat", last_name="Prof")
        svc.set_role(db, prof, "instructor")
        course = svc.create_course(db, prof, term="Spring 2027", subject="cse", catalog="2050",
                                   title="Data Structures")
        q = svc.create_question(db, prof, type="mc_single", body_md="2+2?",
                                options=[("3", False), ("4", True)])
        poll = svc.open_poll(db, course, q, prof, duration_seconds=60)
        poll.closes_at = svc.utcnow() - dt.timedelta(seconds=1)
        db.commit()
        course_id, poll_id = course.id, poll.id

    assert close_expired_polls(Session) == [(course_id, poll_id)]

    with Session() as db:
        poll = db.get(Poll, poll_id)
        assert poll.status == "closed" and poll.closed_at is not None
        assert "poll_timeout" in {e.event_type for e in db.query(EventLog)}
    engine.dispose()
