"""Users, logins, NetID rules, account roles and course permissions.

Run with: python -m pytest -q tests/test_database_users.py
"""

from __future__ import annotations

import pytest

from app.database import services as svc
from app.database.models import User
from app.database.roster import import_identifiers
from tests.helpers import _count, _fails


@pytest.mark.parametrize("bad", ["prof01", "ab12345", "abcd1234", "abc1234", "abc123456", "12345abc", "abc-1234"])
def test_netid_must_be_three_letters_five_digits(db, bad):
    with pytest.raises(svc.HuskyPollError, match="not a valid NetID"):
        svc.find_or_create_user(db, net_id=bad)
    with pytest.raises(svc.HuskyPollError, match="not a valid NetID"):
        svc.record_login(db, net_id=bad, email="first.last@uconn.edu")
    _fails(db, "INSERT INTO users (net_id, created_at) VALUES (:n, '2027-01-01')",
           {"n": bad.lower()}, match="net_id_format")


def test_roster_row_links_to_first_login(db, course_setup):
    _prof, course, *_ = course_setup
    import_identifiers(db, course, "new.student@uconn.edu\n1234567, jdo99999")
    u = svc.record_login(db, net_id="NSX11111", email="New.Student@uconn.edu", first_name="New")
    assert u.email == "new.student@uconn.edu" and u.net_id == "nsx11111"
    assert db.query(User).filter_by(email="new.student@uconn.edu").count() == 1
    assert svc.is_enrolled(db, course, u)


@pytest.mark.parametrize("email,net_id,expected_netid", [
    ("jonathan.smith@uconn.edu", "jos10001", "jos10001"),
    ("Jonathan.Q.Smith@UConn.edu", "jqs10002", "jqs10002"),  # case doesn't matter
    ("mary-kate.smith-jones@uconn.edu", "mks10003", "mks10003"),  # hyphenated names
    ("abc12345@uconn.edu", None, "abc12345"),  # NetID taken from the email
    ("ABC12345@uconn.edu", "abc12345", "abc12345"),  # both given and they agree
])
def test_allowed_login_emails(db, email, net_id, expected_netid):
    u = svc.record_login(db, email=email, net_id=net_id)
    assert u.net_id == expected_netid and u.email == email.lower() and u.last_login_at


@pytest.mark.parametrize("email", [
    "jonathan.smith@gmail.com", "jonathan@uconn.edu", "jonathan.quincy.smith@uconn.edu",
    "j.q.r.smith@uconn.edu", "jonathan..smith@uconn.edu", "jonathan.smith2@uconn.edu",
    "abc1234@uconn.edu", "jonathan.smith@uconn.edu.evil.com", "jonathan.smith@health.uconn.edu", "",
])
def test_refused_login_emails(db, email):
    with pytest.raises(svc.HuskyPollError, match="Only UConn emails"):
        svc.record_login(db, email=email, net_id="abc12345")
    assert _count(db, "users") == 0


def test_login_needs_a_netid(db):
    with pytest.raises(svc.HuskyPollError, match="could not determine a NetID"):
        svc.record_login(db, email="jonathan.smith@uconn.edu")


def test_netid_email_must_match_netid(db):
    with pytest.raises(svc.HuskyPollError, match="does not belong"):
        svc.record_login(db, email="abc12345@uconn.edu", net_id="xyz67890")


def test_email_cannot_switch_netid(db):
    svc.record_login(db, email="jonathan.smith@uconn.edu", net_id="jos10001")
    with pytest.raises(svc.HuskyPollError, match="different NetID"):
        svc.record_login(db, email="jonathan.smith@uconn.edu", net_id="xyz67890")


def test_roster_email_gets_netid_at_first_login(db, course_setup):
    _prof, course, *_ = course_setup
    import_identifiers(db, course, "jonathan.smith@uconn.edu")
    roster_user = svc.find_user(db, email="jonathan.smith@uconn.edu")
    assert roster_user.net_id is None
    u = svc.record_login(db, email="jonathan.smith@uconn.edu", net_id="jos10001")
    assert u is roster_user and u.net_id == "jos10001" and svc.is_enrolled(db, course, u)


def test_new_login_is_guest_until_on_a_roster(db, course_setup):
    _prof, course, *_ = course_setup
    u = svc.record_login(db, email="new.person@uconn.edu", net_id="npe12345")
    assert u.role == "guest"
    svc.enroll(db, course, u)
    assert u.role == "student"


def test_roster_import_creates_students(db, course_setup):
    _prof, course, *_ = course_setup
    import_identifiers(db, course, "fresh.student@uconn.edu")
    assert svc.find_user(db, email="fresh.student@uconn.edu").role == "student"


def test_adding_course_staff_promotes_but_never_demotes(db, course_setup):
    _prof, course, s1, *_ = course_setup
    assert s1.role == "student"
    svc.add_instructor(db, course, s1, role="ta")
    assert s1.role == "ta"                       # student -> ta
    svc.enroll(db, course, s1)
    assert s1.role == "ta"                       # enrolling elsewhere doesn't demote
    svc.add_instructor(db, course, s1, role="instructor")
    assert s1.role == "instructor"


def test_only_instructors_and_admins_create_courses(db, course_setup):
    _prof, _course, s1, *_ = course_setup
    for role in ("ta", "student", "guest"):
        s1.role = role
        with pytest.raises(svc.NotAllowed, match="only instructors and admins"):
            svc.create_course(db, s1, term="T", subject="X", catalog="1", title="t")
    s1.role = "admin"
    assert svc.create_course(db, s1, term="T", subject="X", catalog="1", title="t")


def test_set_role_rules(db, course_setup):
    prof, _course, _s1, s2, _q = course_setup
    admin, _ = svc.find_or_create_user(db, net_id="adm00001")
    svc.set_role(db, admin, "admin")
    with pytest.raises(svc.NotAllowed, match="only an admin"):
        svc.set_role(db, s2, "instructor", by=prof)
    svc.set_role(db, s2, "instructor", by=admin)
    assert s2.role == "instructor"
    with pytest.raises(svc.HuskyPollError, match="at least one admin"):
        svc.set_role(db, admin, "instructor", by=admin)
    with pytest.raises(svc.HuskyPollError, match="role must be one of"):
        svc.set_role(db, s2, "superuser")
    _fails(db, "UPDATE users SET role = 'Admin' WHERE id = :u", {"u": s2.id}, match="ck_users_role")
    assert _count(db, "event_log", "event_type = 'role_change'") >= 2


def test_admin_has_every_course_permission(db, course_setup):
    _prof, course, _s1, _s2, _q = course_setup
    admin, _ = svc.find_or_create_user(db, net_id="adm00001")
    svc.set_role(db, admin, "admin")
    assert svc.is_instructor(db, course, admin) and svc.is_owner(db, course, admin)
