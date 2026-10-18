# HuskyPoll backend

The HuskyPoll backend has two parts:

- `huskypoll_db` is the SQLite database layer: the schema, the rules the
  database enforces, roster import, the HuskyCT export and demo data
  (SQLAlchemy 2).
- `huskypoll_api` is the web API the frontend talks to (FastAPI): UConn login,
  courses, rosters, question banks, images, live polls with QR codes and
  real-time updates, students' history and exports.
## Run it (without the frontend)
"run these commands from database_code/"

python -m pip install -r requirements.txt
 $env:HUSKYPOLL_DEV_LOGIN="1"
python -m uvicorn huskypoll_api.main:app --reload

## Run it (with the frontend)

The repository has two folders side by side, `frontend/` (React + Vite) and
`database_code/` (this backend). For development, run each in its own terminal:

```powershell
# Terminal 1, in database_code/   (Mac/Linux: export VAR=value instead of $env:)
pip install -r requirements.txt
$env:HUSKYPOLL_DEV_LOGIN="1"; $env:HUSKYPOLL_SITE_URL="http://localhost:5173"
python -m uvicorn huskypoll_api.main:app --reload

# Terminal 2, in frontend/
npm install
npm run dev
```

Open **http://localhost:5173**. Vite forwards everything under `/api`,
including live updates, to the backend on port 8000. The browser therefore
sees one address, and login cookies work without any cross-site setup.
`HUSKYPOLL_SITE_URL` tells the backend which address people use, so the join
links, QR codes and login redirects it creates point at the frontend.

The API's interactive docs are at **http://localhost:5173/api/docs** (or
http://localhost:8000/api/docs). Every endpoint is listed there and can be
tried in the browser. Log in first with `POST /auth/dev-login`, for example
`{"email": "pat.prof@uconn.edu", "net_id": "prf00001", "role": "instructor"}`.
The database is created on first start.

`HUSKYPOLL_DEV_LOGIN=1` lets anyone log in as anyone, with any role. It's for
development and testing until UConn ITS registers the app for CAS/Entra login,
and must never be turned on for a real course.

## Database tools

```bash

python -m huskypoll_db seed-demo --roster samples/studentadmin-template.xlsx   # demo database
python -m huskypoll_db init                                                    # or an empty one
python -m pytest -q                                                            # 100 tests (database + API)
```

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
| `python -m huskypoll_db set-role NETID ROLE` | Make someone `admin`, `instructor`, `ta`, `student` or `guest` |
| `python -m huskypoll_db users [--role ROLE]` | List accounts and their roles |
| `python -m huskypoll_db schema` | Print every CREATE statement (same as `schema.sql`) |
| `python scripts/demo_tour.py` | Guided 14-step tour of every feature, pausing after each step (`--no-pause`, `--keep tour.db`) |
| `python scripts/simulate_lecture.py --students 500` | Load test: 500 students answering one poll |

## Layout

```
huskypoll_api/
  main.py       entry point: uvicorn huskypoll_api.main:app
  app.py        builds the app: settings, middleware, error handling, routers
  site.py       path-prefix handling; serves the built frontend at SITE_URL/
  config.py     settings from environment variables (see below)
  deps.py       database session per request, current user, permission checks
  live.py       WebSocket hub for live updates
  schemas.py    request/response shapes (shown at /docs)
  serializers.py  turns rows into responses; hides answer keys from students
  routers/      auth, courses (+ roster, sessions, exports), questions (+ banks, images), polls
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
tests/          pytest suite (test_database.py, test_api.py)
samples/        StudentAdmin roster template
docs/           huskypoll-schema.drawio (open at app.diagrams.net)
deploy/         full-stack Dockerfile, docker-compose and nginx examples
Dockerfile      one-container deployment
```

## API settings

All settings are environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `HUSKYPOLL_SITE_URL` | `http://localhost:8000` | Full address of the site, **including any path prefix**. Pages at `SITE_URL/`, API at `SITE_URL/api` |
| `HUSKYPOLL_FRONTEND_DIST` | none | The built frontend (`frontend/dist`). When set, the backend serves the pages too |
| `HUSKYPOLL_PUBLIC_URL` | `SITE_URL/api` | Full address of the API, only if it isn't `SITE_URL/api` |
| `HUSKYPOLL_FRONTEND_URL` | `SITE_URL` | Full address of the pages, only if they're served somewhere else |
| `HUSKYPOLL_SECRET_KEY` | random at each start | Signs login cookies. Set it in production, or logins reset on restart |
| `HUSKYPOLL_DB` | `huskypoll.db` | Database file |
| `HUSKYPOLL_MEDIA_DIR` | `media` | Folder for uploaded images |
| `HUSKYPOLL_CAS_URL` | `https://login.uconn.edu/cas` | UConn CAS server (confirm with ITS) |
| `HUSKYPOLL_DEV_LOGIN` | `0` | `1` enables `/auth/dev-login`. Never on a real course |
| `HUSKYPOLL_CORS_ORIGINS` | none | Frontend dev server origins if they differ, e.g. `http://localhost:5173` |
| `HUSKYPOLL_ADMIN_NETIDS` | none | NetIDs made admins when they log in |
| `HUSKYPOLL_INSTRUCTOR_NETIDS` | none | NetIDs made (at least) instructors when they log in |
| `HUSKYPOLL_SECURE_COOKIES` | `0` | `1` sends cookies over HTTPS only (set in production) |

## Running under a path, not just a domain

The app never assumes it's at the root of a domain. Put the site's full
address, path included, in `HUSKYPOLL_SITE_URL`:

```
HUSKYPOLL_SITE_URL=https://huskypoll.cse.uconn.edu                  # domain root
HUSKYPOLL_SITE_URL=https://huskypoll.cse.uconn.edu/cse1010          # one course
HUSKYPOLL_SITE_URL=https://huskypoll.cse.uconn.edu/test-version1    # a test copy
```

That gives you:

- **Pages** at `.../cse1010/`.
- **The API** at `.../cse1010/api`, with its docs at `.../cse1010/api/docs`.
- **Everything the server creates uses the prefix:** the login cookie (scoped
  to `/cse1010/api`), the UConn login return address, image links, QR codes and
  join links (`.../cse1010/join/ABCDE`).
- **Either proxy style works.** The reverse proxy may pass the prefix through
  or strip it.
- **Copies are independent.** Several copies can share one domain under
  different paths, each with its own database and logins.

**One frontend build works under every prefix.** Vite builds it with relative
paths. When the backend serves `index.html`, it adds `<base href="/cse1010/">`
and `window.__HUSKYPOLL__ = {basePath, apiBase}`, so nothing is rebuilt per
course. Deep links like `.../cse1010/courses/3` load correctly.

**For the frontend team.** Never hard-code `/` or a domain. The `frontend/src`
helpers already handle this:

| File | Use it for |
| --- | --- |
| `src/config.js` | `API_BASE`, `BASE_PATH` (the router's `basename`), `pagePath('/courses/3')` |
| `src/api.js` | `api.get/post/patch/delete/upload`, `api.me()`, `api.loginUrl(next)`, `api.qrUrl(pollId)`, `api.exportUrl(courseId)`; throws `ApiError` with `.status` and a readable message |
| `src/live.js` | `connectCourse(courseId, onMessage)` for live updates, with automatic reconnect |

- **Use the URLs the API returns as they are.** That means `join_url` (a
  frontend page: build a `/join/:code` route) and image `url`s.
- **Pass `next` relative to the site.** For login, send people to
  `api.loginUrl('/courses/3')`. The `next` path is relative to the site
  (`/courses/3`, not `/cse1010/courses/3`).
- **If you add React Router,** use `<BrowserRouter basename={BASE_PATH}>`.

## API overview

All paths below are relative to the API address (`SITE_URL/api`): `GET /me`
means `https://huskypoll.cse.uconn.edu/cse1010/api/me`. Full details and a
try-it-out page are at `SITE_URL/api/docs`.

| Area | Endpoints |
| --- | --- |
| Login | `GET /auth/login` (UConn CAS), `POST /auth/dev-login`, `POST /auth/logout`, `GET /me` |
| Roles (admins) | `GET /users?q=&role=`, `PATCH /users/{id}/role` |
| Courses | `GET/POST /courses`, `GET/PATCH/DELETE /courses/{id}`, `POST /courses/{id}/archive`, `/unarchive` |
| Instructors | `GET/POST /courses/{id}/instructors`, `DELETE /courses/{id}/instructors/{user_id}` |
| Roster | `GET/POST /courses/{id}/roster`, `POST .../roster/paste`, `POST .../roster/import` (.xlsx), `DELETE .../roster/{user_id}` |
| Lectures | `GET/POST /courses/{id}/sessions`, `PATCH/DELETE /sessions/{id}` |
| Questions | `GET/POST /banks`, `GET/PATCH/DELETE /banks/{id}`, `POST /banks/{id}/copy`, `POST /questions`, `GET/PATCH/DELETE /questions/{id}`, `POST /questions/{id}/copy` |
| Images | `POST /media` (upload or paste), `GET /media/{sha256}` |
| Polls | `POST /courses/{id}/polls`, `POST /courses/{id}/polls/quick`, `POST /courses/{id}/polls/set` (several questions asked one at a time), `POST /polls/{id}/open` (next question, same code), `DELETE /polls/{id}` (unopened only), `GET /courses/{id}/polls`, `GET /polls/by-code/{code}`, `GET/PATCH /polls/{id}`, `POST /polls/{id}/close`, `POST /polls/{id}/regrade`, `GET /polls/{id}/results`, `GET /polls/{id}/responses`, `GET /polls/{id}/qr.svg` / `qr.png` |
| Students | `POST /polls/{id}/responses` (answer; the reply is the confirmation), `GET /courses/{id}/history`, `GET /courses/{id}/my-participation` |
| Grades and logs | `GET /courses/{id}/export/huskyct.csv`, `/export/sessions.csv`, `GET /courses/{id}/participation`, `GET /courses/{id}/events` |
| Live updates | WebSocket `/ws/courses/{id}`: `poll_opened`, `poll_closed`, `results` (results go to students only when shown) |

Students never see the answer key, the explanation, or whether they were
right until a poll closes.

## Deployment

One container serves the pages and the API. Build it from the **repository
root**, the folder that holds `frontend/` and `database_code/`:

```bash
docker build -f database_code/deploy/Dockerfile.fullstack -t huskypoll .
docker run -d -p 127.0.0.1:8001:8000 -v huskypoll-cse1010:/data \
  -e HUSKYPOLL_SITE_URL=https://huskypoll.cse.uconn.edu/cse1010 \
  -e HUSKYPOLL_SECRET_KEY=... -e HUSKYPOLL_SECURE_COOKIES=1 huskypoll
```

The same image runs any copy: only `HUSKYPOLL_SITE_URL` and the volume differ.
`deploy/docker-compose.yml` runs `/cse1010` and `/test-version1` side by side,
and `deploy/nginx-huskypoll.conf` is the matching nginx setup. For the API
alone, there's a `Dockerfile` in this folder.

The container applies migrations (`alembic upgrade head`) and starts **one**
server process. Don't add `--workers`: SQLite has one writer, and live updates
are delivered inside that one process. The database and images live on the
`/data` volume, which is what to back up.

## Who can log in

`services.record_login(email=..., net_id=...)` is called after UConn login. It
accepts anyone whose email is one of:

| Email shape | Example | NetID comes from |
| --- | --- | --- |
| `firstname.lastname@uconn.edu` | `jonathan.smith@uconn.edu` | UConn login |
| `firstname.middleinitial.lastname@uconn.edu` | `jonathan.q.smith@uconn.edu` | UConn login |
| `netid@uconn.edu` | `abc12345@uconn.edu` | The email itself (or UConn login; they must match) |

Case doesn't matter, and name parts may contain hyphens (`mary-kate.smith-jones`).
Anything else is refused with a friendly message: other domains (including
subdomains like `health.uconn.edu`), a full middle name, digits in a name, and
so on. Every logged-in user ends up with a NetID; if none can be determined the
login is refused. Roster rows may have no NetID until the student's first login,
when the NetID is filled in. An email that already belongs to one NetID can't be
used to log in with a different one.

## Roles

Every account has one **role**, its account type, in `users.role`:

| Role | What it allows | How someone gets it |
| --- | --- | --- |
| `admin` | Everything, in every course; changing roles | `set-role` command, `HUSKYPOLL_ADMIN_NETIDS`, or another admin |
| `instructor` | Create courses (and run the ones they're in) | An admin, `HUSKYPOLL_INSTRUCTOR_NETIDS`, or being added as a course's instructor |
| `ta` | Write questions and upload images; run polls in courses they're added to | Being added as a course's TA, or an admin |
| `student` | Answer polls and see history in their courses | Being on a roster |
| `guest` | Log in; nothing else until added to a course | The default for a new login |

Roles only go **up** automatically. Being added to a roster makes a guest a
student, and being added as a TA makes a student a TA. Nothing lowers a role
except an admin, and the last admin can't be removed.

The account role is separate from a person's role **in a particular course**
(owner, instructor or TA in `course_instructors`, or student on the roster).
A graduate student can be a TA in one course and a student in another, so what
someone may do inside a course is still decided by their role in that course.

**First setup on a new server:** `python -m huskypoll_db set-role abc12345 admin`
(or set `HUSKYPOLL_ADMIN_NETIDS`). The admin then makes professors instructors
on the website (`PATCH /users/{id}/role`), or with `set-role NETID instructor`.

## Rules the database enforces

These rules are enforced by the database itself, so a bug in the API cannot
break them:

- **Valid values only.** Roles, statuses and question types are checked. A user
  must have a NetID, email or student ID. A NetID must be 3 letters followed by
  5 numbers (e.g. `abc12345`); `services` raises a friendly error for anything
  else, and roster imports list bad NetIDs as skipped rows. Anyone who has logged
  in must have a NetID. NetIDs and emails are stored in lowercase.
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

Alembic does not detect changes to triggers, views or CHECK constraints. Add
those to the migration yourself (`op.execute(...)`, `batch_op.create_check_constraint(...)`).

Migrations run with foreign keys switched off (see `migrations/env.py`). SQLite
changes a table by rebuilding it, and with foreign keys on, dropping the old
`users` table would delete every enrollment and answer. After each migration,
`env.py` runs a foreign-key check and rolls back if anything is broken.

## Performance (from `scripts/simulate_lecture.py`, 500 students)

| Scenario | Result |
| --- | --- |
| Answers arrive over 20 s (realistic) | 500/500 stored; median 5 ms, slowest 1% under 20 ms |
| All 500 at the same instant (worst case) | 500/500 stored, no errors, all done in about 3 s |

For deployment: run one backend container, keep `huskypoll.db` on a local
Docker volume (not a network drive), and back it up with `sqlite3 huskypoll.db
".backup backup.db"` or Litestream. Copying the file while the app is running
can produce a corrupt backup.

## Demo accounts

`seed-demo` creates `adm00001` (admin), `prf00001` (instructor, owns the demo
course) and `tas00001` (TA), so for example: `python -m huskypoll_db delete-course 1 --as prf00001`.

## Open items

- **Login email shapes.** Confirm with UConn ITS that these three cover everyone,
  e.g. whether duplicate names get addresses with numbers (`john.smith2@`), which
  are currently refused. The rule is `LOGIN_EMAIL_RE` in `services.py`.

- **HuskyCT column headers.** The export uses `Last Name, First Name, Username,
  Student ID, HuskyPoll Participation [Total Pts: N Score]`. Check these against
  a grade-center CSV downloaded from a test course.
- **Roster rows with only a student ID.** These can't be matched to a login
  unless CAS/Entra sends the student ID. Rows with a NetID or email match
  automatically.
- **Assigning instructors automatically.** If UConn's login service reports
  whether someone is faculty or staff, new faculty could become instructors
  automatically (in `routers/auth.py`). Until then an admin assigns them.
- **UConn login details.** Confirm the CAS server URL and attribute names (email,
  first and last name) with ITS, or switch to Entra ID when ITS registers the app.
  Only `routers/auth.py` changes.
- **Docker image.** Each step of `Dockerfile.fullstack` was tested on its own
  (`npm ci`, `npm run build`, migrating, serving the built app at a sub-path in
  a real browser), but the image itself hasn't been built yet. Build it once on
  a machine with Docker.
