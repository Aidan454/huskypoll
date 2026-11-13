"""Fixtures shared by the backend test files."""
from __future__ import annotations

import pytest

from app.app import create_app
from app.database import services as svc
from app.database.database import init_db, make_engine, make_session_factory
from tests.helpers import login, make_settings


@pytest.fixture()
def db(tmp_path):
    engine = make_engine(tmp_path / "test.db")
    init_db(engine)
    Session = make_session_factory(engine)
    with Session() as session:
        yield session
        session.rollback()
    engine.dispose()


@pytest.fixture()
def course_setup(db):
    prof, _ = svc.find_or_create_user(db, net_id="prf00001", first_name="Pat", last_name="Prof")
    svc.set_role(db, prof, "instructor")
    course = svc.create_course(db, prof, term="Spring 2027", subject="cse", catalog="2050",
                               title="Data Structures")
    s1, _ = svc.find_or_create_user(db, net_id="abc12345", first_name="Ann", last_name="Able")
    s2, _ = svc.find_or_create_user(db, net_id="xyz67890", first_name="Bob", last_name="Baker")
    svc.enroll(db, course, s1)
    svc.enroll(db, course, s2)
    q = svc.create_question(db, prof, type="mc_single", body_md="2+2?",
                            options=[("3", False), ("4", True), ("5", False)])
    return prof, course, s1, s2, q


@pytest.fixture()
def app(tmp_path):
    return create_app(make_settings(tmp_path))


@pytest.fixture()
def lecture(app):
    """A course with an owner, a TA, two students and one multiple-choice question."""
    prof = login(app, "pat.prof@uconn.edu", "prf00001", "Pat", "Prof", role="instructor")
    course = prof.post("/courses", json={"term": "Spring 2027", "subject": "cse", "catalog": "2050",
                                         "title": "Data Structures"}).json()
    cid = course["id"]
    assert prof.post(f"/courses/{cid}/instructors", json={"identifier": "tas00001", "role": "ta"}).status_code == 201
    r = prof.post(f"/courses/{cid}/roster/paste", json={"text": "ann.able@uconn.edu\nbob.baker@uconn.edu"})
    assert r.json()["enrolled"] == 2
    ann = login(app, "ann.able@uconn.edu", "aab11111", "Ann", "Able")
    bob = login(app, "bob.baker@uconn.edu", "bba22222", "Bob", "Baker")
    ta = login(app, "tas00001@uconn.edu")
    q = prof.post("/questions", json={"type": "mc_single", "body_md": "2+2?",
                                      "options": [{"text_md": "3"}, {"text_md": "4", "is_correct": True}],
                                      "explanation_md": "Arithmetic."}).json()
    return {"prof": prof, "ta": ta, "ann": ann, "bob": bob, "cid": cid, "q": q}
