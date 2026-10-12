"""Turn database rows into response models, applying who-may-see-what rules."""
from __future__ import annotations

from typing import Optional

from huskypoll_db.models import (
    Course,
    CourseInstructor,
    Enrollment,
    LectureSession,
    Media,
    Poll,
    Question,
    QuestionBank,
    Response,
    User,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import schemas as s
from .config import Settings


def media_url(settings: Settings, media: Optional[Media]) -> Optional[str]:
    return settings.api_url(f"/media/{media.sha256}") if media else None


def user_out(u: User) -> s.UserOut:
    return s.UserOut(id=u.id, net_id=u.net_id, email=u.email, student_id=u.student_id,
                     first_name=u.first_name, last_name=u.last_name, display_name=u.display_name,
                     role=u.role, is_admin=u.is_admin)


def course_out(c: Course, role: Optional[str]) -> s.CourseOut:
    return s.CourseOut(
        id=c.id, term=c.term, subject=c.subject, catalog=c.catalog, section=c.section, title=c.title,
        code=c.code, points_participation=c.points_participation, points_correct=c.points_correct,
        archived_at=c.archived_at, my_role=role,
        join_code=c.join_code if role in ("owner", "instructor", "ta") else None,
    )


def question_out(settings: Settings, q: Question, *, reveal: bool = True) -> s.QuestionOut:
    """reveal=False hides the answer key (students, while the poll is open)."""
    db = Session.object_session(q)
    def murl(media_id):
        return media_url(settings, db.get(Media, media_id)) if media_id else None
    return s.QuestionOut(
        id=q.id, type=q.type, body_md=q.body_md, body_media_url=murl(q.body_media_id),
        options=[s.OptionOut(id=o.id, position=o.position, letter=o.letter, text_md=o.text_md,
                             media_url=murl(o.media_id), is_correct=o.is_correct if reveal else None)
                 for o in q.options],
        bank_id=q.bank_id if reveal else None,
        is_locked=q.is_locked,
        copied_from_id=q.copied_from_id if reveal else None,
        explanation_md=q.explanation_md if reveal else None,
        explanation_media_url=murl(q.explanation_media_id) if reveal else None,
        text_answer=q.text_answer if reveal else None,
        numeric_answer=q.numeric_answer if reveal else None,
        numeric_tolerance=q.numeric_tolerance if reveal else None,
        answer_revealed=reveal,
    )


def my_response_out(r: Response, *, reveal: bool) -> s.MyResponseOut:
    return s.MyResponseOut(
        poll_id=r.poll_id, option_ids=[c.option_id for c in r.choices], text_answer=r.text_answer,
        numeric_answer=r.numeric_answer, submitted_at=r.submitted_at, updated_at=r.updated_at,
        is_correct=r.is_correct if reveal else None,
    )


def poll_out(settings: Settings, poll: Poll, *, is_instructor: bool,
             my_response: Optional[Response] = None) -> s.PollOut:
    # Students see the answer key and their marks only once the poll is closed.
    reveal = is_instructor or poll.status == "closed"
    open_ = poll.status == "open"
    return s.PollOut(
        id=poll.id, course_id=poll.session.course_id, session_id=poll.session_id, status=poll.status,
        access_code=poll.access_code if open_ else None,
        join_url=settings.frontend_link(f"/join/{poll.access_code}") if open_ and poll.access_code else None,
        position=poll.position, show_results=poll.show_results,
        opened_at=poll.opened_at, closed_at=poll.closed_at,
        question=question_out(settings, poll.question, reveal=reveal),
        my_response=my_response_out(my_response, reveal=reveal) if my_response else None,
    )


def bank_out(db: Session, b: QuestionBank) -> s.BankOut:
    n = db.scalar(select(func.count()).select_from(Question).where(Question.bank_id == b.id))
    return s.BankOut(id=b.id, name=b.name, description=b.description, course_id=b.course_id,
                     owner_id=b.owner_id, question_count=n or 0)


def session_out(db: Session, sess: LectureSession) -> s.SessionOut:
    n = db.scalar(select(func.count()).select_from(Poll).where(Poll.session_id == sess.id))
    return s.SessionOut(id=sess.id, course_id=sess.course_id, title=sess.title, session_date=sess.session_date,
                        is_auto=sess.is_auto, poll_count=n or 0)


def roster_out(e: Enrollment) -> s.RosterEntryOut:
    return s.RosterEntryOut(user=user_out(e.user), section=e.section, source=e.source, status=e.status,
                            added_at=e.added_at)


def instructor_out(link: CourseInstructor) -> s.InstructorOut:
    return s.InstructorOut(user=user_out(link.user), role=link.role)
