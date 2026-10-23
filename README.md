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
  To start over: `docker compose down`, delete `backend/data`, `docker compose up -d`.
- Backend code changes reload automatically. After pulling new backend code with a new
  database migration, just restart: `docker compose restart backend` (migrations run on start).
- Logs: `docker compose logs -f backend` (or `frontend`).