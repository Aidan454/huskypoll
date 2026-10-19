# HuskyPoll frontend

React + Vite pages for HuskyPoll. Everything talks to the backend API in
`backend` (see its README for the full API).

## Run it

```powershell
# Terminal 1, in backend/
$env:HUSKYPOLL_DEV_LOGIN="1"; $env:HUSKYPOLL_SITE_URL="http://localhost:5173"
python -m uvicorn app.main:app --reload

# Terminal 2, in frontend/
npm install
npm run dev
```

Open http://localhost:5173. Vite forwards `/api` (live updates included) to the
backend on port 8000. With Docker, `docker compose up` sets `VITE_API_BASE` instead.
For demo data run `python -m app.database seed-demo` in the backend folder, then use the
Instructor / TA / Admin / Student buttons on the login page.

## Pages

| Path | Who | What |
| --- | --- | --- |
| `/login` | everyone | UConn login, plus developer login when `HUSKYPOLL_DEV_LOGIN=1` |
| `/courses` | everyone | Courses you teach or are enrolled in; create a course |
| `/courses/:id` | staff | Open a poll from a bank or a quick poll; live polls; all polls by lecture |
| `/courses/:id` | students | Answer the live poll, participation totals, history with answers and marks |
| `/courses/:id/live` | staff | A poll with several questions: students see one at a time; close it, show results, then Next question (same code) |
| `/courses/:id/lectures` | staff | Add, rename, re-date and delete lectures |
| `/courses/:id/roster` | staff | Roster, add by pasted list / StudentAdmin .xlsx / one student, drop |
| `/courses/:id/staff` | staff | Add or remove instructors and TAs |
| `/courses/:id/grades` | staff | Points per student, HuskyCT and per-lecture CSV downloads |
| `/courses/:id/activity` | staff | Course event log |
| `/courses/:id/settings` | staff | Title, section, points; archive; delete (owner/admin) |
| `/polls/:id` | staff | Classroom view: code, QR, live result bars, show results, close, answer key and re-mark |
| `/polls/:id` | students | Answer it, or see the mark once closed |
| `/join`, `/join/:code` | everyone | Enter a poll code (the QR code opens `/join/CODE`); follows a multi-question poll question by question |
| `/banks`, `/banks/:id` | instructors, TAs | Question banks; write, edit, copy and delete questions, with pictures |
| `/admin/users` | admins | Find accounts and change their role |

## Code layout

```
src/
  config.js      API_BASE, BASE_PATH, pagePath(): never hard-code "/" or a domain
  api.js         api.get/post/patch/delete/upload; throws ApiError with a readable message
  live.js        connectCourse(courseId, onMessage): WebSocket with reconnect
  hooks.js       useAuth(), useApi(path), useAction(fn)
  format.js      dates, labels, small helpers
  components/    layout, login guard, dialogs, question editor, poll pieces, Markdown
  pages/         one file per page; pages/course/ holds the course tabs
```
