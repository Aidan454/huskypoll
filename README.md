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
