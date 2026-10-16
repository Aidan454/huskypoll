"""Shared FastAPI dependencies: database session, current user, permission checks."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from app.database import services as svc
from app.database.models import (
    Course,
    CourseInstructor,
    LectureSession,
    Poll,
    Question,
    User,
)
from sqlalchemy.orm import Session

from .config import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    """One request = one transaction. Commits at the end (rolls back on any error),
    then runs after-commit callbacks such as live-update broadcasts."""
    db: Session = request.app.state.session_factory()
    request.state.after_commit = []
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()
    for fn in request.state.after_commit:
        fn()


def after_commit(request: Request, fn: Callable[[], None]) -> None:
    """Run fn only if (and after) this request's changes are saved."""
    request.state.after_commit.append(fn)


def optional_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    user = db.get(User, user_id)
    if user is None:
        request.session.clear()
    return user


def current_user(user: User | Annotated[User | None, Depends(optional_user)]) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    return user


# --- loading things by id, with permission checks -----------------------------

def course_or_404(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(404, "Course not found")
    return course


def role_in(db: Session, course: Course, user: User) -> str | None:
    """'owner' | 'instructor' | 'ta' | 'student' | None (admins count as owner)."""
    link = db.get(CourseInstructor, (course.id, user.id))
    if link is not None:
        return link.role
    if user.is_admin:
        return "owner"
    if svc.is_enrolled(db, course, user):
        return "student"
    return None


def require_staff(user: User) -> None:
    """Admins, instructors and TAs (account role) - e.g. to write questions or upload images."""
    if not user.is_staff:
        raise HTTPException(403, "Only instructors, TAs and admins can do this")


def require_admin(user: User) -> None:
    if not user.is_admin:
        raise HTTPException(403, "Only admins can do this")


def require_instructor(db: Session, course: Course, user: User) -> None:
    if not svc.is_instructor(db, course, user):
        raise HTTPException(403, "Only instructors of this course can do this")


def require_member(db: Session, course: Course, user: User) -> str:
    role = role_in(db, course, user)
    if role is None:
        # Hide that the course exists from people who aren't in it.
        raise HTTPException(404, "Course not found")
    return role


def session_or_404(db: Session, session_id: int) -> LectureSession:
    sess = db.get(LectureSession, session_id)
    if sess is None:
        raise HTTPException(404, "Lecture session not found")
    return sess


def poll_or_404(db: Session, poll_id: int) -> Poll:
    poll = db.get(Poll, poll_id)
    if poll is None:
        raise HTTPException(404, "Poll not found")
    return poll


def question_or_404(db: Session, question_id: int) -> Question:
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(404, "Question not found")
    return q


def can_manage_question(db: Session, q: Question, user: User) -> bool:
    """Author, admin, an instructor of the bank's course, or of a course that polled it."""
    if user.is_admin or q.author_id == user.id:
        return True
    if q.bank is not None and q.bank.course_id is not None:
        course = db.get(Course, q.bank.course_id)
        if course is not None and svc.is_instructor(db, course, user):
            return True
    for poll in db.query(Poll).filter(Poll.question_id == q.id):
        if svc.is_instructor(db, poll.session.course, user):
            return True
    return False


def require_question_access(db: Session, q: Question, user: User) -> None:
    if not can_manage_question(db, q, user):
        raise HTTPException(404, "Question not found")
