"""Courses, instructors, rosters, lecture sessions, exports and the course event log."""
from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response as RawResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from huskypoll_db import services as svc
from huskypoll_db.export import participation_totals, per_session_csv, write_huskyct_csv
from huskypoll_db.models import Course, CourseInstructor, Enrollment, EventLog, LectureSession, User
from huskypoll_db.roster import import_identifiers, import_records, import_studentadmin_xlsx

from .. import schemas as s
from ..deps import course_or_404, current_user, get_db, require_instructor, require_member, role_in, session_or_404
from ..serializers import course_out, instructor_out, roster_out, session_out

router = APIRouter(tags=["courses"])

MAX_ROSTER_BYTES = 5 * 1024 * 1024


def _import_out(res) -> s.ImportResultOut:
    return s.ImportResultOut(
        users_created=res.users_created, users_matched=res.users_matched, enrolled=res.enrolled,
        reactivated=res.reactivated, unchanged=res.unchanged, dropped=res.dropped,
        skipped=[{"row": r, "reason": why} for r, why in res.skipped], summary=res.summary())


def _find_by_identifier(db: Session, identifier: str) -> Optional[User]:
    ident = identifier.strip()
    if "@" in ident:
        return svc.find_user(db, email=ident)
    if svc.STUDENT_ID_RE.match(ident):
        return svc.find_user(db, student_id=ident)
    return svc.find_user(db, net_id=ident.lower())


# --- courses ------------------------------------------------------------------

@router.get("/courses", response_model=list[s.CourseOut], summary="My courses (teaching and enrolled)")
def my_courses(include_archived: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)):
    teaching = {ci.course_id: ci.role for ci in db.scalars(
        select(CourseInstructor).where(CourseInstructor.user_id == user.id))}
    enrolled = set(db.scalars(select(Enrollment.course_id).where(
        Enrollment.user_id == user.id, Enrollment.status == "active")))
    ids = set(teaching) | enrolled
    courses = db.scalars(select(Course).where(Course.id.in_(ids)).order_by(Course.created_at.desc())).all() if ids else []
    return [course_out(c, teaching.get(c.id, "student")) for c in courses
            if include_archived or c.archived_at is None]


@router.post("/courses", response_model=s.CourseOut, status_code=201, summary="Create a course (you become its owner)")
def create_course(body: s.CourseCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = svc.create_course(db, user, **body.model_dump())
    return course_out(c, "owner")


@router.get("/courses/{course_id}", response_model=s.CourseOut)
def get_course(course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    return course_out(c, require_member(db, c, user))


@router.patch("/courses/{course_id}", response_model=s.CourseOut)
def update_course(course_id: int, body: s.CourseUpdate, db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_member(db, c, user)
    svc.update_course(db, c, user, **body.model_dump(exclude_unset=True))
    return course_out(c, role_in(db, c, user))


@router.post("/courses/{course_id}/archive", response_model=s.CourseOut, summary="Hide a finished course (keeps everything)")
def archive_course(course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_member(db, c, user)
    svc.archive_course(db, c, user)
    return course_out(c, role_in(db, c, user))


@router.post("/courses/{course_id}/unarchive", response_model=s.CourseOut)
def unarchive_course(course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_member(db, c, user)
    svc.unarchive_course(db, c, user)
    return course_out(c, role_in(db, c, user))


@router.delete("/courses/{course_id}", response_model=s.DeleteCourseOut,
               summary="Permanently delete a course (owner only; export grades first)")
def delete_course(course_id: int, delete_logs: bool = False, db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_member(db, c, user)
    return svc.delete_course(db, c, user, delete_logs=delete_logs)


# --- instructors ---------------------------------------------------------------

@router.get("/courses/{course_id}/instructors", response_model=list[s.InstructorOut])
def list_instructors(course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_member(db, c, user)
    return [instructor_out(link) for link in c.instructors]


@router.post("/courses/{course_id}/instructors", response_model=s.InstructorOut, status_code=201,
             summary="Add an instructor or TA (owner only)")
def add_instructor(course_id: int, body: s.InstructorAdd, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_instructor(db, c, user)
    if not svc.is_owner(db, c, user):
        raise HTTPException(403, "Only the course owner can add instructors")
    ident = body.identifier.strip()
    other = _find_by_identifier(db, ident)
    if other is None:
        # Not logged in yet: create the account from the NetID/email so they can be added now.
        other, _ = svc.find_or_create_user(db, **({"email": ident} if "@" in ident else {"net_id": ident}))
    link = svc.add_instructor(db, c, other, role=body.role)
    svc.log_event(db, "instructor_add", user=user, course=c, added_user_id=other.id, role=body.role)
    return instructor_out(link)


@router.delete("/courses/{course_id}/instructors/{user_id}", status_code=204)
def remove_instructor(course_id: int, user_id: int, db: Session = Depends(get_db),
                      user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_instructor(db, c, user)
    other = db.get(User, user_id)
    if other is None:
        raise HTTPException(404, "User not found")
    svc.remove_instructor(db, c, other, user)


# --- roster ---------------------------------------------------------------------

@router.get("/courses/{course_id}/roster", response_model=list[s.RosterEntryOut])
def get_roster(course_id: int, include_dropped: bool = False, db: Session = Depends(get_db),
               user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_instructor(db, c, user)
    rows = [e for e in c.enrollments if include_dropped or e.status == "active"]
    rows.sort(key=lambda e: ((e.user.last_name or "").lower(), (e.user.first_name or "").lower(), e.user.net_id or ""))
    return [roster_out(e) for e in rows]


@router.post("/courses/{course_id}/roster", response_model=s.ImportResultOut, status_code=201,
             summary="Add one student by NetID, email or student ID")
def add_student(course_id: int, body: s.RosterAdd, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_instructor(db, c, user)
    ident = body.identifier.strip()
    key = "email" if "@" in ident else "student_id" if svc.STUDENT_ID_RE.match(ident) else "net_id"
    rec = {key: ident, "first_name": body.first_name, "last_name": body.last_name, "section": body.section, "_row": 1}
    res = import_records(db, c, [rec], by=user)
    if res.skipped:
        raise HTTPException(400, res.skipped[0][1])
    return _import_out(res)


@router.post("/courses/{course_id}/roster/paste", response_model=s.ImportResultOut,
             summary="Add many students from pasted NetIDs / emails / student IDs")
def paste_roster(course_id: int, body: s.RosterPaste, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_instructor(db, c, user)
    return _import_out(import_identifiers(db, c, body.text, by=user))


@router.post("/courses/{course_id}/roster/import", response_model=s.ImportResultOut,
             summary="Import a StudentAdmin class roster (.xlsx)")
def import_roster(course_id: int, file: UploadFile = File(...), drop_missing: bool = False,
                  db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_instructor(db, c, user)
    data = file.file.read(MAX_ROSTER_BYTES + 1)
    if len(data) > MAX_ROSTER_BYTES:
        raise HTTPException(413, "Roster file is too large (5 MB max)")
    if not data.startswith(b"PK"):
        raise HTTPException(400, "Please upload the roster as an .xlsx file")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "roster.xlsx"
        path.write_bytes(data)
        try:
            res = import_studentadmin_xlsx(db, c, path, drop_missing=drop_missing, by=user)
        except svc.HuskyPollError:
            raise
        except Exception:
            raise HTTPException(400, "Could not read that spreadsheet; is it the StudentAdmin roster .xlsx?")
    return _import_out(res)


@router.delete("/courses/{course_id}/roster/{user_id}", status_code=204,
               summary="Drop a student (their past answers are kept)")
def drop_student(course_id: int, user_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_instructor(db, c, user)
    other = db.get(User, user_id)
    if other is None:
        raise HTTPException(404, "User not found")
    svc.drop_student(db, c, other, user)


# --- lecture sessions ---------------------------------------------------------

@router.get("/courses/{course_id}/sessions", response_model=list[s.SessionOut])
def list_sessions(course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_member(db, c, user)
    sessions = db.scalars(select(LectureSession).where(LectureSession.course_id == c.id)
                          .order_by(LectureSession.session_date.desc(), LectureSession.id.desc()))
    return [session_out(db, x) for x in sessions]


@router.post("/courses/{course_id}/sessions", response_model=s.SessionOut, status_code=201)
def create_session(course_id: int, body: s.SessionCreate, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_instructor(db, c, user)
    return session_out(db, svc.create_session(db, c, title=body.title, on_date=body.session_date))


@router.patch("/sessions/{session_id}", response_model=s.SessionOut)
def update_session(session_id: int, body: s.SessionUpdate, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    sess = session_or_404(db, session_id)
    require_instructor(db, sess.course, user)
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(sess, key, value)
    sess.is_auto = False
    db.flush()
    return session_out(db, sess)


@router.delete("/sessions/{session_id}", status_code=204, summary="Delete an empty lecture session")
def delete_session(session_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    sess = session_or_404(db, session_id)
    require_instructor(db, sess.course, user)
    if sess.polls:
        raise HTTPException(400, "Move or keep its polls: only empty sessions can be deleted")
    db.delete(sess)


# --- exports, participation, events ------------------------------------------

@router.get("/courses/{course_id}/export/huskyct.csv", response_class=RawResponse,
            summary="Participation grades for HuskyCT")
def export_huskyct(course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_instructor(db, c, user)
    buf = io.StringIO()
    write_huskyct_csv(db, c, buf, by=user)
    name = f"{c.subject}{c.catalog}-{c.term}-huskypoll.csv".replace(" ", "")
    return RawResponse(buf.getvalue(), media_type="text/csv",
                       headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/courses/{course_id}/export/sessions.csv", response_class=RawResponse,
            summary="Points per student per lecture")
def export_sessions(course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_instructor(db, c, user)
    name = f"{c.subject}{c.catalog}-{c.term}-by-lecture.csv".replace(" ", "")
    return RawResponse(per_session_csv(db, c), media_type="text/csv",
                       headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/courses/{course_id}/participation", response_model=list[dict],
            summary="Every student's totals (instructors)")
def participation(course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_instructor(db, c, user)
    return participation_totals(db, c)


@router.get("/courses/{course_id}/events", response_model=list[s.EventOut], summary="Course activity log")
def course_events(course_id: int, limit: int = 200, before_id: Optional[int] = None,
                  db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = course_or_404(db, course_id)
    require_instructor(db, c, user)
    q = select(EventLog).where(EventLog.course_id == c.id)
    if before_id:
        q = q.where(EventLog.id < before_id)
    events = db.scalars(q.order_by(EventLog.id.desc()).limit(min(limit, 1000))).all()
    users = {u.id: u.net_id for u in db.scalars(select(User).where(User.id.in_({e.user_id for e in events if e.user_id})))}
    return [s.EventOut(id=e.id, occurred_at=e.occurred_at, event_type=e.event_type, net_id=users.get(e.user_id),
                       poll_id=e.poll_id, details=e.details_json) for e in events]
