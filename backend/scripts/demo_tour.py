"""Guided tour of the HuskyPoll database - run it to show what the database can do.

    python scripts/demo_tour.py              # pauses after each step (press Enter)
    python scripts/demo_tour.py --no-pause   # runs straight through
    python scripts/demo_tour.py --keep tour.db   # keep the database afterwards to explore

Uses a throwaway database, so it never touches huskypoll.db.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import sys
import tempfile
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database import services as svc
from app.database.database import init_db, make_engine, make_session_factory
from app.database.export import per_session_csv, write_huskyct_csv
from app.database.models import QuestionBank
from app.database.roster import import_identifiers, import_studentadmin_xlsx

ap = argparse.ArgumentParser()
ap.add_argument("--no-pause", action="store_true")
ap.add_argument("--keep", metavar="FILE", help="save the tour database to FILE")
args = ap.parse_args()

step_no = 0


def step(title: str) -> None:
    global step_no
    step_no += 1
    if step_no > 1 and not args.no_pause:
        input("\n   [Enter for next step] ")
    print(f"\n{'=' * 72}\n {step_no}. {title}\n{'=' * 72}")


def say(msg: str = "") -> None:
    print(f"   {msg}")


def blocked(db, sql: str, params: dict | None = None) -> None:
    """Try SQL that breaks a rule and show the database refusing it."""
    try:
        with db.begin_nested():
            db.execute(text(sql), params or {})
        say(f"!! NOT blocked: {sql}")
    except IntegrityError as exc:
        say(f"BLOCKED -> {exc.orig!s}")


def refused(fn, *a, **kw) -> None:
    try:
        fn(*a, **kw)
        say("!! not refused")
    except svc.HuskyPollError as exc:
        say(f"REFUSED -> {exc}")


def rows(db, sql: str, params: dict | None = None) -> None:
    result = db.execute(text(sql), params or {})
    cols = list(result.keys())
    data = [[("" if v is None else str(v)) for v in r] for r in result]
    widths = [max(len(c), *(len(r[i]) for r in data)) if data else len(c) for i, c in enumerate(cols)]
    say("  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    say("  ".join("-" * w for w in widths))
    for r in data:
        say("  ".join(v.ljust(w) for v, w in zip(r, widths)))


db_path = Path(args.keep) if args.keep else Path(tempfile.mkdtemp()) / "tour.db"
if db_path.exists():
    sys.exit(f"{db_path} already exists - pick another name")
engine = make_engine(db_path)
Session = make_session_factory(engine)

# ---------------------------------------------------------------------------
step("Create the database")
init_db(engine)
db = Session()
tables = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")).scalars().all()
triggers = db.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'")).scalar()
say(f"{len(tables)} tables: {', '.join(tables)}")
say(f"{triggers} triggers and 2 views enforce the rules shown later.")
say(f"Journal mode: {db.execute(text('PRAGMA journal_mode')).scalar()}  "
    f"(WAL - students answering never block the live results)")

# ---------------------------------------------------------------------------
step("Instructor logs in with UConn credentials and creates a course")
prof = svc.record_login(db, net_id="PRF00001", email="pat.prof@uconn.edu", first_name="Pat", last_name="Professor")
say(f"Logged in: {prof.display_name} (NetID 'PRF00001' stored lowercase: '{prof.net_id}')")
say("Who can log in - the email decides:")
for email in ("pat.q.prof@uconn.edu", "abc12345@uconn.edu", "pat.prof@gmail.com", "pat@uconn.edu",
              "pat.quinn.prof@uconn.edu"):
    try:
        with db.begin_nested() as sp:
            u = svc.record_login(db, email=email, net_id=None if "12345" in email else "pqp00001")
            say(f"  {email:<26} accepted -> NetID {u.net_id}")
            sp.rollback()
    except svc.HuskyPollError as exc:
        say(f"  {email:<26} REFUSED -> {exc}")
say(f"New accounts start as '{prof.role}'. An admin makes professors instructors (once):")
svc.set_role(db, prof, "instructor")  # in the app: PATCH /users/{id}/role, or `python -m app.database set-role`
say(f"  {prof.net_id} is now '{prof.role}' and can create courses")
course = svc.create_course(db, prof, term="Spring 2027", subject="cse", catalog="2050", section="001",
                           title="Data Structures", points_participation=1, points_correct=1)
say(f"Created {course.code} - join code {course.join_code}")
say(f"Grading: {course.points_participation:g} pt for answering + {course.points_correct:g} pt if correct")
ta = svc.record_login(db, net_id="tas00001", email="terry.assistant@uconn.edu", first_name="Terry", last_name="Assistant")
svc.add_instructor(db, course, ta, role="ta")
say("Added a second instructor (TA):")
rows(db, "SELECT u.net_id, ci.role FROM course_instructors ci JOIN users u ON u.id = ci.user_id")

# ---------------------------------------------------------------------------
step("Import the roster (StudentAdmin spreadsheet + a pasted list)")
res = import_studentadmin_xlsx(db, course, ROOT / "samples" / "studentadmin-template.xlsx", by=prof)
say(f"StudentAdmin file: {res.summary()}")
pasted = "\n".join([f"stu{n:05d}" for n in range(1, 9)] + ["late.student@uconn.edu"])
res = import_identifiers(db, course, pasted, by=prof)
say(f"Pasted list (NetIDs + an email): {res.summary()}")
rows(db, "SELECT u.net_id, u.student_id, u.email, e.section, e.source FROM enrollments e "
         "JOIN users u ON u.id = e.user_id ORDER BY u.id LIMIT 4")
say("...")
student = svc.record_login(db, net_id="LSX12345", email="Late.Student@uconn.edu", first_name="Lee")
say(f"First login by late.student@uconn.edu -> matched to the roster row (user {student.id}), "
    f"no duplicate account. Enrolled: {svc.is_enrolled(db, course, student)}")
NAMES = [("Ava", "Nguyen"), ("Liam", "Patel"), ("Maya", "Garcia"), ("Noah", "Kim"), ("Priya", "Silva"),
         ("Ethan", "Cohen"), ("Sofia", "Okafor"), ("Omar", "Rossi")]
students = [svc.record_login(db, net_id=f"stu{n:05d}", email=f"{f}.{l}@uconn.edu", first_name=f, last_name=l)
            for n, (f, l) in enumerate(NAMES, start=1)] + [student]
student.last_name = "Student"
say("The other pasted students log in too; their names now come from UConn login.")

# ---------------------------------------------------------------------------
step("Build a question bank - four question types")
bank = QuestionBank(owner_id=prof.id, course_id=course.id, name="Week 1")
db.add(bank)
db.flush()
q_mc = svc.create_question(db, prof, bank=bank, type="mc_single",
                           body_md="Worst-case search time in a **balanced** BST?",
                           options=[("O(1)", False), ("O(log n)", True), ("O(n)", False)],
                           explanation_md="A balanced tree has height O(log n).")
q_multi = svc.create_question(db, prof, bank=bank, type="mc_multi", body_md="Which sorts are stable?",
                              options=[("Merge sort", True), ("Quick sort", False), ("Insertion sort", True)])
q_num = svc.create_question(db, prof, bank=bank, type="numeric", body_md="Edges in a tree with 10 vertices?",
                            numeric_answer=9, numeric_tolerance=0)
q_text = svc.create_question(db, prof, bank=bank, type="free_text", body_md="Which structure is LIFO?",
                             text_answer="stack")
rows(db, "SELECT id, type, body_md, numeric_answer, text_answer FROM questions")

# ---------------------------------------------------------------------------
step("Open a poll in lecture")
poll = svc.open_poll(db, course, q_mc, prof)
say(f"Poll open. Students enter code {poll.access_code} (or scan the QR code).")
say(f"Lecture session created automatically: '{poll.session.title}' (is_auto={poll.session.is_auto})")
say(f"Question is now locked: is_locked={q_mc.is_locked}")
found = svc.find_open_poll_by_code(db, poll.access_code.lower())
say(f"Student types '{poll.access_code.lower()}' -> finds poll {found.id} (case doesn't matter)")

# ---------------------------------------------------------------------------
step("Students answer - with automatic marking and a confirmation")
opts = {o.text_md: o.id for o in q_mc.options}
picks = ["O(log n)"] * 6 + ["O(n)", "O(1)"]
for s, pick in zip(students, picks):
    svc.submit_response(db, poll, s, option_ids=[opts[pick]])
r = svc.submit_response(db, poll, students[-1], option_ids=[opts["O(n)"]])
say(f"Confirmation for {students[-1].email}: received at {r.submitted_at:%H:%M:%S} UTC, correct={r.is_correct}")
r = svc.submit_response(db, poll, students[-1], option_ids=[opts["O(log n)"]])
say(f"They change their answer while the poll is open -> same row updated, correct={r.is_correct}")
say("Live results (v_poll_option_counts):")
rows(db, "SELECT o.text_md AS option, v.votes, v.is_correct FROM v_poll_option_counts v "
         "JOIN question_options o ON o.id = v.option_id WHERE v.poll_id = :p ORDER BY v.position",
     {"p": poll.id})

# ---------------------------------------------------------------------------
step("Rules the app enforces (friendly error messages)")
outsider = svc.record_login(db, email="out99999@uconn.edu")
say("Someone not on the roster tries to answer:")
refused(svc.submit_response, db, poll, outsider, option_ids=[opts["O(1)"]])
say("A student tries to open a poll:")
refused(svc.open_poll, db, course, q_multi, students[0])
say("A student picks two options on a single-answer question:")
refused(svc.submit_response, db, poll, students[0], option_ids=[opts["O(1)"], opts["O(n)"]])

# ---------------------------------------------------------------------------
step("Rules the DATABASE enforces (even if the app has a bug)")
say("Second answer from the same student to the same poll:")
blocked(db, "INSERT INTO responses (poll_id, user_id, submitted_at, updated_at) "
            "VALUES (:p, :u, '2027-01-01', '2027-01-01')", {"p": poll.id, "u": students[0].id})
say("Rewording a question students already answered:")
blocked(db, "UPDATE questions SET body_md = 'something else' WHERE id = :q", {"q": q_mc.id})
say("Invalid value (typo in a status):")
blocked(db, "UPDATE polls SET status = 'opne' WHERE id = :p", {"p": poll.id})
say("Editing the audit log:")
blocked(db, "UPDATE event_log SET event_type = 'nothing happened'")
svc.close_poll(db, poll, prof)
say("Poll closed. A late answer straight into the database:")
blocked(db, "INSERT INTO responses (poll_id, user_id, submitted_at, updated_at) "
            "VALUES (:p, :u, '2027-01-01', '2027-01-01')", {"p": poll.id, "u": outsider.id})

# ---------------------------------------------------------------------------
step("Quick in-lecture question, answer added after class, then regrade")
quick = svc.create_question(db, prof, type="mc_single", body_md="(typed in lecture) Best structure for undo?",
                            options=[("Queue", False), ("Stack", False), ("Heap", False)])
p2 = svc.open_poll(db, course, quick, prof)
for i, s in enumerate(students):
    svc.submit_response(db, p2, s, option_ids=[quick.options[1 if i % 3 else 0].id])
svc.close_poll(db, p2, prof)
say(f"No answer key yet -> is_correct for all: {sorted({str(r.is_correct) for r in p2.responses})}")
quick.options[1].is_correct = True  # instructor adds the answer
db.flush()
changed = svc.regrade_poll(db, p2)
say(f"Instructor marks 'Stack' correct and regrades -> {changed} responses re-marked")
say(f"Now: {sum(1 for r in p2.responses if r.is_correct)} correct, "
    f"{sum(1 for r in p2.responses if r.is_correct is False)} wrong")

# ---------------------------------------------------------------------------
step("Other question types, in a second lecture")
lec2 = svc.get_or_create_session(db, course, on_date=dt.date.today() + dt.timedelta(days=2), title="Lecture 2")
p3 = svc.open_poll(db, course, q_multi, prof, lecture_session=lec2)
svc.submit_response(db, p3, students[0], option_ids=[q_multi.options[0].id, q_multi.options[2].id])
svc.submit_response(db, p3, students[1], option_ids=[q_multi.options[0].id])
svc.close_poll(db, p3, prof)
p4 = svc.open_poll(db, course, q_num, prof, lecture_session=lec2)
svc.submit_response(db, p4, students[0], numeric_answer=9)
svc.submit_response(db, p4, students[1], numeric_answer=10)
svc.close_poll(db, p4, prof)
p5 = svc.open_poll(db, course, q_text, prof, lecture_session=lec2)
svc.submit_response(db, p5, students[0], text_answer="  Stack ")
svc.submit_response(db, p5, students[1], text_answer="queue")
svc.close_poll(db, p5, prof)
rows(db, "SELECT u.net_id, q.type, r.numeric_answer, r.text_answer, r.is_correct FROM responses r "
         "JOIN users u ON u.id = r.user_id JOIN polls p ON p.id = r.poll_id JOIN questions q ON q.id = p.question_id "
         "WHERE p.session_id = :s ORDER BY p.id, u.id", {"s": lec2.id})
say("Select-all needs every right option; ' Stack ' matches 'stack' (spaces/case ignored).")

# ---------------------------------------------------------------------------
step("Reuse questions: edit a locked question, copy a bank to next semester")
v2 = svc.copy_question(db, q_mc, prof)
v2.body_md = "Worst-case search time in a balanced BST with n keys?"
db.flush()
say(f"Locked question {q_mc.id} copied to {v2.id} (copied_from_id={v2.copied_from_id}) and reworded freely.")
fall = svc.create_course(db, prof, term="Fall 2027", subject="CSE", catalog="2050", title="Data Structures")
bank2 = svc.copy_bank(db, bank, prof, name="Week 1 (Fall 2027)", course=fall)
say(f"Whole bank copied to {fall.code}: {len(bank2.questions)} questions, all editable.")

# ---------------------------------------------------------------------------
step("Students' participation and the HuskyCT export")
say("Per-student, per-poll scores (v_poll_scores), first student:")
rows(db, "SELECT session_date, poll_id, answered, is_correct, points, points_possible FROM v_poll_scores "
         "WHERE user_id = :u ORDER BY poll_id", {"u": students[0].id})
buf = io.StringIO()
write_huskyct_csv(db, course, buf, by=prof)
say("")
say("HuskyCT grade file (first lines):")
for line in buf.getvalue().splitlines()[:5]:
    say(f"  {line}")
say("")
say("Per-lecture review sheet (first lines):")
for line in per_session_csv(db, course).splitlines()[:4]:
    say(f"  {line}")

# ---------------------------------------------------------------------------
step("The audit log")
rows(db, "SELECT event_type, COUNT(*) AS n FROM event_log GROUP BY event_type ORDER BY n DESC")
say("")
say("Most recent entries:")
rows(db, "SELECT e.occurred_at, e.event_type, u.net_id, e.poll_id FROM event_log e "
         "LEFT JOIN users u ON u.id = e.user_id ORDER BY e.id DESC LIMIT 5")

# ---------------------------------------------------------------------------
step("End of semester: archive, then delete")
svc.archive_course(db, course, prof)
say(f"Archived {course.code}: hidden, nothing lost (archived_at set). Reversible with unarchive_course().")
say("The TA tries to delete it:")
refused(svc.delete_course, db, course, ta)
summary = svc.delete_course(db, course, prof)
say(f"Owner deletes it: {summary}")
left = {t: db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
        for t in ("courses", "polls", "responses", "question_banks", "questions", "users", "event_log")}
say(f"Left in the database: {left}")
say("Polls and answers are gone; questions, accounts and the log remain (the Fall 2027 course too).")

db.commit()
db.close()
engine.dispose()
print(f"\n{'=' * 72}")
if args.keep:
    print(f" Done. Explore the result: open {db_path} in VS Code (SQLite Viewer).")
else:
    print(" Done. (Run with --keep tour.db to save the database and explore it.)")
