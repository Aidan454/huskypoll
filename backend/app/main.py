"""Entry point.

    uvicorn huskypoll_api.main:app --reload            # development
    open http://localhost:8000/docs                     # interactive API docs

Run ONE process (no --workers N): SQLite has one writer and live updates are
delivered in-process. One process comfortably handles a 500-student lecture.
"""
from .app import create_app

app = create_app()
