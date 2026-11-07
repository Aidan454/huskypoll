"""WebSocket live updates and WebSocket authentication.

Run with: python -m pytest -q tests/test_api_live.py
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.helpers import login


def test_websocket_live_updates(lecture):
    prof, ann, cid, q = lecture["prof"], lecture["ann"], lecture["cid"], lecture["q"]
    with prof.websocket_connect(f"/ws/courses/{cid}") as prof_ws, ann.websocket_connect(f"/ws/courses/{cid}") as ann_ws:
        assert prof_ws.receive_json()["role"] == "owner"
        assert ann_ws.receive_json()["role"] == "student"

        poll = prof.post(f"/courses/{cid}/polls", json={"question_id": q["id"]}).json()
        for ws in (prof_ws, ann_ws):
            msg = ws.receive_json()
            assert msg["type"] == "poll_opened" and msg["poll"]["id"] == poll["id"]
            assert msg["poll"]["question"]["answer_revealed"] is False  # broadcast is student-safe

        ann.post(f"/polls/{poll['id']}/responses", json={"option_ids": [q["options"][1]["id"]]})
        msg = prof_ws.receive_json()
        assert msg["type"] == "results" and msg["results"]["responses"] == 1

        prof.post(f"/polls/{poll['id']}/close")
        assert prof_ws.receive_json() == {"type": "poll_closed", "poll_id": poll["id"], "reason": "manual"}
        # The student got no results message (results hidden), so the next one is the close:
        assert ann_ws.receive_json() == {"type": "poll_closed", "poll_id": poll["id"], "reason": "manual"}


def test_websocket_requires_login_and_membership(app, lecture):
    from starlette.websockets import WebSocketDisconnect
    with (pytest.raises(WebSocketDisconnect) as exc, 
          TestClient(app).websocket_connect(f"/ws/courses/{lecture['cid']}") as ws):
            ws.receive_json()
    assert exc.value.code == 4401
    outsider = login(app, "out99999@uconn.edu")
    with (pytest.raises(WebSocketDisconnect) as exc, 
          outsider.websocket_connect(f"/ws/courses/{lecture['cid']}") as ws):
            ws.receive_json()
    assert exc.value.code == 4403
