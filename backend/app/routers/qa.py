"""Member-only course Q&A, available without an active poll."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import services as svc
from app.database.models import CourseQuestion, CourseReply, User

from .. import schemas as s
from ..deps import after_commit, course_or_404, current_user, get_db, require_member
from ..live import hub

router = APIRouter(tags=["course Q&A"])
DB = Annotated[Session, Depends(get_db, scope="function")]
Member = Annotated[User, Depends(current_user)]


def _message_out(row):
    # Never fall back to email or student ID when a roster entry lacks a name.
    author = row.author
    name = " ".join(p for p in (author.first_name, author.last_name) if p) if author else ""
    return s.CourseMessageOut(id=row.id, body=row.body, created_at=row.created_at,
                              author_name=name or (author.net_id if author else None) or "Course member")


def _question(db, course_id, question_id):
    question = db.get(CourseQuestion, question_id)
    if question is None or question.course_id != course_id:
        raise HTTPException(404, "Question not found")
    return question


def _changed(request, course_id):
    after_commit(request, lambda: hub.publish(course_id, {"type": "qa_changed"}))


@router.get("/courses/{course_id}/qa", response_model=list[s.CourseQuestionOut])
def list_questions(course_id: int, db: DB, user: Member,
                   before_id: Annotated[int | None, Query(gt=0)] = None):
    course = course_or_404(db, course_id)
    require_member(db, course, user)
    counts = select(CourseReply.question_id, func.count().label("n")).group_by(CourseReply.question_id).subquery()
    query = (select(CourseQuestion, func.coalesce(counts.c.n, 0))
             .outerjoin(counts, counts.c.question_id == CourseQuestion.id)
             .options(selectinload(CourseQuestion.author)).where(CourseQuestion.course_id == course_id))
    if before_id is not None:
        query = query.where(CourseQuestion.id < before_id)
    return [s.CourseQuestionOut(**_message_out(q).model_dump(), reply_count=count)
            for q, count in db.execute(query.order_by(CourseQuestion.id.desc()).limit(30))]


@router.post("/courses/{course_id}/qa", response_model=s.CourseQuestionOut, status_code=201)
def ask_question(course_id: int, body: s.CourseMessageCreate, request: Request, db: DB, user: Member):
    course = course_or_404(db, course_id)
    require_member(db, course, user)
    row = svc.post_course_message(db, course, user, body.body)
    _changed(request, course_id)
    return s.CourseQuestionOut(**_message_out(row).model_dump(), reply_count=0)


@router.get("/courses/{course_id}/qa/{question_id}/replies", response_model=list[s.CourseMessageOut])
def list_replies(course_id: int, question_id: int, db: DB, user: Member):
    require_member(db, course_or_404(db, course_id), user)
    _question(db, course_id, question_id)
    return [_message_out(row) for row in db.scalars(select(CourseReply)
            .where(CourseReply.question_id == question_id).options(selectinload(CourseReply.author))
            .order_by(CourseReply.id))]


@router.post("/courses/{course_id}/qa/{question_id}/replies", response_model=s.CourseMessageOut, status_code=201)
def reply(course_id: int, question_id: int, body: s.CourseMessageCreate, request: Request, db: DB, user: Member):
    course = course_or_404(db, course_id)
    require_member(db, course, user)
    row = svc.post_course_message(db, course, user, body.body, question=_question(db, course_id, question_id))
    _changed(request, course_id)
    return _message_out(row)
