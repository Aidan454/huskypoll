# HuskyPoll
- [Trello](https://trello.com/b/h5MTrDfq/huskypoll)
- [Figma](https://www.figma.com/design/K36XQd4ALpeLzsJDkizw6b/HuskyPoll?node-id=0-1&t=qNfZeEnPTAygMSzT-1)

## Tech Stack
- Frontend: [React](https://react.dev/)
- Backend:  [FastAPI](https://fastapi.tiangolo.com/)
- Database: [SQLite](https://www.sqlite.org/docs.html)

## Docker
To run docker containers, use `docker compose up -d --build` from root
To stop the containers, use `docker compose down`

## Linting
Backend   `ruff check --output-format=github` from /backend
Frontend  `npm run lint` from /frontend

| What | Address |
| --- | --- |
| Frontend (Vite) | http://localhost:5173 |
| Backend API | http://localhost:8000/api |
| API docs (try every endpoint) | http://localhost:8000/api/docs |

- The frontend talks to the backend through the API at `http://localhost:8000/api`
  (available to frontend code as `import.meta.env.VITE_API_BASE`). Send cookies with
  every request: `fetch(url, { credentials: "include" })`.
- Development login: `POST /api/auth/dev-login` with
  `{"email": "pat.prof@uconn.edu", "net_id": "prf00001", "role": "instructor"}`.
- The database and uploaded images are kept in `backend/data/` (not committed).
  Plain `docker compose up -d --build` uses `backend/data/huskypoll.db` and does
  not seed it.
- Demo mode: `./scripts/demo.sh` builds the images, resets and seeds a separate
  `backend/data/huskypoll-demo.db`, and starts the app with a demo course
  (`CSE 2050-001`, 40 students, 6 polls). Demo logins: `prf00001` (instructor),
  `tas00001` (TA), `adm00001` (admin), `ccb23028` (student). The normal database
  is left alone; `docker compose up -d` switches back to it.
- To start the normal database over: `docker compose down`, then
  `docker compose run --rm backend sh -c 'rm -f /data/huskypoll.db*'`, then
  `docker compose up -d --build`. (The container owns `backend/data/`, so delete
  the files through a container rather than with the host user.)
- Backend code changes reload automatically. After pulling new backend code with a new
  database migration, just restart: `docker compose restart backend` (migrations run on start).
- Logs: `docker compose logs -f backend` (or `frontend`).

## Server (huskypoll.cse.uconn.edu)
`compose.yml` is for local development only (developer login on, fixed secret).
On the server, use `compose.server.yml`: one container serves the pages and the API,
login is UConn CAS only, and the database lives in the `huskypoll-data` Docker volume.

```bash
git clone https://github.com/Aidan454/huskypoll.git && cd huskypoll   # then check out the branch to test
cp .env.server.example .env      # fill in HUSKYPOLL_SECRET_KEY (and the site address)
docker compose -f compose.server.yml up -d --build
docker compose -f compose.server.yml exec huskypoll python -m app.database set-role <your-netid> admin
```

Then open http://huskypoll.cse.uconn.edu and log in with your NetID. Make instructors on the
Users page or with `set-role <netid> instructor`. After pulling new code, run the `up -d --build`
line again (migrations run on start). Logs: `docker compose -f compose.server.yml logs -f`.

## Student preview

Instructors can preview a question before publishing from the shared question
editor. Preview inputs are local only and never submit responses or open polls.
See `frontend/README.md` for component organization and verification.

Course Q&A is available to every current course member at the course’s **Q&A** tab.
Questions and replies persist independently of polls, update live, and use plain text
(up to 2,000 characters). Archived courses retain read-only discussions.

Appearance defaults to **Automatic**, using the device’s local time: light from 07:00 to 19:00, dark overnight. Choose Automatic, Light, or Dark in the account menu. Manual choices persist in the browser; automatic mode refreshes while open and after waking. Existing saved Light/Dark choices remain manual until Automatic is selected. Run theme checks with `cd frontend && node --test tests/theme.test.js`.

The login page always uses light mode. Signing in restores the saved Automatic, Light, or Dark preference; signing out does not change that preference.
