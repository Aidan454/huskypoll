"""Run with:  pytest -q"""
from __future__ import annotations

import datetime as dt
import io
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from huskypoll_db import init_db, make_engine, make_session_factory
from huskypoll_db import services as svc
from huskypoll_db.export import participation_totals, write_huskyct_csv
from huskypoll_db.models import (
    EventLog,
    Poll,
    Response,
    User,
)
from huskypoll_db.roster import import_identifiers, import_studentadmin_xlsx

SAMPLE_ROSTER = Path(__file__).parent.parent / "samples" / "studentadmin-template.xlsx"


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
                               title="Data Structures", points_participation=1, points_correct=2)
    s1, _ = svc.find_or_create_user(db, net_id="abc12345", first_name="Ann", last_name="Able")
    s2, _ = svc.find_or_create_user(db, net_id="xyz67890", first_name="Bob", last_name="Baker")
    svc.enroll(db, course, s1)
    svc.enroll(db, course, s2)
    q = svc.create_question(db, prof, type="mc_single", body_md="2+2?",
                            options=[("3", False), ("4", True), ("5", False)])
    return prof, course, s1, s2, q


def _fails(db, sql, params=None, match=None):
    with pytest.raises(IntegrityError, match=match), db.begin_nested():
        db.execute(text(sql), params or {})


# --- connection setup ---------------------------------------------------------

def test_pragmas_are_set(db):
    assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1
    assert db.execute(text("PRAGMA journal_mode")).scalar() == "wal"


# --- users / roster -------------------------------------------------------------

def test_user_needs_an_identifier(db):
    _fails(db, "INSERT INTO users (created_at) VALUES ('2027-01-01')", match="has_identifier")


def test_netid_stored_lowercase(db):
    u, _ = svc.find_or_create_user(db, net_id="  ABC12345 ")
    assert u.net_id == "abc12345"
    _fails(db, "INSERT INTO users (net_id, created_at) VALUES ('ABC12345', '2027-01-01')",
           match="net_id_format")


@pytest.mark.parametrize("bad", ["prof01", "ab12345", "abcd1234", "abc1234", "abc123456", "12345abc", "abc-1234"])
def test_netid_must_be_three_letters_five_digits(db, bad):
    with pytest.raises(svc.HuskyPollError, match="not a valid NetID"):
        svc.find_or_create_user(db, net_id=bad)
    with pytest.raises(svc.HuskyPollError, match="not a valid NetID"):
        svc.record_login(db, net_id=bad, email="first.last@uconn.edu")
    _fails(db, "INSERT INTO users (net_id, created_at) VALUES (:n, '2027-01-01')",
           {"n": bad.lower()}, match="net_id_format")


def test_roster_import_reports_bad_netids(db, course_setup):
    _prof, course, *_ = course_setup
    res = import_identifiers(db, course, "abc11111\nprof01\nxy123\nABD22222")
    assert res.enrolled == 2
    assert [row for row, _ in res.skipped] == [2, 3]
    assert "not a valid NetID" in res.skipped[0][1]


def test_roster_row_links_to_first_login(db, course_setup):
    _prof, course, *_ = course_setup
    import_identifiers(db, course, "new.student@uconn.edu\n1234567, jdo99999")
    u = svc.record_login(db, net_id="NSX11111", email="New.Student@uconn.edu", first_name="New")
    assert u.email == "new.student@uconn.edu" and u.net_id == "nsx11111"
    assert db.query(User).filter_by(email="new.student@uconn.edu").count() == 1
    assert svc.is_enrolled(db, course, u)


def test_studentadmin_import(db, course_setup):
    prof, course, *_ = course_setup
    res = import_studentadmin_xlsx(db, course, SAMPLE_ROSTER, by=prof)
    assert res.enrolled == 1 and not res.skipped
    u = db.query(User).filter_by(student_id="1234567").one()
    assert (u.first_name, u.last_name) == ("FirstName", "LastName")
    enr = svc.enroll(db, course, u)[0]
    assert enr.section == "011Lab" and enr.source == "import"
    # Re-import is idempotent
    res2 = import_studentadmin_xlsx(db, course, SAMPLE_ROSTER)
    assert res2.enrolled == 0 and res2.unchanged == 1


def test_drop_missing_keeps_history(db, course_setup):
    _prof, course, _s1, s2, _q = course_setup
    from huskypoll_db.roster import import_records
    res = import_records(db, course, [{"net_id": "abc12345"}], drop_missing=True)
    assert res.dropped == 1
    assert not svc.is_enrolled(db, course, s2)


# --- check constraints --------------------------------------------------------

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


# --- polls, locking, responses ------------------------------------------------

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


def test_event_log_is_append_only(db, course_setup):
    _fails(db, "UPDATE event_log SET event_type = 'x'", match="append-only")


# --- export -------------------------------------------------------------------

def test_participation_export(db, course_setup):
    prof, course, s1, s2, q = course_setup
    sess = svc.get_or_create_session(db, course, on_date=dt.date(2027, 2, 1))
    poll = svc.open_poll(db, course, q, prof, lecture_session=sess)
    svc.submit_response(db, poll, s1, option_ids=[q.options[1].id])  # correct
    svc.close_poll(db, poll, prof)
    open_poll = svc.open_poll(db, course, q, prof, lecture_session=sess)  # still open: not counted
    svc.submit_response(db, open_poll, s2, option_ids=[q.options[1].id])

    totals = {r["net_id"]: r for r in participation_totals(db, course)}
    assert totals["abc12345"]["points"] == 3 and totals["abc12345"]["points_possible"] == 3
    assert totals["xyz67890"]["points"] == 0 and totals["xyz67890"]["polls"] == 1

    buf = io.StringIO()
    assert write_huskyct_csv(db, course, buf) == 2
    lines = buf.getvalue().splitlines()
    assert lines[0].endswith("[Total Pts: 3 Score]")
    assert lines[1] == "Able,Ann,abc12345,,3"

    assert participation_totals(db, course, start=dt.date(2027, 3, 1))[0]["points"] == 0


def test_timestamps_are_utc_aware(db, course_setup):
    prof, _course, *_ = course_setup
    db.expire_all()
    assert db.get(User, prof.id).created_at.tzinfo == dt.UTC


# --- end of semester ----------------------------------------------------------

def _count(db, table, where="1=1", **params):
    return db.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}"), params).scalar()


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


# --- who can log in ------------------------------------------------------------

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


def test_db_requires_netid_once_logged_in(db):
    _fails(db, "INSERT INTO users (email, created_at, last_login_at) "
               "VALUES ('a.b@uconn.edu', '2027-01-01', '2027-01-01')", match="logged_in_has_net_id")


# --- account roles ----------------------------------------------------------------

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
