"""Engine and session setup for the HuskyPoll SQLite database.

Every connection gets the PRAGMAs the design brief calls for:
  * foreign_keys=ON   - SQLite ignores FK constraints unless this is set per connection
  * journal_mode=WAL  - readers never block the writer (live results while students answer)
  * busy_timeout=5000 - wait up to 5 s for the write lock instead of failing immediately
  * synchronous=NORMAL - safe with WAL and much faster than FULL
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DB_PATH = Path(os.environ.get("DB", "huskypoll.db"))


def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def make_engine(db_path: str | Path | None = None, echo: bool = False) -> Engine:
    """Create an engine for a database file (or ':memory:' for tests)."""
    path = str(db_path or DEFAULT_DB_PATH)
    url = "sqlite://" if path == ":memory:" else f"sqlite:///{path}"
    engine = create_engine(url, echo=echo)
    event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Create all tables, indexes, triggers and views on an empty database.

    For a database that already exists, use Alembic migrations instead
    (`alembic upgrade head`) so changes are applied without losing data.
    """
    from .models import Base  # local import avoids a cycle

    Base.metadata.create_all(engine)
