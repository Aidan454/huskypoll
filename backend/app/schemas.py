"""Request and response shapes. FastAPI turns these into the interactive docs at /docs,
which is what the frontend team should read."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.database.models import QUESTION_TYPES

QuestionType = Literal["mc_single", "mc_multi", "free_text", "numeric"]
assert set(QuestionType.__args__) == set(QUESTION_TYPES)
Role = Literal["owner", "instructor", "ta", "student"]          # role within one course
UserRole = Literal["admin", "instructor", "ta", "student", "guest"]  # account type


# --- users -----------------------------------------------------------------------

class UserOut(BaseModel):
    id: int
    net_id: str | None
    email: str | None
    student_id: str | None = None
    first_name: str | None
    last_name: str | None
    display_name: str
    role: UserRole
    is_admin: bool = False


class DevLogin(BaseModel):
    email: str = Field(examples=["jonathan.smith@uconn.edu"])
    net_id: str | None = Field(None, examples=["jos10001"])
    first_name: str | None = None
    last_name: str | None = None
    role: UserRole | None = Field(None, description="Development only: log in with this account role")


class RoleUpdate(BaseModel):
    role: UserRole


# --- courses -----------------------------------------------------------------------

class CourseCreate(BaseModel):
    term: str = Field(examples=["Spring 2027"])
    subject: str = Field(examples=["CSE"])
    catalog: str = Field(examples=["2050"])
    section: str | None = Field(None, examples=["001"])
    title: str = Field(examples=["Data Structures"])
    points_participation: float = Field(1.0, ge=0)
    points_correct: float = Field(0.0, ge=0)


class CourseUpdate(BaseModel):
    title: str | None = None
    section: str | None = None
    points_participation: float | None = Field(None, ge=0)
    points_correct: float | None = Field(None, ge=0)


class CourseOut(BaseModel):
    id: int
    term: str
    subject: str
    catalog: str
    section: str | None
    title: str
    code: str
    points_participation: float
    points_correct: float
    archived_at: dt.datetime | None
    my_role: Role | None
    join_code: str | None = None  # instructors only


class InstructorAdd(BaseModel):
    identifier: str = Field(description="NetID or email", examples=["abc12345"])
    role: Literal["owner", "instructor", "ta"] = "instructor"


class InstructorOut(BaseModel):
    user: UserOut
    role: Role


class RosterAdd(BaseModel):
    identifier: str = Field(description="NetID, email or 7-digit student ID", examples=["abc12345"])
    first_name: str | None = None
    last_name: str | None = None
    section: str | None = None


class RosterPaste(BaseModel):
    text: str = Field(description="One NetID, email or student ID per line (commas also work)")


class RosterEntryOut(BaseModel):
    user: UserOut
    section: str | None
    source: str
    status: str
    added_at: dt.datetime


class ImportResultOut(BaseModel):
    users_created: int
    users_matched: int
    enrolled: int
    reactivated: int
    unchanged: int
    dropped: int
    skipped: list[dict]
    summary: str


# --- questions ---------------------------------------------------------------------

class OptionIn(BaseModel):
    text_md: str
    is_correct: bool = False


class OptionOut(BaseModel):
    id: int
    position: int
    letter: str
    text_md: str
    media_url: str | None = None
    is_correct: bool | None = None  # hidden from students while a poll is open


class QuestionCreate(BaseModel):
    type: QuestionType
    body_md: str = Field("", description="Question text (simple Markdown)")
    body_media_id: int | None = None
    options: list[OptionIn] = []
    explanation_md: str | None = None
    explanation_media_id: int | None = None
    text_answer: str | None = None
    numeric_answer: float | None = None
    numeric_tolerance: float | None = Field(None, ge=0)
    bank_id: int | None = None


class QuestionUpdate(BaseModel):
    """Send only the fields to change. Once a question has been polled, only the answer
    key and explanation can change (use correct_option_ids for multiple choice)."""
    type: QuestionType | None = None
    body_md: str | None = None
    body_media_id: int | None = None
    options: list[OptionIn] | None = None
    correct_option_ids: list[int] | None = None
    explanation_md: str | None = None
    explanation_media_id: int | None = None
    text_answer: str | None = None
    numeric_answer: float | None = None
    numeric_tolerance: float | None = Field(None, ge=0)
    bank_id: int | None = None


class QuestionOut(BaseModel):
    id: int
    type: QuestionType
    body_md: str
    body_media_url: str | None
    options: list[OptionOut]
    bank_id: int | None = None
    is_locked: bool = False
    copied_from_id: int | None = None
    # Answer key - None for students while the poll is open
    explanation_md: str | None = None
    explanation_media_url: str | None = None
    text_answer: str | None = None
    numeric_answer: float | None = None
    numeric_tolerance: float | None = None
    answer_revealed: bool = True


class QuestionUpdateOut(BaseModel):
    question: QuestionOut
    responses_regraded: int


class BankCreate(BaseModel):
    name: str
    description: str | None = None
    course_id: int | None = None


class BankUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    course_id: int | None = None


class BankCopy(BaseModel):
    name: str
    course_id: int | None = None


class BankOut(BaseModel):
    id: int
    name: str
    description: str | None
    course_id: int | None
    owner_id: int
    question_count: int


class BankDetail(BankOut):
    questions: list[QuestionOut]


# --- sessions, polls, responses -------------------------------------------------

class SessionCreate(BaseModel):
    title: str
    session_date: dt.date | None = None


class SessionUpdate(BaseModel):
    title: str | None = None
    session_date: dt.date | None = None


class SessionOut(BaseModel):
    id: int
    course_id: int
    title: str | None
    session_date: dt.date
    is_auto: bool
    poll_count: int


class PollOpen(BaseModel):
    question_id: int
    session_id: int | None = Field(None, description="Default: today's session, created if needed")
    show_results: bool = False


class PollSetCreate(BaseModel):
    """Several questions asked one after another in one lecture. The first opens
    right away; the rest wait as drafts until POST /polls/{id}/open."""
    question_ids: list[int] = Field(min_length=1, description="In the order they will be asked")
    session_id: int | None = Field(None, description="Default: today's session, created if needed")
    show_results: bool = False
    open_first: bool = True


class QuickPoll(QuestionCreate):
    """Create a question in lecture and open it in one step."""
    session_id: int | None = None
    show_results: bool = False


class PollUpdate(BaseModel):
    show_results: bool | None = None
    session_id: int | None = Field(None, description="Move the poll to another session of the course")


class ResponseIn(BaseModel):
    option_ids: list[int] = []
    text_answer: str | None = Field(None, max_length=2000)
    numeric_answer: float | None = None

    @field_validator("option_ids")
    @classmethod
    def _unique(cls, v: list[int]) -> list[int]:
        return list(dict.fromkeys(v))


class MyResponseOut(BaseModel):
    """The student's confirmation / their saved answer."""
    poll_id: int
    received: bool = True
    option_ids: list[int]
    text_answer: str | None
    numeric_answer: float | None
    submitted_at: dt.datetime
    updated_at: dt.datetime
    is_correct: bool | None = None  # hidden until the poll closes


class PollOut(BaseModel):
    id: int
    course_id: int
    session_id: int
    status: Literal["draft", "open", "closed"]
    access_code: str | None
    join_url: str | None
    position: int
    show_results: bool
    opened_at: dt.datetime | None
    closed_at: dt.datetime | None
    question: QuestionOut
    my_response: MyResponseOut | None = None


class PollResults(BaseModel):
    poll_id: int
    status: str
    responses: int
    correct: int
    options: list[dict] | None = None
    answers: list[dict] | None = None


class RegradeOut(BaseModel):
    responses_regraded: int


class HistoryItem(BaseModel):
    poll: PollOut
    session_title: str | None
    session_date: dt.date
    answered: bool


class ParticipationOut(BaseModel):
    polls: int
    answered: int
    correct: int
    points: float
    points_possible: float


class EventOut(BaseModel):
    id: int
    occurred_at: dt.datetime
    event_type: str
    net_id: str | None
    poll_id: int | None
    details: dict | None


class MediaOut(BaseModel):
    id: int
    url: str
    mime_type: str
    size_bytes: int | None


class DeleteCourseOut(BaseModel):
    course_code: str
    students: int
    sessions: int
    polls: int
    responses: int
