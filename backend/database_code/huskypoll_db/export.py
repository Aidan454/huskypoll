"""Participation export for HuskyCT.

Totals come from the v_poll_scores view (one row per active student x closed
poll). Two formats:

  * huskyct_summary  - one row per student with a total, for the grade center
  * per_session      - one column per lecture session, for instructors to review

NOTE: confirm the exact column headers HuskyCT expects by downloading a grade
center CSV for a test course; adjust HUSKYCT_ID_COLUMNS if needed.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
from pathlib import Path
from typing import Optional, TextIO

from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import Course, User
from .services import log_event

HUSKYCT_ID_COLUMNS = ["Last Name", "First Name", "Username", "Student ID"]


def _fmt(x: float) -> str:
    return f"{x:g}"


def participation_totals(
    db: Session, course: Course, start: Optional[dt.date] = None, end: Optional[dt.date] = None
) -> list[dict]:
    sql = text("""
        SELECT u.last_name, u.first_name, u.net_id, u.student_id, u.email,
               COUNT(v.poll_id)            AS polls,
               COALESCE(SUM(v.answered),0) AS answered,
               COALESCE(SUM(v.is_correct = 1),0) AS correct,
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


def write_huskyct_csv(
    db: Session,
    course: Course,
    out: TextIO | str | Path,
    *,
    column_name: str = "HuskyPoll Participation",
    start: Optional[dt.date] = None,
    end: Optional[dt.date] = None,
    by: Optional[User] = None,
) -> int:
    """Write one row per student with total points. Returns number of students."""
    rows = participation_totals(db, course, start, end)
    possible = max((r["points_possible"] for r in rows), default=0)
    header = HUSKYCT_ID_COLUMNS + [f"{column_name} [Total Pts: {_fmt(possible)} Score]"]

    def _write(f: TextIO) -> None:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow([r["last_name"] or "", r["first_name"] or "", r["net_id"] or "",
                        r["student_id"] or "", _fmt(r["points"])])

    if isinstance(out, (str, Path)):
        with open(out, "w", newline="", encoding="utf-8") as f:
            _write(f)
    else:
        _write(out)
    log_event(db, "export_huskyct", user=by, course=course, students=len(rows),
              start=str(start) if start else None, end=str(end) if end else None)
    return len(rows)


def per_session_csv(db: Session, course: Course) -> str:
    """Instructor review sheet: students down, lecture sessions across, points in cells."""
    data = db.execute(text("""
        SELECT v.user_id, v.session_id, s.session_date, s.title, SUM(v.points) AS points
        FROM v_poll_scores v JOIN lecture_sessions s ON s.id = v.session_id
        WHERE v.course_id = :cid
        GROUP BY v.user_id, v.session_id
    """), {"cid": course.id}).all()
    students = db.execute(text("""
        SELECT u.id, u.last_name, u.first_name, u.net_id FROM enrollments e JOIN users u ON u.id = e.user_id
        WHERE e.course_id = :cid AND e.status = 'active'
        ORDER BY u.last_name COLLATE NOCASE, u.first_name COLLATE NOCASE
    """), {"cid": course.id}).all()
    sessions = sorted({(d.session_date, d.session_id, d.title) for d in data})
    cell = {(d.user_id, d.session_id): d.points for d in data}

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Last Name", "First Name", "Username"] + [f"{d} {t or ''}".strip() for d, _, t in sessions] + ["Total"])
    for s in students:
        pts = [cell.get((s.id, sid), 0) for _, sid, _ in sessions]
        w.writerow([s.last_name or "", s.first_name or "", s.net_id or ""] + [_fmt(p) for p in pts] + [_fmt(sum(pts))])
    return buf.getvalue()
