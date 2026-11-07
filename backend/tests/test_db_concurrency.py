"""Concurrent requests that once created duplicate rows or failed.

Run with: python -m pytest -q tests/test_database_concurrency.py
"""

from __future__ import annotations

from app.database import services as svc
from app.database.database import init_db, make_engine, make_session_factory
from app.database.models import Poll, Response, User


def test_two_simultaneous_first_logins_share_one_account(tmp_path):
    """Regression: two requests creating the same new user at once must not fail."""
    import threading

    engine = make_engine(tmp_path / "race.db")
    init_db(engine)
    Session = make_session_factory(engine)
    a_flushed, b_checked = threading.Event(), threading.Event()
    results, errors = {}, []

    def first():
        with Session() as db:
            u, created = svc.find_or_create_user(db, net_id="rac12345")  # inserted, not yet committed
            a_flushed.set()
            b_checked.wait(5)          # B has already looked and seen no user
            db.commit()
            results["a"] = (u.id, created)

    def second():
        a_flushed.wait(5)
        with Session() as db:
            assert svc.find_user(db, net_id="rac12345") is None   # A hasn't committed yet
            b_checked.set()
            try:
                u, created = svc.find_or_create_user(db, net_id="rac12345")  # waits for A, then collides
                db.commit()
                results["b"] = (u.id, created)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

    threads = [threading.Thread(target=first), threading.Thread(target=second)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert not errors, errors
    assert results["a"][0] == results["b"][0] and results["a"][1] is True and results["b"][1] is False
    with Session() as db:
        assert db.query(User).filter_by(net_id="rac12345").count() == 1


def test_double_tapped_submit_records_one_answer(tmp_path):
    """Regression: two simultaneous submissions from one student must both succeed, one row."""
    import threading

    engine = make_engine(tmp_path / "tap.db")
    init_db(engine)
    Session = make_session_factory(engine)
    with Session.begin() as db:
        prof, _ = svc.find_or_create_user(db, net_id="prf00001")
        prof.role = "instructor"
        course = svc.create_course(db, prof, term="T", subject="C", catalog="1", title="t")
        stu, _ = svc.find_or_create_user(db, net_id="stu00001")
        svc.enroll(db, course, stu)
        q = svc.create_question(db, prof, type="mc_single", body_md="?", options=[("a", True), ("b", False)])
        poll_id, stu_id, opt = svc.open_poll(db, course, q, prof).id, stu.id, q.options[0].id

    a_inserted, b_checked = threading.Event(), threading.Event()
    errors = []

    def tap(first: bool):
        try:
            with Session() as db:
                poll, user = db.get(Poll, poll_id), db.get(User, stu_id)
                if first:
                    svc.submit_response(db, poll, user, option_ids=[opt])
                    a_inserted.set()
                    b_checked.wait(5)
                else:
                    a_inserted.wait(5)
                    assert db.query(Response).filter_by(poll_id=poll_id).count() == 0  # A not committed
                    b_checked.set()
                    svc.submit_response(db, poll, user, option_ids=[opt])
                db.commit()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=tap, args=(f,)) for f in (True, False)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert not errors, errors
    with Session() as db:
        rows = db.query(Response).filter_by(poll_id=poll_id).all()
        assert len(rows) == 1 and [c.option_id for c in rows[0].choices] == [opt]
