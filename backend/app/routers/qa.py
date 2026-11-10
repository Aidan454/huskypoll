"""Member-only lecture Q&A, available without an active poll."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import services as svc
from app.database.models import CourseQuestion, CourseReply, User

from .. import schemas as s
from ..deps import after_commit, current_user, get_db, require_member, session_or_404
from ..live import hub

router = APIRouter(tags=["lecture Q&A"])
DB = Annotated[Session, Depends(get_db, scope="function")]
Member = Annotated[User, Depends(current_user)]


def _message_out(row):
    # Never fall back to email or student ID when a roster entry lacks a name.
    author = row.author
    name = " ".join(p for p in (author.first_name, author.last_name) if p) if author else ""
    return s.CourseMessageOut(id=row.id, body=row.body, created_at=row.created_at,
                              author_name=name or (author.net_id if author else None) or "Course member")


def _question(db, session_id, question_id):
    question = db.get(CourseQuestion, question_id)
    if question is None or question.session_id != session_id:
        raise HTTPException(404, "Question not found")
    return question


def _changed(request, session):
    course_id, session_id = session.course_id, session.id
    after_commit(request, lambda: hub.publish(course_id, {"type": "qa_changed", "session_id": session_id}))


@router.get("/sessions/{session_id}/qa", response_model=list[s.CourseQuestionOut])
def list_questions(session_id: int, db: DB, user: Member,
                   before_id: Annotated[int | None, Query(gt=0)] = None):
    session = session_or_404(db, session_id)
    require_member(db, session.course, user)
    counts = select(CourseReply.question_id, func.count().label("n")).group_by(CourseReply.question_id).subquery()
    query = (select(CourseQuestion, func.coalesce(counts.c.n, 0))
             .outerjoin(counts, counts.c.question_id == CourseQuestion.id)
             .options(selectinload(CourseQuestion.author)).where(CourseQuestion.session_id == session_id))
    if before_id is not None:
        query = query.where(CourseQuestion.id < before_id)
    return [s.CourseQuestionOut(**_message_out(q).model_dump(), reply_count=count)
            for q, count in db.execute(query.order_by(CourseQuestion.id.desc()).limit(30))]


@router.post("/sessions/{session_id}/qa", response_model=s.CourseQuestionOut, status_code=201)
def ask_question(session_id: int, body: s.CourseMessageCreate, request: Request, db: DB, user: Member):
    session = session_or_404(db, session_id)
    require_member(db, session.course, user)
    row = svc.post_lecture_message(db, session, user, body.body)
    _changed(request, session)
    return s.CourseQuestionOut(**_message_out(row).model_dump(), reply_count=0)


@router.get("/sessions/{session_id}/qa/{question_id}/replies", response_model=list[s.CourseMessageOut])
def list_replies(session_id: int, question_id: int, db: DB, user: Member):
    session = session_or_404(db, session_id)
    require_member(db, session.course, user)
    _question(db, session_id, question_id)
    return [_message_out(row) for row in db.scalars(select(CourseReply)
            .where(CourseReply.question_id == question_id).options(selectinload(CourseReply.author))
            .order_by(CourseReply.id))]


@router.post("/sessions/{session_id}/qa/{question_id}/replies", response_model=s.CourseMessageOut, status_code=201)
def reply(session_id: int, question_id: int, body: s.CourseMessageCreate, request: Request, db: DB, user: Member):
    session = session_or_404(db, session_id)
    require_member(db, session.course, user)
    row = svc.post_lecture_message(db, session, user, body.body, question=_question(db, session_id, question_id))
    _changed(request, session)
    return _message_out(row)


@router.get("/sessions/{session_id}", response_model=s.SessionOut)
def get_session(session_id: int, db: DB, user: Member):
    from ..serializers import session_out
    session = session_or_404(db, session_id)
    require_member(db, session.course, user)
    return session_out(db, session)
