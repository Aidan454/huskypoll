# AGENTS.md

Guide for coding agents (and new teammates) working on HuskyPoll, a live
classroom polling site for UConn. Read this before changing code. The feature
list, with what is done and what is planned, is in [FEATURES.md](FEATURES.md).

## Stack

- **Backend:** Python 3.11+ (3.13 in Docker), FastAPI, SQLAlchemy 2, Alembic, SQLite. In `backend/`.
- **Frontend:** React 19, React Router, Vite, plain CSS. No TypeScript. In `frontend/`.
- **Deploy:** one Docker container serving the built pages and the API, at
  http://huskypoll.cse.uconn.edu.

## Layout

```
backend/
  app/
    main.py, app.py     entry point (uvicorn app.main:app) and app factory
    config.py           every setting, from HUSKYPOLL_* environment variables
    deps.py             DB session per request, current user, permission checks
    live.py             WebSocket hub for live updates (in-process)
    schemas.py          request/response models (shown at /api/docs)
    serializers.py      rows -> responses; hides answer keys from students
    site.py             path-prefix handling; serves frontend/dist on the server
    routers/            auth, users, courses, questions, polls
    database/
      models.py         the tables: single source of truth for the schema
      triggers.py       triggers and views (rules a CHECK can't express)
      services.py       business logic the routers call
      roster.py, export.py, seed.py
      __main__.py       CLI: python -m app.database <command>
  migrations/versions/  Alembic migrations
  schema.sql            generated from models; do not edit by hand
  tests/                test_database.py, test_api.py
  scripts/              demo_tour.py, simulate_lecture.py
frontend/src/
  App.jsx               all routes
  api.js, config.js, live.js   API client, base paths, WebSocket helper
  hooks.js, format.js   useApi/useAction/useAuth, role helpers, formatting
  components/           shared UI (ui.jsx, PollParts.jsx, QuestionEditor.jsx, ...)
  pages/                top-level pages; pages/course/ has the course tabs
compose.yml             local development (two containers, hot reload)
compose.demo.yml        overlay used by scripts/demo.sh
compose.server.yml      the server (one container, CAS login only)
Dockerfile.server       builds frontend + backend into one image
```

## Run it locally

From the repository root, with Docker running:

```bash
docker compose up -d --build        # frontend http://localhost:5173, API http://localhost:8000/api
docker compose logs -f backend      # logs
./scripts/demo.sh                   # same, with a seeded demo course in a separate DB
```

Local compose turns on the **developer login** (`HUSKYPOLL_DEV_LOGIN=1`), so the
login page lets you pick any NetID and role. Demo logins: `prf00001`
(instructor), `tas00001` (TA), `adm00001` (admin), `ccb23028` (student).
Backend and frontend code reload on save. The local database is
`backend/data/huskypoll.db` (not committed).

Without Docker: see `backend/README.md` ("Run it (with the frontend)").

## Test and lint

Run these before every push; CI runs the same checks on pushes and PRs to `main`
and `develop`.

```bash
cd backend && pip install -r requirements.txt ruff
python -m pytest -q                 # database + API tests
ruff check .

cd frontend && npm ci
npm run lint
npm run build
```

There are no frontend tests yet. Backend tests use a temporary SQLite file and
the dev login, so they need no services.

## The server

```bash
cp .env.server.example .env         # fill in HUSKYPOLL_SECRET_KEY
docker compose -f compose.server.yml up -d --build      # also how you deploy new code
docker compose -f compose.server.yml exec huskypoll python -m app.database set-role <netid> admin
docker compose -f compose.server.yml logs -f
```

- Login on the server is **UConn CAS only**. The dev login is off and must stay
  off (`HUSKYPOLL_DEV_LOGIN: "0"`): with it on, anyone can log in as anyone.
- The database and uploaded images live in the `huskypoll-data` Docker volume.
  Never run `docker compose -f compose.server.yml down -v`; `-v` deletes it.
- Migrations run automatically when the container starts.
- Run exactly **one** server process. Don't add uvicorn `--workers`: SQLite has
  one writer and live updates are delivered inside that one process.

## Making changes

### Database schema

1. Change `backend/app/database/models.py` (and `triggers.py` if needed).
2. Add a migration in `backend/migrations/versions/` (from `backend/`:
   `alembic revision --autogenerate -m "short description"`, then check the file
   by hand; `env.py` already uses batch mode, which SQLite needs for column changes).
3. Regenerate `schema.sql`: `python -m app.database schema > schema.sql`.
4. Add tests in `tests/test_database.py`.

### API

- Put logic in `app/database/services.py`; keep routers thin. Raise
  `HuskyPollError` for user-facing errors.
- Check permissions with the helpers in `app/deps.py`. What someone may do in a
  course depends on their role **in that course**, not only their account role.
- Never send answer keys, explanations or correctness to students before a poll
  closes; go through `serializers.py`.
- Store times in UTC and return timezone-aware datetimes.
- Add API tests in `tests/test_api.py`.

### Frontend

- Call the API only through `src/api.js` (it sends cookies and throws
  `ApiError`). Use `src/live.js` for WebSockets.
- Never hard-code `/` or a domain. The site can run under a path prefix (e.g.
  `/cse1010`); use `BASE_PATH`/`pagePath()` from `src/config.js` and the URLs the
  API returns (`join_url`, image `url`).
- Add new pages as routes in `src/App.jsx`. Use the shared pieces in
  `components/ui.jsx` and the hooks in `hooks.js`.
- Style with the CSS variables in `index.css` so the light/dark theme works.

### Conventions

- Match the style of the file you're in. Python: ruff config in
  `backend/ruff.toml`. JS: ESLint config in `frontend/eslint.config.js`.
- Keep docs in step with the code: the root `README.md`, `backend/README.md`,
  and `FEATURES.md` when a feature lands or changes status.
- Branch from `main` and open a pull request; CI must pass.

## Gotchas

- **Folder names are lowercase:** `backend/`, `frontend/`, `app/database/`.
  The repo used to have `Backend/` and `Database/`. Windows and macOS ignore case,
  so an old checkout can keep a capital `Backend` folder or git can show
  confusing renames. Always use the lowercase paths; if you see `Backend/`, fix
  it with `git mv` in two steps (`Backend` -> `tmp` -> `backend`).
  `backend/DOCKER.md` is an older doc and may still mention old paths.
- **Secrets:** the server's settings are in `.env` at the repo root, which is
  git-ignored. Never commit it or put a real `HUSKYPOLL_SECRET_KEY` in any
  compose file. `compose.yml` uses a fixed dev-only key on purpose.
- **Dev login is local only.** If a feature only works through
  `/api/auth/dev-login`, it doesn't work on the server.
- **Local data files belong to the container.** To reset the local database,
  delete it through a container:
  `docker compose run --rm backend sh -c 'rm -f /data/huskypoll.db*'`.
- **After pulling a new migration locally:** `docker compose restart backend`.
- **Unused files.** `pages/Polls.jsx`, `pages/InstructorHome.jsx`,
  `pages/StudentHome.jsx`, `components/Header/`, `components/LoginCard/`,
  `components/PollCard/`, `components/ToggleButton/`, `components/Courses/` and
  `components/BackendStatus.jsx` are early prototypes not used by any route.
  Some import CSS files that aren't in the repo, so importing them breaks the
  build. Don't build on them; the live pages are the ones in `App.jsx`.
- **Microsoft sign-in doesn't exist yet.** Only CAS is coded; see FEATURES.md.
