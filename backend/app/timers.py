"""Closes polls whose time limit has run out.

The countdown itself runs in the browser; this loop is what makes the deadline
authoritative. It runs once per second in the same process as the WebSocket hub,
so a timeout is broadcast to everyone as soon as it happens.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from .database.models import Poll, utcnow
from .database.services import log_event
from .live import hub


def close_expired_polls(session_factory) -> list[tuple[int, int]]:
    """Close every open poll past its deadline. Returns (course_id, poll_id) pairs."""
    with session_factory() as db:
        now = utcnow()
        expired = db.scalars(
            select(Poll).where(
                Poll.status == "open",
                Poll.closes_at.is_not(None),
                Poll.closes_at <= now,
            )
        ).all()
        closed = []
        for poll in expired:
            poll.status = "closed"
            poll.closed_at = now
            log_event(db, "poll_timeout", course=poll.session.course, poll=poll)
            closed.append((poll.session.course_id, poll.id))
        db.commit()
        return closed


async def poll_timer_loop(session_factory, interval: float = 1.0) -> None:
    while True:
        for course_id, poll_id in await asyncio.to_thread(close_expired_polls, session_factory):
            hub.publish(course_id, {"type": "poll_closed", "poll_id": poll_id, "reason": "timeout"})
        await asyncio.sleep(interval)
