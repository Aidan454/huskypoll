"""Alembic environment for HuskyPoll.

Uses the same engine setup as the app (PRAGMAs included) and render_as_batch,
which SQLite needs for ALTER TABLE changes (Alembic rebuilds the table).
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from huskypoll_db.models import Base  # noqa: E402
from sqlalchemy import create_engine, event, text  # noqa: E402

config = context.config
if config.config_file_name is not None:
    # disable_existing_loggers=False: when the app creates a database it runs Alembic
    # in-process; without this, Alembic would silence the web server's own logs.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# Read at run time (not import time) so callers can point Alembic at any file.
DB_PATH = os.environ.get("HUSKYPOLL_DB", "huskypoll.db")


def _include_object(obj, name, type_, reflected, compare_to):
    # Views (v_*) are managed by hand in migrations, not by autogenerate.
    return not (type_ == "table" and name.startswith("v_"))


def run_migrations_offline() -> None:
    context.configure(
        url=f"sqlite:///{DB_PATH}",
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def _migration_engine():
    """Engine for migrations: foreign keys OFF.

    SQLite can't add or change constraints in place, so Alembic "batch"
    migrations rebuild a table (create new, copy rows, drop old, rename).
    With foreign keys ON, dropping the old table would cascade-delete every
    row that references it (e.g. dropping users would wipe enrollments and
    responses). So migrations run with them OFF, and we verify afterwards.
    """
    engine = create_engine(f"sqlite:///{DB_PATH}")

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection, _record):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=OFF")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    return engine


def run_migrations_online() -> None:
    engine = _migration_engine()
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            include_object=_include_object,
        )
        with context.begin_transaction():
            context.run_migrations()
            problems = connection.execute(text("PRAGMA foreign_key_check")).fetchall()
            if problems:
                raise RuntimeError(f"migration left broken foreign keys, rolled back: {problems[:5]}")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
