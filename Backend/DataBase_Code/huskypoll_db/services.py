"""Database operations the FastAPI routes will call.

Each function takes an open SQLAlchemy Session and does NOT commit: the caller
(one API request = one transaction) commits, which keeps write transactions
short - important with SQLite's single writer.
"""
from __future__ import annotations

import datetime as dt
import math
import re
import secrets
from typing import Iterable, Optional, Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .models import (
    Course,
    CourseInstructor,
    Enrollment,
    EventLog,
    LectureSession,
    Poll,
    Question,
    QuestionBank,
    QuestionOption,
    Response,
    ResponseChoice,
    User,
    utcnow,
)

# Codes students type or scan; no 0/O/1/I/L to avoid misreads on a projector.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
STUDENT_ID_RE = re.compile(r"^\d{7,9}$")
NETID_RE = re.compile(r"^[a-z]{3}[0-9]{5}$")  # UConn NetID, e.g. abc12345 (matches models.NETID_GLOB)

# Emails allowed to log in (checked case-insensitively, stored lowercase):
#   firstname.lastname@uconn.edu            e.g. jonathan.smith@uconn.edu
#   firstname.middleinitial.lastname@...    e.g. jonathan.q.smith@uconn.edu
#   netid@uconn.edu                         e.g. abc12345@uconn.edu
# Name parts are letters, optionally joined by hyphens (mary-kate, smith-jones).
_NAME = r"[a-z]+(?:-[a-z]+)*"
LOGIN_EMAIL_RE = re.compile(
    rf"^(?:(?P<first>{_NAME})\.(?:(?P<middle>[a-z])\.)?(?P<last>{_NAME})|(?P<netid>[a-z]{{3}}[0-9]{{5}}))@uconn\.edu$"
)


class HuskyPollError(Exception):
    """A rule was broken (not enrolled, poll closed, ...). Map to HTTP 4xx in the API."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _lower(value: Optional[str]) -> Optional[str]:
    value = _clean(value)
    return value.lower() if value else None


def _count(db: Session, model, *where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where)) or 0


def new_code(length: int = 6) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def log_event(
    db: Session,
    event_type: str,
    *,
    user: Optional[User] = None,
    course: Optional[Course] = None,
    poll: Optional[Poll] = None,
    ip_address: Optional[str] = None,
    **details,
) -> EventLog:
    entry = EventLog(
        event_type=event_type,
        user_id=user.id if user else None,
        course_id=course.id if course else None,
        poll_id=poll.id if poll else None,
        ip_address=ip_address,
        details_json=details or None,
    )
    db.add(entry)
    return entry


# ---------------------------------------------------------------------------
# Users and login
# ---------------------------------------------------------------------------

def normalize_net_id(net_id: Optional[str]) -> Optional[str]:
    """Trim and lowercase a NetID; raise HuskyPollError if it isn't 3 letters + 5 digits."""
    value = _lower(net_id)
    if value is not None and not NETID_RE.match(value):
        raise HuskyPollError(f"'{str(net_id).strip()}' is not a valid NetID (3 letters followed by 5 numbers, e.g. abc12345)")
    return value


def is_valid_net_id(net_id: Optional[str]) -> bool:
    return bool(net_id) and bool(NETID_RE.match(str(net_id).strip().lower()))


def find_user(
    db: Session,
    *,
    net_id: Optional[str] = None,
    email: Optional[str] = None,
    student_id: Optional[str] = None,
) -> Optional[User]:
    """Match by NetID, then student ID, then email (most to least reliable)."""
    for column, value in (
        (User.net_id, _lower(net_id)),
        (User.student_id, _clean(student_id)),
        (User.email, _lower(email)),
    ):
        if value:
            user = db.scalar(select(User).where(column == value))
            if user:
                return user
    return None


def find_or_create_user(
    db: Session,
    *,
    net_id: Optional[str] = None,
    email: Optional[str] = None,
    student_id: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> tuple[User, bool]:
    """Return (user, created). Fills in any identifiers the existing row is missing."""
    net_id, email, student_id = normalize_net_id(net_id), _lower(email), _clean(student_id)
    if not (net_id or email or student_id):
        raise HuskyPollError("need a NetID, email or student ID")

    user = find_user(db, net_id=net_id, email=email, student_id=student_id)
    created = user is None
    if created:
        user = User(net_id=net_id, email=email, student_id=student_id)
        db.add(user)
    else:
        user.net_id = user.net_id or net_id
        user.email = user.email or email
        user.student_id = user.student_id or student_id
    user.first_name = _clean(first_name) or user.first_name
    user.last_name = _clean(last_name) or user.last_name
    db.flush()
    return user, created


def check_login_email(email: Optional[str]) -> tuple[str, Optional[str]]:
    """Validate a login email. Returns (email lowercased, NetID if the email is netid@uconn.edu)."""
    value = _lower(email)
    m = LOGIN_EMAIL_RE.match(value or "")
    if not m:
        raise HuskyPollError(
            "Only UConn emails can log in: firstname.lastname@uconn.edu, "
            "firstname.middleinitial.lastname@uconn.edu or netid@uconn.edu"
        )
    return value, m.group("netid")


def record_login(
    db: Session,
    *,
    email: str,
    net_id: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    student_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> User:
    """Call after CAS/Entra authenticates someone. Links them to any roster row.

    Anyone whose email is firstname.lastname@, firstname.m.lastname@ or
    netid@uconn.edu may log in, and every logged-in user ends up with a NetID:
    the one UConn login supplies, or the one in a netid@uconn.edu email.
    """
    email, email_netid = check_login_email(email)
    net_id = normalize_net_id(net_id)
    if net_id and email_netid and net_id != email_netid:
        raise HuskyPollError(f"email {email} does not belong to NetID {net_id}")
    net_id = net_id or email_netid
    if not net_id:
        raise HuskyPollError(
            f"could not determine a NetID for {email}; UConn login must supply one "
            "(or log in with netid@uconn.edu)"
        )
    existing = find_user(db, email=email)
    if existing and existing.net_id and existing.net_id != net_id:
        raise HuskyPollError(f"email {email} already belongs to a different NetID")

    user, created = find_or_create_user(
        db, net_id=net_id, email=email, student_id=student_id, first_name=first_name, last_name=last_name
    )
    user.last_login_at = utcnow()
    log_event(db, "login", user=user, ip_address=ip_address, first_login=created)
    return user


# ---------------------------------------------------------------------------
# Courses, instructors, rosters
# ---------------------------------------------------------------------------

def create_course(
    db: Session,
    creator: User,
    *,
    term: str,
    subject: str,
    catalog: str,
    title: str,
    section: Optional[str] = None,
    points_participation: float = 1.0,
    points_correct: float = 0.0,
) -> Course:
    course = Course(
        term=term.strip(),
        subject=subject.strip().upper(),
        catalog=catalog.strip().upper(),
        section=_clean(section),
        title=title.strip(),
        join_code=_unique_join_code(db),
        points_participation=points_participation,
        points_correct=points_correct,
        created_by=creator.id,
    )
    course.instructors.append(CourseInstructor(user_id=creator.id, role="owner"))
    db.add(course)
    db.flush()
    log_event(db, "course_create", user=creator, course=course)
    return course


def _unique_join_code(db: Session) -> str:
    while True:
        code = new_code(6)
        if not db.scalar(select(Course.id).where(Course.join_code == code)):
            return code


def is_owner(db: Session, course: Course, user: User) -> bool:
    link = db.get(CourseInstructor, (course.id, user.id))
    return user.is_admin or (link is not None and link.role == "owner")


def archive_course(db: Session, course: Course, by: User) -> Course:
    """End-of-semester option 1: hide the course but keep everything (reversible)."""
    if not is_instructor(db, course, by):
        raise HuskyPollError("only an instructor of this course can archive it")
    course.archived_at = utcnow()
    db.flush()
    log_event(db, "course_archive", user=by, course=course)
    return course


def unarchive_course(db: Session, course: Course, by: User) -> Course:
    if not is_instructor(db, course, by):
        raise HuskyPollError("only an instructor of this course can restore it")
    course.archived_at = None
    db.flush()
    log_event(db, "course_unarchive", user=by, course=course)
    return course


def delete_course(db: Session, course: Course, by: User, *, delete_logs: bool = False) -> dict:
    """End-of-semester option 2: permanently delete a course. Cannot be undone.

    Deleted: the roster, instructor list, lecture sessions, polls, and every
    student answer in the course.
    Kept: question banks and questions (so they can be reused next semester),
    user accounts, and the event log - unless delete_logs=True, which also
    removes the course's log entries.

    Only the course owner (or an admin) may do this. Export grades first.
    """
    if not is_owner(db, course, by):
        raise HuskyPollError("only the course owner can delete a course")

    # Count with queries, not loaded collections, so the numbers are always current.
    poll_ids = list(db.scalars(
        select(Poll.id).join(LectureSession).where(LectureSession.course_id == course.id)))
    summary = {
        "course_code": course.code,
        "students": _count(db, Enrollment, Enrollment.course_id == course.id),
        "sessions": _count(db, LectureSession, LectureSession.course_id == course.id),
        "polls": len(poll_ids),
        "responses": _count(db, Response, Response.poll_id.in_(poll_ids)) if poll_ids else 0,
    }
    if delete_logs:
        db.execute(delete(EventLog).where(EventLog.course_id == course.id))
        if poll_ids:
            db.execute(delete(EventLog).where(EventLog.poll_id.in_(poll_ids)))
    db.delete(course)
    db.flush()
    # Logged without a course link (the course no longer exists); the summary says what went.
    log_event(db, "course_delete", user=by, deleted_logs=delete_logs, **summary)
    return summary


def add_instructor(db: Session, course: Course, user: User, role: str = "instructor") -> CourseInstructor:
    link = db.get(CourseInstructor, (course.id, user.id))
    if link is None:
        link = CourseInstructor(course_id=course.id, user_id=user.id, role=role)
        db.add(link)
    else:
        link.role = role
    db.flush()
    return link


def is_instructor(db: Session, course: Course, user: User) -> bool:
    return db.get(CourseInstructor, (course.id, user.id)) is not None or user.is_admin


def enroll(
    db: Session, course: Course, user: User, *, source: str = "manual", section: Optional[str] = None
) -> tuple[Enrollment, str]:
    """Add or re-activate a student. Returns (enrollment, 'added'|'reactivated'|'unchanged')."""
    enr = db.get(Enrollment, (course.id, user.id))
    if enr is None:
        enr = Enrollment(course_id=course.id, user_id=user.id, source=source, section=_clean(section))
        db.add(enr)
        outcome = "added"
    elif enr.status != "active":
        enr.status = "active"
        outcome = "reactivated"
    else:
        outcome = "unchanged"
    if section:
        enr.section = _clean(section)
    db.flush()
    return enr, outcome


def is_enrolled(db: Session, course: Course, user: User) -> bool:
    enr = db.get(Enrollment, (course.id, user.id))
    return enr is not None and enr.status == "active"


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------

def create_question(
    db: Session,
    author: User,
    *,
    type: str,
    body_md: str,
    options: Sequence[tuple[str, bool]] = (),
    bank: Optional[QuestionBank] = None,
    explanation_md: Optional[str] = None,
    text_answer: Optional[str] = None,
    numeric_answer: Optional[float] = None,
    numeric_tolerance: Optional[float] = None,
) -> Question:
    """Create a question. `options` is [(text, is_correct), ...] for multiple choice.

    A quick in-lecture question can leave the answer out and have it added later.
    """
    if type in ("mc_single", "mc_multi") and len(options) < 2:
        raise HuskyPollError("multiple-choice questions need at least two options")
    if type == "mc_single" and sum(1 for _, ok in options if ok) > 1:
        raise HuskyPollError("single-answer question can have at most one correct option")
    q = Question(
        author_id=author.id,
        bank_id=bank.id if bank else None,
        type=type,
        body_md=body_md,
        explanation_md=explanation_md,
        text_answer=text_answer,
        numeric_answer=numeric_answer,
        numeric_tolerance=numeric_tolerance,
    )
    q.options = [QuestionOption(position=i, text_md=t, is_correct=ok) for i, (t, ok) in enumerate(options)]
    db.add(q)
    db.flush()
    return q


def copy_question(db: Session, source: Question, author: User, bank: Optional[QuestionBank] = None) -> Question:
    """Editable copy of a (possibly locked) question - for edits and for reuse in a new term."""
    q = Question(
        author_id=author.id,
        bank_id=(bank.id if bank else source.bank_id),
        type=source.type,
        body_md=source.body_md,
        body_media_id=source.body_media_id,
        explanation_md=source.explanation_md,
        explanation_media_id=source.explanation_media_id,
        text_answer=source.text_answer,
        numeric_answer=source.numeric_answer,
        numeric_tolerance=source.numeric_tolerance,
        copied_from_id=source.id,
    )
    q.options = [
        QuestionOption(position=o.position, text_md=o.text_md, media_id=o.media_id, is_correct=o.is_correct)
        for o in source.options
    ]
    db.add(q)
    db.flush()
    return q


def copy_bank(db: Session, source: QuestionBank, owner: User, *, name: str, course: Optional[Course] = None) -> QuestionBank:
    """Copy a whole question bank, e.g. last semester's bank into this semester's course."""
    bank = QuestionBank(owner_id=owner.id, course_id=course.id if course else None, name=name,
                        description=source.description)
    db.add(bank)
    db.flush()
    for q in source.questions:
        copy_question(db, q, owner, bank=bank)
    return bank


# ---------------------------------------------------------------------------
# Lecture sessions and polls
# ---------------------------------------------------------------------------

def get_or_create_session(
    db: Session, course: Course, *, on_date: Optional[dt.date] = None, title: Optional[str] = None
) -> LectureSession:
    """Today's lecture session for the course, auto-creating it on the first poll of the day."""
    on_date = on_date or dt.date.today()
    sess = db.scalar(
        select(LectureSession)
        .where(LectureSession.course_id == course.id, LectureSession.session_date == on_date)
        .order_by(LectureSession.id.desc())
    )
    if sess is None:
        sess = LectureSession(
            session_date=on_date,
            title=title or f"Lecture {on_date:%b %d}",
            started_at=utcnow(),
            is_auto=title is None,
        )
        course.sessions.append(sess)  # keeps course.sessions up to date in this session
        db.flush()
    return sess


def open_poll(
    db: Session,
    course: Course,
    question: Question,
    opened_by: User,
    *,
    lecture_session: Optional[LectureSession] = None,
    show_results: bool = False,
) -> Poll:
    """Open a poll on a question (from a bank, or just created in lecture)."""
    if not is_instructor(db, course, opened_by):
        raise HuskyPollError("only an instructor of this course can open polls")
    sess = lecture_session or get_or_create_session(db, course)
    if sess.course_id != course.id:
        raise HuskyPollError("lecture session belongs to another course")
    poll = Poll(
        question_id=question.id,
        access_code=_unique_open_access_code(db),
        status="open",
        position=_count(db, Poll, Poll.session_id == sess.id),
        show_results=show_results,
        opened_by=opened_by.id,
        opened_at=utcnow(),
    )
    sess.polls.append(poll)
    db.flush()  # trigger locks the question here
    db.refresh(question)
    log_event(db, "poll_open", user=opened_by, course=course, poll=poll, question_id=question.id)
    return poll


def _unique_open_access_code(db: Session) -> str:
    while True:
        code = new_code(5)
        if not db.scalar(select(Poll.id).where(Poll.access_code == code, Poll.status == "open")):
            return code


def close_poll(db: Session, poll: Poll, closed_by: User) -> Poll:
    if poll.status != "open":
        raise HuskyPollError("poll is not open")
    poll.status = "closed"
    poll.closed_at = utcnow()
    db.flush()
    log_event(db, "poll_close", user=closed_by, course=poll.session.course, poll=poll,
              responses=_count(db, Response, Response.poll_id == poll.id))
    return poll


def find_open_poll_by_code(db: Session, access_code: str) -> Optional[Poll]:
    return db.scalar(select(Poll).where(Poll.access_code == access_code.strip().upper(), Poll.status == "open"))


# ---------------------------------------------------------------------------
# Responses and grading
# ---------------------------------------------------------------------------

def grade(
    question: Question,
    option_ids: Iterable[int] = (),
    text_answer: Optional[str] = None,
    numeric_answer: Optional[float] = None,
) -> Optional[bool]:
    """True/False if the question has an answer key, None if it does not."""
    if question.type in ("mc_single", "mc_multi"):
        correct = {o.id for o in question.options if o.is_correct}
        if not correct:
            return None
        return set(option_ids) == correct
    if question.type == "numeric":
        if question.numeric_answer is None:
            return None
        if numeric_answer is None:
            return False
        tol = question.numeric_tolerance or 0.0
        return math.isclose(numeric_answer, question.numeric_answer, rel_tol=0.0, abs_tol=max(tol, 1e-9))
    if question.type == "free_text":
        if not question.text_answer:
            return None
        return (text_answer or "").strip().casefold() == question.text_answer.strip().casefold()
    return None


def submit_response(
    db: Session,
    poll: Poll,
    student: User,
    *,
    option_ids: Sequence[int] = (),
    text_answer: Optional[str] = None,
    numeric_answer: Optional[float] = None,
    ip_address: Optional[str] = None,
) -> Response:
    """Record (or replace) a student's answer. The returned row is the confirmation."""
    course = poll.session.course
    if poll.status != "open":
        raise HuskyPollError("this poll is closed")
    if not is_enrolled(db, course, student):
        raise HuskyPollError("you are not on the roster for this course")

    q = poll.question
    valid = {o.id for o in q.options}
    if q.type in ("mc_single", "mc_multi"):
        if not option_ids or not set(option_ids) <= valid:
            raise HuskyPollError("choose one of the listed options")
        if q.type == "mc_single" and len(set(option_ids)) != 1:
            raise HuskyPollError("choose exactly one option")
    elif q.type == "numeric" and numeric_answer is None:
        raise HuskyPollError("enter a number")
    elif q.type == "free_text" and not _clean(text_answer):
        raise HuskyPollError("enter an answer")

    resp = db.scalar(select(Response).where(Response.poll_id == poll.id, Response.user_id == student.id))
    is_update = resp is not None
    if resp is None:
        resp = Response(poll_id=poll.id, user_id=student.id)
        db.add(resp)
    resp.text_answer = _clean(text_answer) if q.type == "free_text" else None
    resp.numeric_answer = numeric_answer if q.type == "numeric" else None
    resp.is_correct = grade(q, option_ids, text_answer, numeric_answer)
    resp.choices.clear()
    db.flush()
    for oid in dict.fromkeys(option_ids):  # de-duplicate, keep order
        resp.choices.append(ResponseChoice(option_id=oid))
    db.flush()
    log_event(db, "response_update" if is_update else "response_submit", user=student, course=course,
              poll=poll, ip_address=ip_address)
    return resp


def regrade_poll(db: Session, poll: Poll) -> int:
    """Re-mark every response after the answer key was added or fixed. Returns count changed."""
    db.refresh(poll.question)
    changed = 0
    for resp in db.scalars(select(Response).where(Response.poll_id == poll.id)):
        new = grade(poll.question, [c.option_id for c in resp.choices], resp.text_answer, resp.numeric_answer)
        if new != resp.is_correct:
            resp.is_correct = new
            changed += 1
    db.flush()
    return changed
