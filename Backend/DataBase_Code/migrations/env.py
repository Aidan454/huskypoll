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
from huskypoll_db.database import make_engine  # noqa: E402
from huskypoll_db.models import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

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


def run_migrations_online() -> None:
    engine = make_engine(DB_PATH)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            include_object=_include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
