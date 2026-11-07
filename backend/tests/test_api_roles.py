"""Account roles in the API, admin user management and settings-based roles.

Run with: python -m pytest -q tests/test_api_roles.py
"""

from __future__ import annotations

from app.app import create_app
from tests.helpers import login, make_settings, tiny_png


def test_role_rules_in_the_api(app, lecture):
    ta, ann = lecture["ta"], lecture["ann"]
    guest = login(app, "gus12345@uconn.edu")
    assert guest.get("/me").json()["role"] == "guest"
    assert ann.get("/me").json()["role"] == "student"      # roster import made her a student
    assert ta.get("/me").json()["role"] == "ta"            # being added as TA made them a TA

    course = {"term": "T", "subject": "X", "catalog": "1", "title": "t"}
    r = guest.post("/courses", json=course)
    assert r.status_code == 403 and "only instructors and admins" in r.json()["detail"]
    assert ann.post("/courses", json=course).status_code == 403
    assert ta.post("/courses", json=course).status_code == 403

    # Students and guests can't write questions or upload images; TAs can
    q = {"type": "free_text", "body_md": "?"}
    assert ann.post("/questions", json=q).status_code == 403
    assert guest.post("/media", files={"file": ("a.png", tiny_png())}).status_code == 403
    assert ta.post("/questions", json=q).status_code == 201
    assert ann.post("/banks", json={"name": "mine"}).status_code == 403


def test_admin_manages_roles(app):
    admin = login(app, "adm00001@uconn.edu", role="admin")
    pat = login(app, "pat.prof@uconn.edu", "prf00001")
    assert pat.post("/courses", json={"term": "T", "subject": "X", "catalog": "1", "title": "t"}).status_code == 403
    pat_id = pat.get("/me").json()["id"]

    assert pat.get("/users").status_code == 403
    assert pat.patch(f"/users/{pat_id}/role", json={"role": "admin"}).status_code == 403
    found = admin.get("/users", params={"q": "prf"}).json()
    assert [u["net_id"] for u in found] == ["prf00001"]
    assert admin.patch(f"/users/{pat_id}/role", json={"role": "instructor"}).json()["role"] == "instructor"
    assert pat.post("/courses", json={"term": "T", "subject": "X", "catalog": "1", "title": "t"}).status_code == 201
    assert [u["net_id"] for u in admin.get("/users", params={"role": "instructor"}).json()] == ["prf00001"]
    assert admin.patch(f"/users/{pat_id}/role", json={"role": "boss"}).status_code == 422

    admin_id = admin.get("/me").json()["id"]
    r = admin.patch(f"/users/{admin_id}/role", json={"role": "guest"})
    assert r.status_code == 400 and "at least one admin" in r.json()["detail"]


def test_admin_and_instructor_netids_from_settings(tmp_path):
    app = create_app(make_settings(tmp_path, admin_net_ids=["adm00001"], instructor_net_ids=["prf00001"]))
    assert login(app, "adm00001@uconn.edu").get("/me").json()["role"] == "admin"
    assert login(app, "pat.prof@uconn.edu", "prf00001").get("/me").json()["role"] == "instructor"
    assert login(app, "ann.able@uconn.edu", "aab11111").get("/me").json()["role"] == "guest"
