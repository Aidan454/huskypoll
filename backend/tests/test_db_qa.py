"""Lecture Q&A storage: messages survive, and deleting a course removes them.

Run with: python -m pytest -q tests/test_db_qa.py
"""

from __future__ import annotations

from app.database import services as svc
from app.database.models import CourseQuestion, CourseReply


def test_lecture_qa_retention_and_cascade(db, course_setup):
    prof, course, student, _, _ = course_setup
    session = svc.create_session(db, course, title="Lecture discussion")
    q = svc.post_lecture_message(db, session, student, " Question ")
    reply = svc.post_lecture_message(db, session, prof, "Answer", question=q)
    qid, rid = q.id, reply.id
    db.commit()
    db.expire_all()
    assert db.get(CourseQuestion, qid).body == "Question"
    assert db.get(CourseReply, rid).body == "Answer"
    svc.delete_course(db, course, prof)
    db.flush()
    db.expunge_all()
    assert db.get(CourseQuestion, qid) is None
    assert db.get(CourseReply, rid) is None
