"""Fill a database with a realistic demo course so the frontend team has data to work against."""
from __future__ import annotations

import datetime as dt
import random
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from . import services as svc
from .models import Poll, QuestionBank
from .roster import import_records, import_studentadmin_xlsx

FIRST = ["Ava", "Liam", "Maya", "Noah", "Priya", "Ethan", "Sofia", "Lucas", "Chloe", "Omar",
         "Grace", "Mateo", "Zoe", "Ryan", "Aisha", "Jack", "Lena", "Owen", "Nina", "Caleb"]
LAST = ["Nguyen", "Smith", "Patel", "Garcia", "Kim", "Brown", "Rossi", "Cohen", "Okafor", "Silva",
        "Murphy", "Chen", "Lopez", "Walsh", "Haddad", "Turner", "Novak", "Reyes", "Singh", "Baker"]


def seed_demo(db: Session, *, students: int = 40, roster_xlsx: Optional[Path] = None, rng_seed: int = 7) -> dict:
    rng = random.Random(rng_seed)

    admin, _ = svc.find_or_create_user(db, net_id="adm00001", email="hpadmin@example.edu",
                                       first_name="HuskyPoll", last_name="Admin")
    admin.role = "admin"
    prof, _ = svc.find_or_create_user(db, net_id="prf00001", email="prof01@example.edu",
                                      first_name="Pat", last_name="Professor")
    prof.role = "instructor"
    ta, _ = svc.find_or_create_user(db, net_id="tas00001", email="ta01@example.edu",
                                    first_name="Terry", last_name="Assistant")

    course = svc.create_course(db, prof, term="Spring 2027", subject="CSE", catalog="2050",
                               section="001", title="Data Structures and Object-Oriented Design",
                               points_participation=1, points_correct=1)
    svc.add_instructor(db, course, ta, role="ta")

    # Roster: the real StudentAdmin layout (if given) plus generated students.
    if roster_xlsx:
        import_studentadmin_xlsx(db, course, roster_xlsx, by=prof)
    records = []
    for i in range(students):
        first, last = FIRST[i % len(FIRST)], LAST[(i * 7 + i // len(FIRST) * 3) % len(LAST)]
        net = f"{first[0]}{chr(ord('a') + i % 26)}{last[0]}{23000 + i}".lower()  # 3 letters + 5 digits
        records.append({"student_id": f"{3000000 + i}", "name": f"{last},{first}", "net_id": net,
                        "email": f"{first}.{last}{i}@example.edu".lower(),
                        "section": rng.choice(["011Lab", "012Lab"]), "_row": i + 2})
    import_records(db, course, records, by=prof)

    # A question bank.
    bank = QuestionBank(owner_id=prof.id, course_id=course.id, name="CSE 2050 - Week 1-3")
    db.add(bank)
    db.flush()
    qs = [
        svc.create_question(db, prof, bank=bank, type="mc_single",
                            body_md="What is the worst-case time to search a **balanced** BST with *n* keys?",
                            options=[("O(1)", False), ("O(log n)", True), ("O(n)", False), ("O(n log n)", False)],
                            explanation_md="Height of a balanced tree is O(log n)."),
        svc.create_question(db, prof, bank=bank, type="mc_multi",
                            body_md="Which of these are **stable** sorting algorithms? (select all)",
                            options=[("Merge sort", True), ("Quick sort", False), ("Insertion sort", True),
                                     ("Heap sort", False)]),
        svc.create_question(db, prof, bank=bank, type="numeric",
                            body_md="How many edges does a tree with 10 vertices have?",
                            numeric_answer=9, numeric_tolerance=0),
        svc.create_question(db, prof, bank=bank, type="free_text",
                            body_md="Name the data structure that is LIFO.", text_answer="stack"),
        svc.create_question(db, prof, bank=bank, type="mc_single",
                            body_md="How confident do you feel about recursion?",
                            options=[("Very", False), ("Somewhat", False), ("Not yet", False)]),  # survey: no key
    ]

    # Three past lectures, polls opened, answered by most students, closed.
    enrolled = [e.user for e in course.enrollments if e.status == "active"]
    start = dt.date(2027, 1, 20)
    polls: list[Poll] = []
    for week, q_idx in enumerate([(0, 4), (1, 2), (3, 0)]):
        lec = svc.get_or_create_session(db, course, on_date=start + dt.timedelta(days=7 * week))
        for qi in q_idx:
            q = qs[qi]
            if q.is_locked:  # asked before: reuse an editable copy, as instructors would
                q = svc.copy_question(db, q, prof)
            poll = svc.open_poll(db, course, q, prof, lecture_session=lec)
            for student in enrolled:
                if rng.random() < 0.15:  # absent
                    continue
                _answer_randomly(db, rng, poll, student)
            svc.close_poll(db, poll, prof)
            polls.append(poll)
    db.flush()
    return {"course": course, "instructor": prof, "students": len(enrolled), "polls": len(polls)}


def _answer_randomly(db: Session, rng: random.Random, poll: Poll, student) -> None:
    q = poll.question
    good = rng.random() < 0.7
    if q.type == "mc_single":
        correct = [o.id for o in q.options if o.is_correct]
        pick = correct[0] if (good and correct) else rng.choice(q.options).id
        svc.submit_response(db, poll, student, option_ids=[pick])
    elif q.type == "mc_multi":
        ids = [o.id for o in q.options if o.is_correct] if good else \
            rng.sample([o.id for o in q.options], k=rng.randint(1, len(q.options)))
        svc.submit_response(db, poll, student, option_ids=ids)
    elif q.type == "numeric":
        svc.submit_response(db, poll, student, numeric_answer=q.numeric_answer if good else rng.choice([8, 10, 11]))
    else:
        svc.submit_response(db, poll, student, text_answer="Stack" if good else rng.choice(["queue", "heap"]))
