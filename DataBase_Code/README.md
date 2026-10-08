# HuskyPoll database

This is the SQLite database layer for HuskyPoll. It contains the schema, the
rules the database enforces, roster import, the HuskyCT export and a demo data
set. It is written in Python with SQLAlchemy 2, so the FastAPI backend can
import it directly.

## Quick start

```bash
pip install -r requirements.txt

python -m huskypoll_db seed-demo --roster samples/studentadmin-template.xlsx   # demo database
python -m huskypoll_db init                                                    # or an empty one
python -m pytest -q                                                            # 26 tests
```
## A demo tour of the database
from database_code -> python scripts/demo_tour.py

`huskypoll.db` is created in the current folder. Set `HUSKYPOLL_DB=/path/to/file.db`
or pass `--db` to use another file.

| Command | What it does |
| --- | --- |
| `python -m huskypoll_db init` | Create an empty database (and mark it as up to date for Alembic) |
| `python -m huskypoll_db seed-demo` | Demo course: CSE 2050, 40 students, 5 questions, 6 closed polls over 3 lectures |
| `python -m huskypoll_db import-roster COURSE_ID roster.xlsx [--drop-missing]` | Import a StudentAdmin class roster |
| `python -m huskypoll_db export COURSE_ID out.csv [--per-session]` | Participation CSV for HuskyCT (or per-lecture breakdown) |
| `python -m huskypoll_db archive-course COURSE_ID --as NETID [--undo]` | Hide a finished course but keep all its data (reversible) |
| `python -m huskypoll_db delete-course COURSE_ID --as NETID [--delete-logs]` | Permanently delete a course (owner or admin only; asks you to confirm) |
| `python -m huskypoll_db schema` | Print every CREATE statement (same as `schema.sql`) |
| `python scripts/simulate_lecture.py --students 500` | Load test: 500 students answering one poll |

## Layout

```
huskypoll_db/
  database.py   engine + PRAGMAs (WAL, foreign keys, busy timeout)
  models.py     the 13 tables - the single source of truth for the schema
  triggers.py   triggers and views (rules a CHECK constraint can't express)
  services.py   operations the API calls: login, courses, questions, polls, responses, grading
  roster.py     StudentAdmin .xlsx import, pasted NetID/email/ID lists
  export.py     HuskyCT participation CSV
  seed.py       demo data
migrations/     Alembic (schema changes after the first release)
schema.sql      generated, read-only view of the schema
tests/          pytest suite
samples/        StudentAdmin roster template
```

## Using it from FastAPI

```python
from fastapi import Depends, FastAPI, HTTPException
from huskypoll_db import make_engine, make_session_factory
from huskypoll_db import services as svc

engine = make_engine()                      # reads HUSKYPOLL_DB
SessionLocal = make_session_factory(engine)
app = FastAPI()

def get_db():
    with SessionLocal.begin() as db:        # one request = one short transaction
        yield db

@app.post("/polls/{code}/respond")
def respond(code: str, option_ids: list[int], db=Depends(get_db), user=Depends(current_user)):
    poll = svc.find_open_poll_by_code(db, code)
    if poll is None:
        raise HTTPException(404, "No open poll with that code")
    try:
        resp = svc.submit_response(db, poll, user, option_ids=option_ids)
    except svc.HuskyPollError as e:
        raise HTTPException(400, str(e))
    return {"received": True, "submitted_at": resp.updated_at}   # the student's confirmation
```

The service functions call `flush()` but never `commit()`. The request's
transaction commits once, at the end.

## Rules the database enforces

These rules are enforced by the database itself, so a bug in the API cannot
break them:

- **Valid values only.** Roles, statuses and question types are checked. A user
  must have a NetID, email or student ID. NetIDs and emails are stored in
  lowercase.
- **One answer per student per poll.** Resubmitting while the poll is open
  updates the same row.
- **Answers only while the poll is open.** This is enforced by a trigger.
- **Valid choices only.** A choice must belong to the poll's question, and a
  single-answer question accepts only one choice.
- **Polled questions are locked.** When a poll opens, its question's wording,
  type, picture and choices are frozen. To change them, use
  `services.copy_question()`. The answer key and explanation stay editable, so
  an instructor can add the answer after class and then call
  `services.regrade_poll()`.
- **Access codes are unique among open polls only,** so short codes can be
  reused.
- **The event log can't be edited.** Rows can be deleted when the retention
  period ends, but never changed. The one exception is automatic: when a user,
  course or poll is deleted, log rows keep their details but lose the link to
  the deleted record.
- **Times are stored in UTC.** Every timestamp comes back timezone-aware.

Two views do common queries:
- `v_poll_scores`: one row per student per closed poll, with points. The export
  is built from it.
- `v_poll_option_counts`: live vote counts for the results bar chart.

## End of semester: archive or delete a course

| | Archive | Delete |
| --- | --- | --- |
| Function | `services.archive_course()` / `unarchive_course()` | `services.delete_course()` |
| Who | Any instructor of the course | Course owner or an admin |
| Course, roster, sessions, polls, answers | Kept, course hidden (`archived_at` set) | Permanently removed |
| Question banks and questions | Kept | Kept (unlinked from the course) for reuse next term |
| User accounts | Kept | Kept |
| Event log | Kept | Kept, unless `delete_logs=True` |
| Undo | `unarchive_course()` | Not possible, except from a backup |

Export the HuskyCT CSV before deleting, because the answers are gone afterwards.

## Changing the schema

1. Edit `huskypoll_db/models.py` (or `triggers.py` for triggers and views).
2. Run `alembic revision --autogenerate -m "add poll time limit"`, then read the
   generated file in `migrations/versions/`.
3. Run `alembic upgrade head` to apply it to an existing database without
   losing data.
4. Regenerate the readable copy: `python -m huskypoll_db schema > schema.sql`.

Alembic does not detect changes to triggers or views. Add those to the
migration yourself with `op.execute(...)`.

## Performance (from `scripts/simulate_lecture.py`, 500 students)

| Scenario | Result |
| --- | --- |
| Answers arrive over 20 s (realistic) | 500/500 stored; median 5 ms, slowest 1% under 20 ms |
| All 500 at the same instant (worst case) | 500/500 stored, no errors, all done in about 3 s |

For deployment: run one backend container, keep `huskypoll.db` on a local
Docker volume (not a network drive), and back it up with `sqlite3 huskypoll.db
".backup backup.db"` or Litestream. Copying the file while the app is running
can produce a corrupt backup.

## Open items

- **HuskyCT column headers.** The export uses `Last Name, First Name, Username,
  Student ID, HuskyPoll Participation [Total Pts: N Score]`. Check these against
  a grade-center CSV downloaded from a test course.
- **Roster rows with only a student ID.** These can't be matched to a login
  unless CAS/Entra sends the student ID. Rows with a NetID or email match
  automatically.
- **Additions since the diagram.** `media.size_bytes` and `polls.created_at` were
  added after the draw.io diagram was drawn.
