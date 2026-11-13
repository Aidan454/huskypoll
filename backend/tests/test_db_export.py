"""Participation export totals, CSV columns and export timestamps.

Run with: python -m pytest -q tests/test_db_export.py
"""

from __future__ import annotations

import datetime as dt

from app.database import services as svc
from app.database.export import (
    participation_csv,
    participation_sessions,
    participation_totals,
)


def test_participation_export(db, course_setup):
    prof, course, s1, s2, q = course_setup
    sess = svc.get_or_create_session(db, course, on_date=dt.date(2027, 2, 1))
    poll = svc.open_poll(db, course, q, prof, lecture_session=sess)
    svc.submit_response(db, poll, s1, option_ids=[q.options[1].id])  # correct
    svc.close_poll(db, poll, prof)
    open_poll = svc.open_poll(db, course, q, prof, lecture_session=sess)  # still open: not counted
    svc.submit_response(db, open_poll, s2, option_ids=[q.options[1].id])

    totals = {r["net_id"]: r for r in participation_totals(db, course)}
    # Participation is one point per answered closed poll; correctness no longer adds points.
    assert totals["abc12345"]["points"] == 1 and totals["abc12345"]["points_possible"] == 1
    assert totals["abc12345"]["answered"] == 1 and totals["abc12345"]["correct"] == 0
    assert totals["xyz67890"]["points"] == 0 and totals["xyz67890"]["polls"] == 1

    next_week = svc.get_or_create_session(db, course, on_date=dt.date(2027, 2, 8))
    week2_poll = svc.open_poll(db, course, q, prof, lecture_session=next_week)
    svc.submit_response(db, week2_poll, s2, option_ids=[q.options[1].id])
    svc.close_poll(db, week2_poll, prof)

    lines = participation_csv(db, course).splitlines()
    assert lines[0] == "Username,W1-02-01-PART,W2-02-08-PART"
    assert lines[1] == "ABC12345,100,0"
    assert lines[2] == "XYZ67890,0,100"

    filtered = participation_csv(db, course, dates=[dt.date(2027, 2, 8)]).splitlines()
    assert filtered[0] == "Username,W2-02-08-PART"
    assert filtered[1] == "ABC12345,0"
    assert filtered[2] == "XYZ67890,100"

    # Both dates have been exported; a new lecture date has not.
    third = svc.get_or_create_session(db, course, on_date=dt.date(2027, 2, 15))
    svc.close_poll(db, svc.open_poll(db, course, q, prof, lecture_session=third), prof)
    db.flush()
    sessions = participation_sessions(db, course)
    assert [(x["date"], x["column"]) for x in sessions] == [
        (dt.date(2027, 2, 1), "W1-02-01-PART"),
        (dt.date(2027, 2, 8), "W2-02-08-PART"),
        (dt.date(2027, 2, 15), "W3-02-15-PART"),
    ]
    assert [x["exported_at"] is not None for x in sessions] == [True, True, False]
    assert sessions[0]["exported_at"].tzinfo is not None

    assert participation_totals(db, course, start=dt.date(2027, 3, 1))[0]["points"] == 0
