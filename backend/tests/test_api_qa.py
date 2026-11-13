"""Lecture Q&A: per-lecture questions and replies, permissions and live updates.

Run with: python -m pytest -q tests/test_api_qa.py
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import login


def test_lecture_qa_without_poll(lecture):
    prof, ann, bob, cid = (lecture[k] for k in ("prof", "ann", "bob", "cid"))
    sid = prof.post(f"/courses/{cid}/sessions", json={"title": "Lecture Q&A"}).json()["id"]
    path = f"/sessions/{sid}/qa"
    assert ann.get(path).json() == []
    result = ann.post(path, json={"body": "  Can someone explain recursion?  "})
    assert result.status_code == 201, result.text
    question = result.json()
    assert question["body"] == "Can someone explain recursion?"
    assert question["author_name"] == "Ann Able"
    assert question["reply_count"] == 0
    assert question["created_at"].endswith("Z")
    replies = f"{path}/{question['id']}/replies"
    assert bob.post(replies, json={"body": "A function calling itself."}).status_code == 201
    assert prof.post(replies, json={"body": "Remember the base case!"}).status_code == 201
    assert [r["body"] for r in ann.get(replies).json()] == ["A function calling itself.", "Remember the base case!"]
    assert prof.get(path).json()[0]["reply_count"] == 2
    assert "email" not in str(ann.get(path).json())


def test_lecture_qa_permissions_and_validation(lecture, app):
    prof, ann, cid = (lecture[k] for k in ("prof", "ann", "cid"))
    outsider = login(app, "out.side@uconn.edu", "out12345")
    sid = prof.post(f"/courses/{cid}/sessions", json={"title": "Lecture Q&A"}).json()["id"]
    path = f"/sessions/{sid}/qa"
    qid = ann.post(path, json={"body": "Question"}).json()["id"]
    replies = f"{path}/{qid}/replies"
    assert TestClient(app).get(path).status_code == 401
    for url in (path, replies):
        assert outsider.get(url).status_code == 404
        assert outsider.post(url, json={"body": "No access"}).status_code == 404
        assert ann.post(url, json={"body": " \n \t"}).status_code == 400
        assert ann.post(url, json={"body": "a" * 2001}).status_code == 422
    other = prof.post("/courses", json={"term": "Spring 2027", "subject": "CSE", "catalog": "9999",
                                        "title": "Other"}).json()["id"]
    other_sid = prof.post(f"/courses/{other}/sessions", json={"title": "Other lecture"}).json()["id"]
    assert prof.get(f"/sessions/{other_sid}/qa/{qid}/replies").status_code == 404
    assert prof.post(f"/sessions/{other_sid}/qa/{qid}/replies", json={"body": "Wrong course"}).status_code == 404
    assert prof.post(f"/courses/{cid}/archive").status_code == 200
    for url in (path, replies):
        assert ann.get(url).status_code == 200
        assert ann.post(url, json={"body": "Archived"}).status_code == 400


def test_lecture_qa_pagination_and_live_updates(lecture):
    prof, ann, cid = (lecture[k] for k in ("prof", "ann", "cid"))
    sid = prof.post(f"/courses/{cid}/sessions", json={"title": "Lecture Q&A"}).json()["id"]
    path = f"/sessions/{sid}/qa"
    with prof.websocket_connect(f"/ws/courses/{cid}") as ws:
        assert ws.receive_json()["type"] == "hello"
        qid = ann.post(path, json={"body": "Live question"}).json()["id"]
        assert ws.receive_json() == {"type": "qa_changed", "session_id": sid}
        prof.post(f"{path}/{qid}/replies", json={"body": "Live reply"})
        assert ws.receive_json() == {"type": "qa_changed", "session_id": sid}
    for i in range(30):
        assert ann.post(path, json={"body": f"Question {i}"}).status_code == 201
    page = prof.get(path).json()
    assert len(page) == 30
    older = prof.get(path, params={"before_id": page[-1]["id"]}).json()
    assert [q["id"] for q in older] == [qid]
    assert not {q["id"] for q in page} & {q["id"] for q in older}


def test_lecture_qa_isolation_and_lecture_access(lecture):
    prof, ann, cid = (lecture[k] for k in ("prof", "ann", "cid"))
    first = prof.post(f"/courses/{cid}/sessions", json={"title": "First lecture"}).json()["id"]
    second = prof.post(f"/courses/{cid}/sessions", json={"title": "Second lecture"}).json()["id"]
    qid = ann.post(f"/sessions/{first}/qa", json={"body": "First only"}).json()["id"]
    assert prof.post(f"/sessions/{second}/qa", json={"body": "Instructor question"}).status_code == 201
    assert [q["body"] for q in ann.get(f"/sessions/{second}/qa").json()] == ["Instructor question"]
    assert ann.get(f"/sessions/{second}/qa/{qid}/replies").status_code == 404
    assert ann.post(f"/sessions/{second}/qa/{qid}/replies", json={"body": "Wrong lecture"}).status_code == 404
    assert ann.get(f"/sessions/{first}").json()["qa_count"] == 1
    assert ann.get(f"/courses/{cid}/sessions").status_code == 200
    assert ann.delete(f"/sessions/{first}").status_code == 403
    assert prof.delete(f"/sessions/{first}").status_code == 400
    assert len(ann.get(f"/sessions/{first}/qa").json()) == 1
    # The former global API is gone; old clients cannot create unscoped posts.
    assert ann.post(f"/courses/{cid}/qa", json={"body": "Unscoped"}).status_code == 404
