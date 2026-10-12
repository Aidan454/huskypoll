"""Builds the FastAPI application (create_app). The runnable app is in main.py."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from starlette.middleware.sessions import SessionMiddleware

from huskypoll_db import init_db, make_engine, make_session_factory
from huskypoll_db.services import HuskyPollError, NotAllowed

from .config import Settings
from .site import HuskyPollSite
from .routers import auth, courses, polls, questions, users
from .routers.auth import validate_cas_ticket

log = logging.getLogger("huskypoll")


def _prepare_database(engine, settings: Settings) -> None:
    """Create the database on first run; warn if it needs `alembic upgrade head`."""
    if not inspect(engine).has_table("users"):
        init_db(engine)
        try:
            from huskypoll_db.__main__ import _stamp_alembic_head
            _stamp_alembic_head(str(settings.db_path))
        except Exception as exc:  # alembic.ini missing (e.g. installed as a package)
            log.warning("created database but could not stamp Alembic version: %s", exc)
        log.info("created new database %s", settings.db_path)
        return
    try:
        from pathlib import Path

        from alembic.config import Config
        from alembic.script import ScriptDirectory
        ini = Path(__file__).resolve().parent.parent / "alembic.ini"
        head = ScriptDirectory.from_config(Config(str(ini))).get_current_head()
        with engine.connect() as c:
            current = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if current != head:
            log.warning("database is at migration %s but the code expects %s - run `alembic upgrade head`",
                        current, head)
    except Exception as exc:
        log.warning("could not check database migration version: %s", exc)


def create_app(settings: Settings | None = None) -> HuskyPollSite:
    """The API at SITE_URL/api, plus the built frontend at SITE_URL/ when HUSKYPOLL_FRONTEND_DIST is set."""
    settings = settings or Settings()

    app = FastAPI(
        title="HuskyPoll API",
        version="0.1.0",
        description="In-class polling for UConn. Log in via /auth/login (UConn) or /auth/dev-login (development).",
        # Serve under a path prefix (e.g. /cse1010). Requests work whether or not the
        # reverse proxy strips the prefix, and /docs points at the right openapi.json.
        root_path=settings.base_path,
    )
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = make_engine(settings.db_path)
    _prepare_database(engine, settings)
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.cas_validator = validate_cas_ticket  # tests replace this

    # Signed cookie holding only the user id. SameSite=Lax blocks cross-site form posts (CSRF).
    # Scoped to the base path, so copies at /cse1010 and /test-version1 keep separate logins.
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, session_cookie="huskypoll_session",
                       max_age=14 * 24 * 3600, path=settings.base_path or "/", same_site="lax",
                       https_only=settings.secure_cookies)
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                           allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(NotAllowed)
    async def _not_allowed(_: Request, exc: NotAllowed):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    @app.exception_handler(HuskyPollError)
    async def _rule_broken(_: Request, exc: HuskyPollError):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError):
        # A database rule caught something the API didn't (see triggers.py / CHECK constraints).
        msg = str(exc.orig) if exc.orig is not None else "conflict"
        if "UNIQUE constraint failed" in msg:
            msg = "That already exists"
        return JSONResponse({"detail": msg}, status_code=409)

    @app.get("/health", tags=["system"], summary="Is the server and database OK")
    def health():
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return {"ok": True}

    for r in (auth.router, users.router, courses.router, questions.router, polls.router):
        app.include_router(r)
    return HuskyPollSite(app, settings)
