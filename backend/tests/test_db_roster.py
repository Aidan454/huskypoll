"""StudentAdmin roster import, re-import, missing students and drops.

Run with: python -m pytest -q tests/test_db_roster.py
"""

from __future__ import annotations

import pytest

from app.database import services as svc
from app.database.models import User
from app.database.roster import (
    drop_students,
    import_identifiers,
    import_records,
    import_studentadmin_csv,
    import_studentadmin_xlsx,
    read_studentadmin_csv,
)
from tests.helpers import SAMPLE_ROSTER


def test_roster_import_reports_bad_netids(db, course_setup):
    _prof, course, *_ = course_setup
    res = import_identifiers(db, course, "abc11111\nprof01\nxy123\nABD22222")
    assert res.enrolled == 2
    assert [row for row, _ in res.skipped] == [2, 3]
    assert "not a valid NetID" in res.skipped[0][1]


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
    res = import_records(db, course, [{"net_id": "abc12345"}], drop_missing=True)
    assert res.dropped == 1
    assert not svc.is_enrolled(db, course, s2)


def test_studentadmin_csv_normalizes_case():
    rows = read_studentadmin_csv("\ufeffNetID,Email\r\nabc12345,Ann.Able@UConn.edu\r\n,\r\nXyz67890 , BOB@uconn.edu\r\n")
    assert [(r["net_id"], r["email"], r["_row"]) for r in rows] == [
        ("ABC12345", "ann.able@uconn.edu", 2),
        ("XYZ67890", "bob@uconn.edu", 4),
    ]
    with pytest.raises(svc.HuskyPollError, match="header row"):
        read_studentadmin_csv("hello,world\n1,2\n")


def test_reimport_reports_missing_without_dropping(db, course_setup):
    prof, course, s1, s2, _q = course_setup
    # s2 (xyz67890) dropped the course, one new student joined; NetIDs arrive in any case.
    res = import_studentadmin_csv(db, course, "NetID,Email\nABC12345,\nNEW11111,New.Student@UCONN.edu\n", by=prof)
    assert (res.enrolled, res.unchanged, res.dropped) == (1, 1, 0)
    assert [u.net_id for u in res.added] == ["new11111"]
    assert res.missing == [s2]
    assert svc.is_enrolled(db, course, s2)  # nothing dropped until the instructor says so
    new = svc.find_user(db, net_id="NEW11111")
    assert new.net_id == "new11111" and new.email == "new.student@uconn.edu"

    assert drop_students(db, course, [u.id for u in res.missing] + [s1.id + 999], by=prof) == 1
    assert not svc.is_enrolled(db, course, s2) and svc.is_enrolled(db, course, s1)
    assert drop_students(db, course, [s2.id], by=prof) == 0  # already dropped

    # The student logs in through CAS later and is matched to the imported row.
    u = svc.record_login(db, net_id="new11111", email="new11111@uconn.edu")
    assert u is new
