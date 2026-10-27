"""Participation grade export.

Totals come from the v_poll_scores view (one row per active student x closed
poll). The grade file has one row per student and one column per lecture date
that had a closed poll:

    Username,W1-09-04-PART,W2-09-11-PART,...
    ABC12345,100,0,...

The Username is the student's NetID in capitals. Each PART column is 100 when
the student answered at least one poll on that date, and 0 when they answered
none. The W## prefix counts the first lecture of the course as week 1.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import Course, User
from .services import log_event


def participation_totals(
    db: Session, course: Course, start: dt.date | None = None, end: dt.date | None = None
) -> list[dict]:
    sql = text("""
        SELECT u.last_name, u.first_name, u.net_id, u.student_id, u.email,
               COUNT(v.poll_id)            AS polls,
               COALESCE(SUM(v.answered),0) AS answered,
               0                          AS correct,
               COALESCE(SUM(v.points),0)   AS points,
               COALESCE(SUM(v.points_possible),0) AS points_possible
        FROM enrollments e
        JOIN users u ON u.id = e.user_id
        LEFT JOIN v_poll_scores v
               ON v.user_id = e.user_id AND v.course_id = e.course_id
              AND (:start IS NULL OR v.session_date >= :start)
              AND (:end   IS NULL OR v.session_date <= :end)
        WHERE e.course_id = :course_id AND e.status = 'active'
        GROUP BY u.id
        ORDER BY u.last_name COLLATE NOCASE, u.first_name COLLATE NOCASE, u.net_id
    """)
    return [dict(r._mapping) for r in db.execute(
        sql, {"course_id": course.id,
              "start": start.isoformat() if start else None,
              "end": end.isoformat() if end else None})]


def _as_date(value: dt.date | str) -> dt.date:
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(value)


def _first_lecture(db: Session, course: Course) -> dt.date | None:
    first = db.execute(text(
        "SELECT MIN(session_date) FROM lecture_sessions WHERE course_id = :cid"
    ), {"cid": course.id}).scalar()
    return _as_date(first) if first is not None else None


def _participation_dates(db: Session, course: Course) -> list[dt.date]:
    """Dates of lectures that have at least one closed poll, oldest first."""
    return [_as_date(d) for d in db.scalars(text("""
        SELECT DISTINCT s.session_date
        FROM lecture_sessions s JOIN polls p ON p.session_id = s.id
        WHERE s.course_id = :cid AND p.status = 'closed'
        ORDER BY s.session_date
    """), {"cid": course.id})]


def _participation_column(session_date: dt.date, first_lecture: dt.date) -> str:
    week = (session_date - first_lecture).days // 7 + 1
    return f"W{week}-{session_date.month:02d}-{session_date.day:02d}-PART"


def participation_sessions(db: Session, course: Course) -> list[dict]:
    """The date columns available for the participation CSV."""
    first_lecture = _first_lecture(db, course)
    if first_lecture is None:
        return []
    return [{"date": d, "column": _participation_column(d, first_lecture)}
            for d in _participation_dates(db, course)]


def participation_csv(
    db: Session, course: Course, *, by: User | None = None, dates: Iterable[dt.date] | None = None
) -> str:
    """Participation sheet: 100 per lecture date answered, 0 for no answers.

    Pass `dates` to include only those lecture dates; omit it for every date.
    """
    students = db.execute(text("""
        SELECT u.id, u.net_id
        FROM enrollments e JOIN users u ON u.id = e.user_id
        WHERE e.course_id = :cid AND e.status = 'active'
        ORDER BY u.last_name COLLATE NOCASE, u.first_name COLLATE NOCASE, u.net_id
    """), {"cid": course.id}).all()

    first_lecture = _first_lecture(db, course)
    session_dates = _participation_dates(db, course)
    if dates is not None:
        wanted = set(dates)
        session_dates = [d for d in session_dates if d in wanted]

    answered = {
        (r.user_id, _as_date(r.session_date)): r.answered
        for r in db.execute(text("""
            SELECT v.user_id, v.session_date, MAX(v.answered) AS answered
            FROM v_poll_scores v
            WHERE v.course_id = :cid
            GROUP BY v.user_id, v.session_date
        """), {"cid": course.id})
    }

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Username"] + [_participation_column(d, first_lecture) for d in session_dates])
    for student in students:
        w.writerow([(student.net_id or "").upper()]
                    + ["100" if answered.get((student.id, d)) else "0" for d in session_dates])

    log_event(db, "export_participation", user=by, course=course,
              students=len(students), sessions=len(session_dates))
    return buf.getvalue()
