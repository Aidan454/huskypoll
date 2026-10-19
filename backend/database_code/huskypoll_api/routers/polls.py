"""Live polls: open/close, QR codes, answering, results, students' history, and the WebSocket."""
from __future__ import annotations

import asyncio
import io
from typing import Literal, Optional

import segno
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import Response as RawResponse
from huskypoll_db import services as svc
from huskypoll_db.models import Course, LectureSession, Poll, Response, User
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas as s
from ..config import Settings
from ..deps import (
    after_commit,
    course_or_404,
    current_user,
    get_db,
    get_settings,
    poll_or_404,
    question_or_404,
    require_instructor,
    require_member,
    require_question_access,
    role_in,
    session_or_404,
)
from ..live import Listener, hub
from ..serializers import my_response_out, poll_out, user_out

router = APIRouter(tags=["polls"])
INSTRUCTOR_ROLES = ("owner", "instructor", "ta")


def _my_response(db: Session, poll: Poll, user: User) -> Optional[Response]:
    return db.scalar(select(Response).where(Response.poll_id == poll.id, Response.user_id == user.id))


# Anyone logged in who has the code may answer that lecture's poll without being on the
# roster. The lectures they joined are remembered in their (signed) session cookie; they
# get the poll pages only, never the course, its history or grades.
JOINED_KEY = "joined_sessions"


def _remember_join(request: Request, poll: Poll) -> None:
    joined = [sid for sid in request.session.get(JOINED_KEY, []) if sid != poll.session_id]
    request.session[JOINED_KEY] = (joined + [poll.session_id])[-20:]


def _poll_role(db: Session, request: Request, poll: Poll, user: User) -> str:
    """The user's course role, or 'guest' if they joined this poll's lecture with its code."""
    role = role_in(db, poll.session.course, user)
    if role is not None:
        return role
    if poll.session_id in request.session.get(JOINED_KEY, []):
        return "guest"
    raise HTTPException(404, "Poll not found")


def _announce_open(request: Request, settings: Settings, poll: Poll) -> None:
    payload = poll_out(settings, poll, is_instructor=False).model_dump(mode="json")
    course_id = poll.session.course_id
    after_commit(request, lambda: hub.publish(course_id, {"type": "poll_opened", "poll": payload}))


def _announce_results(request: Request, db: Session, poll: Poll) -> None:
    results = svc.poll_results(db, poll)
    course_id, everyone = poll.session.course_id, poll.show_results
    after_commit(request, lambda: hub.publish(course_id, {"type": "results", "results": results},
                                              instructors_only=not everyone))


# --- opening and managing polls (instructors) ------------------------------------

@router.post("/courses/{course_id}/polls", response_model=s.PollOut, status_code=201,
             summary="Open a poll on an existing question")
def open_poll(course_id: int, body: s.PollOpen, request: Request, db: Session = Depends(get_db),
              user: User = Depends(current_user), settings: Settings = Depends(get_settings)):
    course = course_or_404(db, course_id)
    require_instructor(db, course, user)
    q = question_or_404(db, body.question_id)
    require_question_access(db, q, user)
    sess = session_or_404(db, body.session_id) if body.session_id else None
    poll = svc.open_poll(db, course, q, user, lecture_session=sess, show_results=body.show_results)
    _announce_open(request, settings, poll)
    return poll_out(settings, poll, is_instructor=True)


@router.post("/courses/{course_id}/polls/set", response_model=list[s.PollOut], status_code=201,
             summary="Queue several questions to ask one at a time (opens the first)")
def create_poll_set(course_id: int, body: s.PollSetCreate, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(current_user), settings: Settings = Depends(get_settings)):
    course = course_or_404(db, course_id)
    require_instructor(db, course, user)
    questions = []
    for qid in body.question_ids:
        q = question_or_404(db, qid)
        require_question_access(db, q, user)
        questions.append(q)
    sess = session_or_404(db, body.session_id) if body.session_id else None
    polls = svc.create_poll_set(db, course, questions, user, lecture_session=sess, show_results=body.show_results)
    if body.open_first:
        svc.open_draft_poll(db, polls[0], user)
        _announce_open(request, settings, polls[0])
    return [poll_out(settings, p, is_instructor=True) for p in polls]


@router.post("/polls/{poll_id}/open", response_model=s.PollOut, summary="Open the next question of a poll set")
def open_draft(poll_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user),
               settings: Settings = Depends(get_settings)):
    poll = poll_or_404(db, poll_id)
    require_instructor(db, poll.session.course, user)
    svc.open_draft_poll(db, poll, user)
    _announce_open(request, settings, poll)
    return poll_out(settings, poll, is_instructor=True)


@router.delete("/polls/{poll_id}", status_code=204, summary="Remove a question that hasn't been opened yet")
def delete_draft(poll_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    poll = poll_or_404(db, poll_id)
    require_instructor(db, poll.session.course, user)
    svc.delete_draft_poll(db, poll, user)


@router.post("/courses/{course_id}/polls/quick", response_model=s.PollOut, status_code=201,
             summary="Write a question in lecture and open it immediately")
def quick_poll(course_id: int, body: s.QuickPoll, request: Request, db: Session = Depends(get_db),
               user: User = Depends(current_user), settings: Settings = Depends(get_settings)):
    course = course_or_404(db, course_id)
    require_instructor(db, course, user)
    data = body.model_dump(exclude={"options", "session_id", "show_results", "bank_id"})
    q = svc.create_question(db, user, options=[(o.text_md, o.is_correct) for o in body.options], **data)
    sess = session_or_404(db, body.session_id) if body.session_id else None
    poll = svc.open_poll(db, course, q, user, lecture_session=sess, show_results=body.show_results)
    _announce_open(request, settings, poll)
    return poll_out(settings, poll, is_instructor=True)


@router.get("/courses/{course_id}/polls", response_model=list[s.PollOut],
            summary="Polls in a course (students: includes their own answers)")
def list_polls(request: Request, course_id: int, status: Optional[Literal["open", "closed"]] = None,
               session_id: Optional[int] = None, db: Session = Depends(get_db), user: User = Depends(current_user),
               settings: Settings = Depends(get_settings)):
    course = course_or_404(db, course_id)
    role = role_in(db, course, user)
    if role is None:
        # people who joined with a code see only that lecture's poll
        if not session_id or session_id not in request.session.get(JOINED_KEY, []):
            raise HTTPException(404, "Course not found")
        role = "guest"
    q = select(Poll).join(LectureSession).where(LectureSession.course_id == course.id)
    if status:
        q = q.where(Poll.status == status)
    if session_id:
        q = q.where(Poll.session_id == session_id)
    instructor = role in INSTRUCTOR_ROLES
    if not instructor:
        q = q.where(Poll.status != "draft")  # students never see questions before they're asked
    polls = db.scalars(q.order_by(LectureSession.session_date.desc(), Poll.position.desc())).all()
    return [poll_out(settings, p, is_instructor=instructor, my_response=None if instructor else _my_response(db, p, user))
            for p in polls]


@router.get("/polls/by-code/{access_code}", response_model=s.PollOut,
            summary="Find an open poll from the code a student typed or scanned")
def poll_by_code(access_code: str, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(current_user), settings: Settings = Depends(get_settings)):
    poll = svc.find_open_poll_by_code(db, access_code) or svc.find_poll_set_by_code(db, access_code)
    if poll is None:
        raise HTTPException(404, "No open poll with that code")
    role = role_in(db, poll.session.course, user)
    if role is None:  # not on the roster: the code lets them into this poll only
        _remember_join(request, poll)
    instructor = role in INSTRUCTOR_ROLES
    return poll_out(settings, poll, is_instructor=instructor, my_response=None if instructor else _my_response(db, poll, user))


@router.get("/polls/{poll_id}", response_model=s.PollOut)
def get_poll(poll_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user),
             settings: Settings = Depends(get_settings)):
    poll = poll_or_404(db, poll_id)
    instructor = _poll_role(db, request, poll, user) in INSTRUCTOR_ROLES
    if poll.status == "draft" and not instructor:
        raise HTTPException(404, "Poll not found")
    return poll_out(settings, poll, is_instructor=instructor, my_response=None if instructor else _my_response(db, poll, user))


@router.patch("/polls/{poll_id}", response_model=s.PollOut, summary="Show/hide results, or move to another session")
def update_poll(poll_id: int, body: s.PollUpdate, request: Request, db: Session = Depends(get_db),
                user: User = Depends(current_user), settings: Settings = Depends(get_settings)):
    poll = poll_or_404(db, poll_id)
    require_instructor(db, poll.session.course, user)
    if body.session_id is not None and body.session_id != poll.session_id:
        svc.move_poll(db, poll, session_or_404(db, body.session_id))
    if body.show_results is not None:
        poll.show_results = body.show_results
        db.flush()
        _announce_results(request, db, poll)
    return poll_out(settings, poll, is_instructor=True)


@router.post("/polls/{poll_id}/close", response_model=s.PollOut)
def close_poll(poll_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user),
               settings: Settings = Depends(get_settings)):
    poll = poll_or_404(db, poll_id)
    require_instructor(db, poll.session.course, user)
    svc.close_poll(db, poll, user)
    course_id = poll.session.course_id
    after_commit(request, lambda: hub.publish(course_id, {"type": "poll_closed", "poll_id": poll_id}))
    return poll_out(settings, poll, is_instructor=True)


@router.post("/polls/{poll_id}/regrade", response_model=s.RegradeOut,
             summary="Re-mark all answers (after fixing the answer key)")
def regrade(poll_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    poll = poll_or_404(db, poll_id)
    require_instructor(db, poll.session.course, user)
    return s.RegradeOut(responses_regraded=svc.regrade_poll(db, poll))


@router.get("/polls/{poll_id}/results", response_model=s.PollResults,
            summary="Vote counts (students only when the instructor shows results)")
def results(poll_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    poll = poll_or_404(db, poll_id)
    role = _poll_role(db, request, poll, user)
    if role not in INSTRUCTOR_ROLES and not poll.show_results:
        raise HTTPException(403, "The instructor hasn't shared the results")
    return svc.poll_results(db, poll)


@router.get("/polls/{poll_id}/responses", summary="Every student's answer (instructors)")
def list_responses(poll_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    poll = poll_or_404(db, poll_id)
    require_instructor(db, poll.session.course, user)
    rows = db.scalars(select(Response).where(Response.poll_id == poll.id).order_by(Response.submitted_at)).all()
    course = poll.session.course
    return [{"user": user_out(r.user).model_dump(), "on_roster": svc.is_enrolled(db, course, r.user),
             **my_response_out(r, reveal=True).model_dump(mode="json")}
            for r in rows]


@router.get("/polls/{poll_id}/qr.{fmt}", response_class=RawResponse,
            summary="QR code for students to join (svg or png)",
            responses={200: {"content": {"image/svg+xml": {}, "image/png": {}}}})
def poll_qr(poll_id: int, fmt: Literal["svg", "png"], scale: int = 10, db: Session = Depends(get_db),
            user: User = Depends(current_user), settings: Settings = Depends(get_settings)):
    poll = poll_or_404(db, poll_id)
    require_instructor(db, poll.session.course, user)
    if poll.status != "open":
        raise HTTPException(400, "The poll is not open")
    qr = segno.make(settings.frontend_link(f"/join/{poll.access_code}"), error="m")
    buf = io.BytesIO()
    qr.save(buf, kind=fmt, scale=max(1, min(scale, 40)), border=2)
    return RawResponse(buf.getvalue(), media_type="image/svg+xml" if fmt == "svg" else "image/png",
                       headers={"Cache-Control": "no-store"})


# --- answering (students) -------------------------------------------------------

@router.post("/polls/{poll_id}/responses", response_model=s.MyResponseOut,
             summary="Submit or change my answer; the reply is the student's confirmation")
def submit(poll_id: int, body: s.ResponseIn, request: Request, db: Session = Depends(get_db),
           user: User = Depends(current_user)):
    poll = poll_or_404(db, poll_id)
    role = _poll_role(db, request, poll, user)
    resp = svc.submit_response(db, poll, user, option_ids=body.option_ids, text_answer=body.text_answer,
                               numeric_answer=body.numeric_answer,
                               ip_address=request.client.host if request.client else None,
                               require_enrollment=role != "guest")
    _announce_results(request, db, poll)
    db.refresh(resp)
    return my_response_out(resp, reveal=False)


@router.get("/courses/{course_id}/history", response_model=list[s.HistoryItem],
            summary="My polls in this course with my answers (answers revealed after each poll closes)")
def history(course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user),
            settings: Settings = Depends(get_settings)):
    course = course_or_404(db, course_id)
    require_member(db, course, user)
    out = []
    for item in svc.student_history(db, user, course):
        p, r = item["poll"], item["response"]
        out.append(s.HistoryItem(poll=poll_out(settings, p, is_instructor=False, my_response=r),
                                 session_title=p.session.title, session_date=p.session.session_date,
                                 answered=r is not None))
    return out


@router.get("/courses/{course_id}/my-participation", response_model=s.ParticipationOut)
def my_participation(course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    from huskypoll_db.export import participation_totals
    course = course_or_404(db, course_id)
    require_member(db, course, user)
    row = next((r for r in participation_totals(db, course) if r["net_id"] == user.net_id and user.net_id), None)
    if row is None:
        return s.ParticipationOut(polls=0, answered=0, correct=0, points=0, points_possible=0)
    return s.ParticipationOut(**{k: row[k] for k in ("polls", "answered", "correct", "points", "points_possible")})


# --- live updates ---------------------------------------------------------------

@router.websocket("/ws/courses/{course_id}")
async def course_updates(websocket: WebSocket, course_id: int):
    """Live updates for one course page. Log in first; the session cookie is used."""
    user_id = websocket.session.get("user_id") if "session" in websocket.scope else None
    if user_id is None:
        await websocket.close(code=4401)
        return

    joined = websocket.session.get(JOINED_KEY, [])

    def lookup():
        with websocket.app.state.session_factory() as db:
            user = db.get(User, user_id)
            course = db.get(Course, course_id) if user else None
            if course is None:
                return None
            role = role_in(db, course, user)
            if role is None and joined and db.scalar(select(LectureSession.id).where(
                    LectureSession.course_id == course_id, LectureSession.id.in_(joined))):
                role = "guest"  # joined a poll in this course with its code
            return role

    role = await asyncio.to_thread(lookup)
    if role is None:
        await websocket.close(code=4403)
        return
    await websocket.accept()
    await websocket.send_json({"type": "hello", "course_id": course_id, "role": role})
    listener = Listener(user_id=user_id, is_instructor=role in INSTRUCTOR_ROLES)
    hub.add(course_id, listener)

    async def pump():
        while True:
            await websocket.send_text(await listener.queue.get())

    sender = asyncio.create_task(pump())
    try:
        while True:  # we don't expect messages, but reading notices the client leaving
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        hub.remove(course_id, listener)
