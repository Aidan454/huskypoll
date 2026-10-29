# HuskyPoll feature list

What the app does today, and what is still planned. Based on the code on `main`
(backend in `backend/app`, frontend in `frontend/src`). When you add or finish a
feature, update this file in the same pull request.

Legend: ✅ done · 🟡 partly done · ⬜ not started

## Sign-in and accounts

| Feature | Status | Notes |
| --- | --- | --- |
| UConn CAS login (NetID) | ✅ | `GET /api/auth/login` → CAS → `/api/auth/cas/callback`. The only login on the server. |
| Developer login | ✅ | `POST /api/auth/dev-login`, log in as anyone with any role. On only when `HUSKYPOLL_DEV_LOGIN=1` (local `compose.yml`); off on the server. |
| Signed session cookie, logout, `GET /api/me` | ✅ | Cookie is scoped to the site's path prefix. |
| UConn email rules | ✅ | Only `first.last@`, `first.m.last@` or `netid@uconn.edu`. NetID must be 3 letters + 5 digits. |
| Microsoft (Entra ID) sign-in | ⬜ | Not coded. Waiting on UConn ITS to register the app. `routers/auth.py` is written so an OpenID Connect login can sit next to CAS. |
| HTTPS on the server | ⬜ | Site runs on `http://`. Once it has a certificate, set `HUSKYPOLL_SECURE_COOKIES=1` and switch `HUSKYPOLL_SITE_URL` to `https://`. |

## Roles and permissions

| Feature | Status | Notes |
| --- | --- | --- |
| Account roles: admin, instructor, TA, student, guest | ✅ | New logins are guests. Roles only go up automatically; only an admin lowers one; the last admin can't be removed. |
| Per-course roles: owner, instructor, TA, student | ✅ | What you can do in a course depends on your role in that course. |
| `set-role` command | ✅ | `python -m app.database set-role <netid> admin` (first admin on a new server). |
| Admins/instructors from env vars | ✅ | `HUSKYPOLL_ADMIN_NETIDS`, `HUSKYPOLL_INSTRUCTOR_NETIDS`. |
| Users page (admins) | ✅ | `/admin/users`: search users, filter by role, change roles. |

## Courses

| Feature | Status | Notes |
| --- | --- | --- |
| Create, edit, list courses | ✅ | Courses page, with filters. |
| Instructors & TAs tab | ✅ | Add or remove co-instructors and TAs. |
| Archive / unarchive a course | ✅ | Hides the course, keeps all data. |
| Delete a course | ✅ | Owner or admin only. Question banks are kept for reuse. |
| Lectures (sessions) tab | ✅ | Polls are grouped by lecture date. |
| Activity log tab | ✅ | Read-only event log (the database refuses edits to it). |

## Roster

| Feature | Status | Notes |
| --- | --- | --- |
| Import a StudentAdmin `.xlsx` roster | ✅ | Bad rows are listed as skipped. Template in `backend/samples/`. |
| Paste NetIDs / emails / student IDs | ✅ | |
| Add / remove single students | ✅ | |
| Students join a course on their own (course code) | ⬜ | Students are only added by staff today. |

## Questions

| Feature | Status | Notes |
| --- | --- | --- |
| Question banks (create, copy, share between courses) | ✅ | `/banks`. |
| Question types: single choice, multiple choice, free text, numeric (with tolerance) | ✅ | |
| Markdown in questions and choices | ✅ | |
| Images (upload, paste or drag and drop) | ✅ | Stored once by SHA-256 in the media folder. |
| Answer key and explanation | ✅ | Hidden from students until the poll closes. |
| Locked after polling | ✅ | Wording/choices freeze once polled; copy the question to change it. The answer key stays editable (then regrade). |

## Polls

| Feature | Status | Notes |
| --- | --- | --- |
| Start a poll from a saved question | ✅ | |
| Quick poll (no saved question) | ✅ | |
| Poll sets (several questions, one at a time, same code) | ✅ | |
| Join by short code, join link and QR code | ✅ | `/join`, `/join/:code`, `qr.svg` / `qr.png`. |
| Live tab for running a poll in class | ✅ | Open/close, live results chart, answer key. |
| Real-time updates over WebSocket | ✅ | `poll_opened`, `poll_closed`, `results`. |
| Show or hide results to students | ✅ | `show_results` per poll. |
| One answer per student; change it while open | ✅ | Enforced by the database. |
| Regrade after changing the answer key | ✅ | |
| Individual answers view for staff | ✅ | Poll page. |
| Poll timer / auto-close countdown | ⬜ | Polls are closed by hand. |
| Location or attendance checks (anti-cheating) | ⬜ | |

## Students

| Feature | Status | Notes |
| --- | --- | --- |
| Live poll on the course page | ✅ | |
| History of past polls with the correct answer | ✅ | |
| My participation summary | ✅ | |

## Grades and exports

| Feature | Status | Notes |
| --- | --- | --- |
| Grades tab | ✅ | Per student, per lecture. |
| Participation CSV export | ✅ | 100 for each lecture the student answered, 0 otherwise. Optional `?dates=` filter. |
| HuskyCT / Brightspace grade sync | ⬜ | Download the CSV and upload it by hand. |
| Correctness-based grading options in the export | ⬜ | Export is participation only. |

## Site and operations

| Feature | Status | Notes |
| --- | --- | --- |
| Single-container server deploy | ✅ | `compose.server.yml` + `Dockerfile.server`, live on huskypoll.cse.uconn.edu. |
| Runs under a path prefix (e.g. `/cse1010`) | ✅ | One build works for any prefix via `HUSKYPOLL_SITE_URL`. |
| Database migrations on start | ✅ | Alembic, `alembic upgrade head` in the container command. |
| Light / dark theme toggle | ✅ | |
| Demo data and demo mode | ✅ | `./scripts/demo.sh`, `python -m app.database seed-demo`. |
| Load test script | ✅ | `backend/scripts/simulate_lecture.py --students 500`. |
| CI: ruff + pytest, ESLint + build | ✅ | `.github/workflows/`. No frontend tests yet. |
| Frontend tests | ⬜ | |
| Automatic database backups | ⬜ | Back up the `huskypoll-data` Docker volume by hand for now. |
| Removing unused prototype components | ⬜ | See "Unused files" in `AGENTS.md`. |
