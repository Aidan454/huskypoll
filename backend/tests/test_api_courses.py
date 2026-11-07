"""Course settings, permissions, archive and delete over the API.

Run with: python -m pytest -q tests/test_api_courses.py
"""

from __future__ import annotations

from tests.helpers import login


def test_participation_points_are_fixed_at_one(app):
    prof = login(app, "pat.prof@uconn.edu", "prf00001", "Pat", "Prof", role="instructor")
    body = {"term": "Spring 2027", "subject": "cse", "catalog": "2050", "title": "Data Structures"}
    course = prof.post("/courses", json={**body, "points_participation": 9}).json()
    assert course["points_participation"] == 1

    updated = prof.patch(f"/courses/{course['id']}",
                         json={"points_participation": 9, "points_correct": 2}).json()
    assert updated["points_participation"] == 1
    assert updated["points_correct"] == 2


def test_permissions(app, lecture):
    prof, ta, ann, cid, q = lecture["prof"], lecture["ta"], lecture["ann"], lecture["cid"], lecture["q"]
    outsider = login(app, "out99999@uconn.edu")
    assert outsider.get(f"/courses/{cid}").status_code == 404          # course hidden
    assert ann.post(f"/courses/{cid}/polls", json={"question_id": q["id"]}).status_code == 403
    assert ann.get(f"/courses/{cid}/roster").status_code == 403
    assert ann.get(f"/questions/{q['id']}").status_code == 404        # answer key not reachable
    assert ann.get(f"/courses/{cid}/export/participation.csv").status_code == 403
    assert ann.get(f"/courses/{cid}/participation/sessions").status_code == 403
    poll = prof.post(f"/courses/{cid}/polls", json={"question_id": q["id"]}).json()
    r = outsider.post(f"/polls/{poll['id']}/responses", json={"option_ids": [q["options"][0]["id"]]})
    assert r.status_code == 404  # not without the code (see test_anyone_with_the_code_can_answer)
    # TA can run polls but can't add instructors or delete the course
    assert ta.post(f"/polls/{poll['id']}/close").status_code == 200
    assert ta.post(f"/courses/{cid}/instructors", json={"identifier": "abc12345"}).status_code == 403
    assert ta.delete(f"/courses/{cid}").status_code == 403


def test_end_of_semester(lecture):
    prof, cid = lecture["prof"], lecture["cid"]
    assert prof.post(f"/courses/{cid}/archive").json()["archived_at"]
    assert prof.get("/courses").json() == []
    assert len(prof.get("/courses", params={"include_archived": True}).json()) == 1
    r = prof.post(f"/courses/{cid}/polls", json={"question_id": lecture["q"]["id"]})
    assert r.status_code == 400 and "archived" in r.json()["detail"]
    prof.post(f"/courses/{cid}/unarchive")
    summary = prof.delete(f"/courses/{cid}").json()
    assert summary["students"] == 2
    assert prof.get(f"/courses/{cid}").status_code == 404
