"""SQLAlchemy models for HuskyPoll - the single source of truth for the schema.

Thirteen tables in five groups (matches huskypoll-schema.drawio):

  People        users
  Courses       courses, course_instructors, enrollments
  Content       question_banks, questions, question_options, media
  Live polling  lecture_sessions, polls, responses, response_choices
  Audit         event_log

Conventions
  * Every timestamp is stored in UTC (see UTCDateTime) and returned timezone-aware.
  * Closed sets of values (roles, statuses, question types) are TEXT + CHECK constraint,
    so the database itself rejects typos such as status='opne'.
  * Images are files on disk; `media` stores only the path and a SHA-256 hash.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .triggers import DDL_STATEMENTS

# ---------------------------------------------------------------------------
# Base, naming convention, helpers
# ---------------------------------------------------------------------------

# Predictable constraint names make Alembic migrations (especially SQLite
# "batch" migrations, which rebuild tables) reliable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UTCDateTime(TypeDecorator):
    """Store datetimes as naive UTC; always hand back timezone-aware UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: Optional[dt.datetime], dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime passed to the database; use utcnow() or an aware datetime")
        return value.astimezone(dt.timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: Optional[dt.datetime], dialect):
        if value is None:
            return None
        return value.replace(tzinfo=dt.timezone.utc)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _bool(name: str) -> Boolean:
    # create_constraint adds CHECK (col IN (0, 1))
    return Boolean(create_constraint=True, name=name)


def _created_at() -> Mapped[dt.datetime]:
    return mapped_column(UTCDateTime, nullable=False, default=utcnow)


# Allowed values for TEXT + CHECK columns. Import these in the API layer
# instead of retyping the strings.
# Account type (users.role), highest first. Separate from the role a person has in a
# particular course (course_instructors.role / being on the roster).
USER_ROLES = ("admin", "instructor", "ta", "student", "guest")
ROLE_RANK = {r: len(USER_ROLES) - i for i, r in enumerate(USER_ROLES)}  # admin=5 ... guest=1
INSTRUCTOR_ROLES = ("owner", "instructor", "ta")
ENROLLMENT_SOURCES = ("import", "manual", "self")
ENROLLMENT_STATUSES = ("active", "dropped")
QUESTION_TYPES = ("mc_single", "mc_multi", "free_text", "numeric")
POLL_STATUSES = ("draft", "open", "closed")


# UConn NetID format, used by the CHECK constraint on users.net_id and by services.NETID_RE.
NETID_GLOB = "[a-z][a-z][a-z][0-9][0-9][0-9][0-9][0-9]"


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

class User(Base):
    """Anyone who logs in (UConn CAS / Entra) or appears on a roster.

    Roster import can create a user before their first login, so any one of
    net_id / email / student_id is enough to identify them.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    net_id: Mapped[Optional[str]] = mapped_column(String(8), unique=True)  # e.g. abc12345, stored lowercase
    student_id: Mapped[Optional[str]] = mapped_column(String(16), unique=True)  # 7-digit PeopleSoft ID
    email: Mapped[Optional[str]] = mapped_column(String(254), unique=True)  # stored lowercase
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    # admin: everything | instructor: create courses | ta: assist in courses |
    # student: on a roster | guest: logged in, not on any roster yet
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="guest", server_default="guest")
    created_at: Mapped[dt.datetime] = _created_at()
    last_login_at: Mapped[Optional[dt.datetime]] = mapped_column(UTCDateTime)

    # passive_deletes: let the database's ON DELETE CASCADE remove these when a user is deleted
    enrollments: Mapped[list[Enrollment]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    teaching: Mapped[list[CourseInstructor]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        CheckConstraint(
            "net_id IS NOT NULL OR email IS NOT NULL OR student_id IS NOT NULL",
            name="has_identifier",
        ),
        # UConn NetID: 3 lowercase letters followed by 5 digits, e.g. abc12345
        CheckConstraint(f"net_id IS NULL OR net_id GLOB '{NETID_GLOB}'", name="net_id_format"),
        # Roster rows may lack a NetID until first login; anyone who has logged in has one.
        CheckConstraint("last_login_at IS NULL OR net_id IS NOT NULL", name="logged_in_has_net_id"),
        CheckConstraint(_in("role", USER_ROLES), name="role"),
        CheckConstraint("email IS NULL OR email = lower(email)", name="email_lower"),
    )

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_staff(self) -> bool:
        """Admin, instructor or TA: may write questions and upload images."""
        return self.role in ("admin", "instructor", "ta")

    def has_role_at_least(self, role: str) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[role]

    @property
    def display_name(self) -> str:
        name = " ".join(p for p in (self.first_name, self.last_name) if p)
        return name or self.net_id or self.email or self.student_id or f"user {self.id}"

    def __repr__(self) -> str:
        return f"<User {self.id} {self.net_id or self.email or self.student_id}>"


# ---------------------------------------------------------------------------
# Courses and rosters
# ---------------------------------------------------------------------------

class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    term: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g. "Spring 2027"
    subject: Mapped[str] = mapped_column(String(16), nullable=False)  # e.g. "CSE"
    catalog: Mapped[str] = mapped_column(String(16), nullable=False)  # e.g. "4939W"
    section: Mapped[Optional[str]] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    join_code: Mapped[Optional[str]] = mapped_column(String(16), unique=True)
    # Grading: each poll is worth points_participation for answering plus
    # points_correct for a correct answer.
    points_participation: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    points_correct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime] = _created_at()
    archived_at: Mapped[Optional[dt.datetime]] = mapped_column(UTCDateTime)

    instructors: Mapped[list[CourseInstructor]] = relationship(back_populates="course", cascade="all, delete-orphan")
    enrollments: Mapped[list[Enrollment]] = relationship(back_populates="course", cascade="all, delete-orphan")
    sessions: Mapped[list[LectureSession]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="LectureSession.session_date"
    )

    __table_args__ = (
        UniqueConstraint("term", "subject", "catalog", "section"),
        CheckConstraint("points_participation >= 0 AND points_correct >= 0", name="points_nonneg"),
    )

    @property
    def code(self) -> str:
        sec = f"-{self.section}" if self.section else ""
        return f"{self.subject} {self.catalog}{sec} ({self.term})"


class CourseInstructor(Base):
    """Many instructors / TAs per course."""

    __tablename__ = "course_instructors"

    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="instructor")
    added_at: Mapped[dt.datetime] = _created_at()

    course: Mapped[Course] = relationship(back_populates="instructors")
    user: Mapped[User] = relationship(back_populates="teaching")

    __table_args__ = (
        CheckConstraint(_in("role", INSTRUCTOR_ROLES), name="role"),
        Index(None, "user_id"),
    )


class Enrollment(Base):
    """The roster: one row per student per course."""

    __tablename__ = "enrollments"

    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    section: Mapped[Optional[str]] = mapped_column(String(16))  # e.g. "011Lab" from StudentAdmin
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    added_at: Mapped[dt.datetime] = _created_at()

    course: Mapped[Course] = relationship(back_populates="enrollments")
    user: Mapped[User] = relationship(back_populates="enrollments")

    __table_args__ = (
        CheckConstraint(_in("source", ENROLLMENT_SOURCES), name="source"),
        CheckConstraint(_in("status", ENROLLMENT_STATUSES), name="status"),
        Index(None, "user_id"),
    )


# ---------------------------------------------------------------------------
# Question content
# ---------------------------------------------------------------------------

class Media(Base):
    """An uploaded or pasted image. The file lives on disk at file_path."""

    __tablename__ = "media"

    id: Mapped[int] = mapped_column(primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # de-duplicates re-uploads
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    uploaded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime] = _created_at()

    __table_args__ = (CheckConstraint("mime_type LIKE 'image/%'", name="image_only"),)


class QuestionBank(Base):
    """A reusable collection of questions, owned by an instructor and optionally tied to a course."""

    __tablename__ = "question_banks"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    course_id: Mapped[Optional[int]] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = _created_at()

    questions: Mapped[list[Question]] = relationship(back_populates="bank")

    __table_args__ = (Index(None, "owner_id"), Index(None, "course_id"))


class Question(Base):
    """Question text, its answer and explanation.

    Once a question has been used in a poll it is locked (a trigger sets
    is_locked when the poll opens, and another trigger blocks edits). To change
    a locked question, copy it with services.copy_question(); the copy records
    copied_from_id. This keeps every student's history showing exactly the
    question they answered.
    """

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    bank_id: Mapped[Optional[int]] = mapped_column(ForeignKey("question_banks.id", ondelete="SET NULL"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False, default="")  # simple Markdown
    body_media_id: Mapped[Optional[int]] = mapped_column(ForeignKey("media.id", ondelete="SET NULL"))
    explanation_md: Mapped[Optional[str]] = mapped_column(Text)
    explanation_media_id: Mapped[Optional[int]] = mapped_column(ForeignKey("media.id", ondelete="SET NULL"))
    text_answer: Mapped[Optional[str]] = mapped_column(Text)  # expected answer for free_text (optional)
    numeric_answer: Mapped[Optional[float]] = mapped_column(Float)
    numeric_tolerance: Mapped[Optional[float]] = mapped_column(Float)
    copied_from_id: Mapped[Optional[int]] = mapped_column(ForeignKey("questions.id", ondelete="SET NULL"))
    is_locked: Mapped[bool] = mapped_column(_bool("is_locked"), nullable=False, default=False)
    created_at: Mapped[dt.datetime] = _created_at()
    updated_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow)

    bank: Mapped[Optional[QuestionBank]] = relationship(back_populates="questions")
    options: Mapped[list[QuestionOption]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="QuestionOption.position"
    )
    body_media: Mapped[Optional[Media]] = relationship(foreign_keys=[body_media_id])
    explanation_media: Mapped[Optional[Media]] = relationship(foreign_keys=[explanation_media_id])

    __table_args__ = (
        CheckConstraint(_in("type", QUESTION_TYPES), name="type"),
        CheckConstraint("body_md <> '' OR body_media_id IS NOT NULL", name="has_body"),
        CheckConstraint("numeric_tolerance IS NULL OR numeric_tolerance >= 0", name="tolerance_nonneg"),
        CheckConstraint(
            "type = 'numeric' OR (numeric_answer IS NULL AND numeric_tolerance IS NULL)",
            name="numeric_fields_only_for_numeric",
        ),
        Index(None, "bank_id"),
        Index(None, "author_id"),
    )


class QuestionOption(Base):
    """One choice of a multiple-choice question."""

    __tablename__ = "question_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 = A, 1 = B, ...
    text_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_id: Mapped[Optional[int]] = mapped_column(ForeignKey("media.id", ondelete="SET NULL"))
    is_correct: Mapped[bool] = mapped_column(_bool("is_correct"), nullable=False, default=False)

    question: Mapped[Question] = relationship(back_populates="options")

    __table_args__ = (
        UniqueConstraint("question_id", "position"),
        CheckConstraint("position >= 0", name="position_nonneg"),
    )

    @property
    def letter(self) -> str:
        return chr(ord("A") + self.position) if self.position < 26 else str(self.position + 1)


# ---------------------------------------------------------------------------
# Live polling
# ---------------------------------------------------------------------------

class LectureSession(Base):
    """Groups the polls asked in one lecture. Created automatically when the
    first poll of the day opens (is_auto=1) or manually by an instructor."""

    __tablename__ = "lecture_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(200))
    session_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    started_at: Mapped[Optional[dt.datetime]] = mapped_column(UTCDateTime)
    ended_at: Mapped[Optional[dt.datetime]] = mapped_column(UTCDateTime)
    is_auto: Mapped[bool] = mapped_column(_bool("is_auto"), nullable=False, default=False)

    course: Mapped[Course] = relationship(back_populates="sessions")
    polls: Mapped[list[Poll]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Poll.position"
    )

    __table_args__ = (Index(None, "course_id", "session_date"),)


class Poll(Base):
    """One question asked once, in one lecture session."""

    __tablename__ = "polls"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("lecture_sessions.id", ondelete="CASCADE"), nullable=False)
    # RESTRICT: a question that has been polled can never be deleted out from under its responses.
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False)
    access_code: Mapped[Optional[str]] = mapped_column(String(16))  # short code shown with the QR image
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    show_results: Mapped[bool] = mapped_column(_bool("show_results"), nullable=False, default=False)
    opened_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    opened_at: Mapped[Optional[dt.datetime]] = mapped_column(UTCDateTime)
    closed_at: Mapped[Optional[dt.datetime]] = mapped_column(UTCDateTime)
    created_at: Mapped[dt.datetime] = _created_at()

    session: Mapped[LectureSession] = relationship(back_populates="polls")
    question: Mapped[Question] = relationship()
    responses: Mapped[list[Response]] = relationship(back_populates="poll", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(_in("status", POLL_STATUSES), name="status"),
        CheckConstraint("status = 'draft' OR opened_at IS NOT NULL", name="opened_has_time"),
        CheckConstraint("status <> 'closed' OR closed_at IS NOT NULL", name="closed_has_time"),
        CheckConstraint("closed_at IS NULL OR closed_at >= opened_at", name="close_after_open"),
        # Access codes only need to be unique among polls that are open right now,
        # so short codes can be reused.
        Index(
            "uq_polls_open_access_code",
            "access_code",
            unique=True,
            sqlite_where=text("status = 'open'"),
        ),
        Index(None, "session_id"),
        Index(None, "question_id"),
    )


class Response(Base):
    """One student's answer to one poll. Resubmitting updates this row."""

    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("polls.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text_answer: Mapped[Optional[str]] = mapped_column(Text)
    numeric_answer: Mapped[Optional[float]] = mapped_column(Float)
    is_correct: Mapped[Optional[bool]] = mapped_column(_bool("is_correct"))  # NULL = no right answer
    submitted_at: Mapped[dt.datetime] = _created_at()
    updated_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow)

    poll: Mapped[Poll] = relationship(back_populates="responses")
    user: Mapped[User] = relationship()
    choices: Mapped[list[ResponseChoice]] = relationship(back_populates="response", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("poll_id", "user_id"),  # one answer per student per poll
        Index(None, "user_id"),
    )


class ResponseChoice(Base):
    """Option(s) a student picked. Several rows = select-all-that-apply."""

    __tablename__ = "response_choices"

    response_id: Mapped[int] = mapped_column(ForeignKey("responses.id", ondelete="CASCADE"), primary_key=True)
    option_id: Mapped[int] = mapped_column(ForeignKey("question_options.id", ondelete="CASCADE"), primary_key=True)

    response: Mapped[Response] = relationship(back_populates="choices")
    option: Mapped[QuestionOption] = relationship()


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

class EventLog(Base):
    """Append-only log: logins, poll open/close, responses, imports, exports."""

    __tablename__ = "event_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g. "login", "poll_open"
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    course_id: Mapped[Optional[int]] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"))
    poll_id: Mapped[Optional[int]] = mapped_column(ForeignKey("polls.id", ondelete="SET NULL"))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    details_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

    __table_args__ = (
        Index(None, "occurred_at"),
        Index("ix_event_log_course_time", "course_id", "occurred_at"),
        Index("ix_event_log_user_time", "user_id", "occurred_at"),
    )


# ---------------------------------------------------------------------------
# Triggers and views (raw SQL, kept in triggers.py so Alembic can reuse it)
# ---------------------------------------------------------------------------

@event.listens_for(Base.metadata, "after_create")
def _create_triggers_and_views(target, connection, **kw) -> None:
    for stmt in DDL_STATEMENTS:
        connection.exec_driver_sql(stmt)
