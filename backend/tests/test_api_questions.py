"""Question banks, media uploads and serving.

Run with: python -m pytest -q tests/test_api_questions.py
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import tiny_png


def test_banks_and_media(app, lecture):
    prof, ta, cid = lecture["prof"], lecture["ta"], lecture["cid"]
    up = prof.post("/media", files={"file": ("pasted.png", tiny_png(), "image/png")})
    assert up.status_code == 201
    media = up.json()
    assert prof.post("/media", files={"file": ("same.png", tiny_png())}).json()["id"] == media["id"]  # de-duplicated
    assert prof.post("/media", files={"file": ("evil.png", b"<script>", "image/png")}).status_code == 400
    path = media["url"].replace("http://api.test", "")
    assert prof.get(path).content == tiny_png()
    assert TestClient(app).get(path).status_code == 401

    bank = prof.post("/banks", json={"name": "Week 1", "course_id": cid}).json()
    q = prof.post("/questions", json={"type": "mc_single", "body_md": "", "body_media_id": media["id"],
                                      "bank_id": bank["id"],
                                      "options": [{"text_md": "x", "is_correct": True}, {"text_md": "y"}]}).json()
    assert q["body_media_url"] == media["url"]
    assert [b["question_count"] for b in ta.get("/banks").json()] == [1]  # TA sees the course's bank
    detail = prof.get(f"/banks/{bank['id']}").json()
    assert detail["questions"][0]["id"] == q["id"]
    copy = prof.post(f"/banks/{bank['id']}/copy", json={"name": "Week 1 (Fall)"}).json()
    assert copy["question_count"] == 1
    assert prof.delete(f"/questions/{q['id']}").status_code == 204
