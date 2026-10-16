"""API tests: python -m pytest -q tests/test_api.py"""
from __future__ import annotations

import struct
import warnings
import zlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from huskypoll_api.app import create_app
from huskypoll_api.config import Settings
from huskypoll_api.routers.auth import parse_cas_response

ROOT = Path(__file__).resolve().parent.parent


def tiny_png() -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))


def make_settings(tmp_path, **kw) -> Settings:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return Settings(db_path=tmp_path / "api.db", media_dir=tmp_path / "media", secret_key="test-secret",
                        dev_login=kw.pop("dev_login", True), public_url="http://api.test",
                        frontend_url="http://front.test", **kw)


@pytest.fixture()
def app(tmp_path):
    return create_app(make_settings(tmp_path))


def login(app, email, net_id=None, first=None, last=None, role=None) -> TestClient:
    c = TestClient(app)
    r = c.post("/auth/dev-login", json={"email": email, "net_id": net_id, "first_name": first, "last_name": last,
                                        "role": role})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture()
def lecture(app):
    """A course with an owner, a TA, two students and one multiple-choice question."""
    prof = login(app, "pat.prof@uconn.edu", "prf00001", "Pat", "Prof", role="instructor")
    course = prof.post("/courses", json={"term": "Spring 2027", "subject": "cse", "catalog": "2050",
                                         "title": "Data Structures", "points_participation": 1,
                                         "points_correct": 1}).json()
    cid = course["id"]
    assert prof.post(f"/courses/{cid}/instructors", json={"identifier": "tas00001", "role": "ta"}).status_code == 201
    r = prof.post(f"/courses/{cid}/roster/paste", json={"text": "ann.able@uconn.edu\nbob.baker@uconn.edu"})
    assert r.json()["enrolled"] == 2
    ann = login(app, "ann.able@uconn.edu", "aab11111", "Ann", "Able")
    bob = login(app, "bob.baker@uconn.edu", "bba22222", "Bob", "Baker")
    ta = login(app, "tas00001@uconn.edu")
    q = prof.post("/questions", json={"type": "mc_single", "body_md": "2+2?",
                                      "options": [{"text_md": "3"}, {"text_md": "4", "is_correct": True}],
                                      "explanation_md": "Arithmetic."}).json()
    return {"prof": prof, "ta": ta, "ann": ann, "bob": bob, "cid": cid, "q": q}


# --- auth ------------------------------------------------------------------------

def test_health_and_login_required(app):
    c = TestClient(app)
    assert c.get("/health").json() == {"ok": True}
    assert c.get("/me").status_code == 401
    assert c.get("/courses").status_code == 401


def test_dev_login_rules(app):
    c = TestClient(app)
    assert c.post("/auth/dev-login", json={"email": "someone@gmail.com", "net_id": "abc12345"}).status_code == 403
    r = c.post("/auth/dev-login", json={"email": "abc12345@uconn.edu"})
    assert r.json()["net_id"] == "abc12345" and r.json()["role"] == "guest"
    assert c.get("/me").json()["email"] == "abc12345@uconn.edu"
    c.post("/auth/logout")
    assert c.get("/me").status_code == 401


def test_dev_login_disabled_by_default(tmp_path):
    app = create_app(make_settings(tmp_path, dev_login=False))
    assert TestClient(app).post("/auth/dev-login", json={"email": "abc12345@uconn.edu"}).status_code == 404


def test_cas_login_flow(app):
    c = TestClient(app, follow_redirects=False)
    r = c.get("/auth/login", params={"next": "/courses/1"})
    assert r.status_code == 307 and r.headers["location"].startswith("https://login.uconn.edu/cas/login?service=")
    app.state.cas_validator = lambda settings, ticket: {"net_id": "jos10001", "email": "jonathan.smith@uconn.edu",
                                                        "first_name": "Jonathan", "last_name": "Smith"}
    r = c.get("/auth/cas/callback", params={"ticket": "ST-1"})
    assert r.status_code == 303 and r.headers["location"] == "http://front.test/courses/1"
    assert c.get("/me").json()["net_id"] == "jos10001"


def test_cas_open_redirect_blocked(app):
    c = TestClient(app, follow_redirects=False)
    c.get("/auth/login", params={"next": "//evil.com"})
    app.state.cas_validator = lambda s, t: {"net_id": "jos10001", "email": None}
    assert c.get("/auth/cas/callback", params={"ticket": "x"}).headers["location"] == "http://front.test/"


def test_parse_cas_response():
    ok = """<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas"><cas:authenticationSuccess>
      <cas:user>abc12345</cas:user><cas:attributes><cas:mail>ann.able@uconn.edu</cas:mail>
      <cas:givenName>Ann</cas:givenName><cas:sn>Able</cas:sn></cas:attributes>
      </cas:authenticationSuccess></cas:serviceResponse>"""
    assert parse_cas_response(ok) == {"net_id": "abc12345", "email": "ann.able@uconn.edu",
                                      "first_name": "Ann", "last_name": "Able"}
    no_attrs = """<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas"><cas:authenticationSuccess>
      <cas:user>abc12345</cas:user></cas:authenticationSuccess></cas:serviceResponse>"""
    assert parse_cas_response(no_attrs)["email"] == "abc12345@uconn.edu"
    bad = """<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
      <cas:authenticationFailure code="INVALID_TICKET">Ticket not recognized</cas:authenticationFailure>
      </cas:serviceResponse>"""
    with pytest.raises(Exception, match="Ticket not recognized"):
        parse_cas_response(bad)


# --- the lecture flow ------------------------------------------------------------

def test_full_lecture_flow(lecture):
    prof, ann, bob, cid, q = lecture["prof"], lecture["ann"], lecture["bob"], lecture["cid"], lecture["q"]

    # Students see the course, without the join code
    mine = ann.get("/courses").json()
    assert [c["my_role"] for c in mine] == ["student"] and mine[0]["join_code"] is None
    assert prof.get(f"/courses/{cid}").json()["join_code"]

    # Open a poll; today's session is created automatically
    poll = prof.post(f"/courses/{cid}/polls", json={"question_id": q["id"]}).json()
    assert poll["status"] == "open" and poll["join_url"] == f"http://front.test/join/{poll['access_code']}"
    assert prof.get(f"/courses/{cid}/sessions").json()[0]["is_auto"] is True

    # QR codes
    svg = prof.get(f"/polls/{poll['id']}/qr.svg")
    assert svg.status_code == 200 and svg.headers["content-type"] == "image/svg+xml" and b"<svg" in svg.content
    assert prof.get(f"/polls/{poll['id']}/qr.png").content.startswith(b"\x89PNG")
    assert ann.get(f"/polls/{poll['id']}/qr.svg").status_code == 403

    # Student finds it by code; answer key hidden
    seen = ann.get(f"/polls/by-code/{poll['access_code'].lower()}").json()
    assert seen["question"]["answer_revealed"] is False
    assert all(o["is_correct"] is None for o in seen["question"]["options"])
    assert seen["question"]["explanation_md"] is None
    wrong, right = [o["id"] for o in seen["question"]["options"]]

    # Answer, get a confirmation (no correctness yet), change answer
    conf = ann.post(f"/polls/{poll['id']}/responses", json={"option_ids": [wrong]}).json()
    assert conf["received"] is True and conf["option_ids"] == [wrong] and conf["is_correct"] is None
    conf = ann.post(f"/polls/{poll['id']}/responses", json={"option_ids": [right]}).json()
    assert conf["option_ids"] == [right]
    bob.post(f"/polls/{poll['id']}/responses", json={"option_ids": [wrong]})
    assert ann.get(f"/polls/{poll['id']}").json()["my_response"]["option_ids"] == [right]

    # Two picks on a single-answer question -> friendly 400
    r = bob.post(f"/polls/{poll['id']}/responses", json={"option_ids": [wrong, right]})
    assert r.status_code == 400 and "exactly one" in r.json()["detail"]

    # Results: instructors yes, students only when shown
    res = prof.get(f"/polls/{poll['id']}/results").json()
    assert res["responses"] == 2 and {o["option_id"]: o["votes"] for o in res["options"]} == {wrong: 1, right: 1}
    assert ann.get(f"/polls/{poll['id']}/results").status_code == 403
    prof.patch(f"/polls/{poll['id']}", json={"show_results": True})
    assert ann.get(f"/polls/{poll['id']}/results").status_code == 200
    assert len(prof.get(f"/polls/{poll['id']}/responses").json()) == 2

    # Close; late answers refused; history reveals answer and mark
    prof.post(f"/polls/{poll['id']}/close")
    r = bob.post(f"/polls/{poll['id']}/responses", json={"option_ids": [right]})
    assert r.status_code == 400 and "closed" in r.json()["detail"]
    hist = ann.get(f"/courses/{cid}/history").json()
    assert hist[0]["answered"] and hist[0]["poll"]["my_response"]["is_correct"] is True
    assert hist[0]["poll"]["question"]["explanation_md"] == "Arithmetic."
    assert ann.get(f"/courses/{cid}/my-participation").json() == {
        "polls": 1, "answered": 1, "correct": 1, "points": 2.0, "points_possible": 2.0}

    # Export and log
    csv = prof.get(f"/courses/{cid}/export/huskyct.csv")
    assert csv.headers["content-type"].startswith("text/csv")
    assert "Able,Ann,aab11111,,2" in csv.text and "Baker,Bob,bba22222,,1" in csv.text
    assert "Total" in prof.get(f"/courses/{cid}/export/sessions.csv").text
    events = {e["event_type"] for e in prof.get(f"/courses/{cid}/events").json()}
    assert {"poll_open", "response_submit", "response_update", "poll_close", "export_huskyct"} <= events


def test_quick_poll_then_add_answer_and_regrade(lecture):
    prof, ann, bob, cid = lecture["prof"], lecture["ann"], lecture["bob"], lecture["cid"]
    poll = prof.post(f"/courses/{cid}/polls/quick", json={
        "type": "mc_single", "body_md": "Typed in lecture", "options": [{"text_md": "A"}, {"text_md": "B"}]}).json()
    a, b = [o["id"] for o in poll["question"]["options"]]
    ann.post(f"/polls/{poll['id']}/responses", json={"option_ids": [b]})
    bob.post(f"/polls/{poll['id']}/responses", json={"option_ids": [a]})
    prof.post(f"/polls/{poll['id']}/close")
    qid = poll["question"]["id"]

    # Wording is locked...
    r = prof.patch(f"/questions/{qid}", json={"body_md": "changed"})
    assert r.status_code == 400 and "locked" in r.json()["detail"]
    # ...but the answer can be added, which re-marks everyone
    r = prof.patch(f"/questions/{qid}", json={"correct_option_ids": [b]}).json()
    assert r["responses_regraded"] == 2
    assert ann.get(f"/courses/{cid}/history").json()[0]["poll"]["my_response"]["is_correct"] is True
    # Editable copy
    copy = prof.post(f"/questions/{qid}/copy").json()
    assert copy["copied_from_id"] == qid and not copy["is_locked"]
    assert prof.patch(f"/questions/{copy['id']}", json={"body_md": "reworded"}).json()["question"]["body_md"] == "reworded"


def test_other_question_types(lecture):
    prof, ann, cid = lecture["prof"], lecture["ann"], lecture["cid"]
    num = prof.post("/questions", json={"type": "numeric", "body_md": "pi?", "numeric_answer": 3.14,
                                        "numeric_tolerance": 0.01}).json()
    text = prof.post("/questions", json={"type": "free_text", "body_md": "LIFO?", "text_answer": "stack"}).json()
    p1 = prof.post(f"/courses/{cid}/polls", json={"question_id": num["id"]}).json()
    p2 = prof.post(f"/courses/{cid}/polls", json={"question_id": text["id"]}).json()
    assert ann.post(f"/polls/{p1['id']}/responses", json={"numeric_answer": 3.145}).status_code == 200
    assert ann.post(f"/polls/{p2['id']}/responses", json={"text_answer": " Stack "}).status_code == 200
    assert ann.post(f"/polls/{p2['id']}/responses", json={}).status_code == 400
    assert prof.get(f"/polls/{p2['id']}/results").json()["answers"] == [{"answer": "stack", "count": 1}]
    open_polls = ann.get(f"/courses/{cid}/polls", params={"status": "open"}).json()
    assert len(open_polls) == 2 and all(p["my_response"] for p in open_polls)


# --- permissions -------------------------------------------------------------------

def test_permissions(app, lecture):
    prof, ta, ann, cid, q = lecture["prof"], lecture["ta"], lecture["ann"], lecture["cid"], lecture["q"]
    outsider = login(app, "out99999@uconn.edu")
    assert outsider.get(f"/courses/{cid}").status_code == 404          # course hidden
    assert ann.post(f"/courses/{cid}/polls", json={"question_id": q["id"]}).status_code == 403
    assert ann.get(f"/courses/{cid}/roster").status_code == 403
    assert ann.get(f"/questions/{q['id']}").status_code == 404        # answer key not reachable
    assert ann.get(f"/courses/{cid}/export/huskyct.csv").status_code == 403
    poll = prof.post(f"/courses/{cid}/polls", json={"question_id": q["id"]}).json()
    r = outsider.post(f"/polls/{poll['id']}/responses", json={"option_ids": [q["options"][0]["id"]]})
    assert r.status_code == 403
    assert outsider.get(f"/polls/by-code/{poll['access_code']}").status_code == 403
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


# --- roster, banks, media ------------------------------------------------------------

def test_roster_endpoints(lecture):
    prof, cid = lecture["prof"], lecture["cid"]
    with open(ROOT / "samples" / "studentadmin-template.xlsx", "rb") as f:
        r = prof.post(f"/courses/{cid}/roster/import", files={"file": ("roster.xlsx", f)})
    assert r.status_code == 200 and r.json()["enrolled"] == 1
    assert prof.post(f"/courses/{cid}/roster/import", files={"file": ("x.xlsx", b"not a spreadsheet")}).status_code == 400
    r = prof.post(f"/courses/{cid}/roster", json={"identifier": "prof01"})
    assert r.status_code == 400 and "not a valid NetID" in r.json()["detail"]
    assert prof.post(f"/courses/{cid}/roster", json={"identifier": "new12345"}).json()["enrolled"] == 1
    roster = prof.get(f"/courses/{cid}/roster").json()
    assert len(roster) == 4
    ann_id = next(e["user"]["id"] for e in roster if e["user"]["net_id"] == "aab11111")
    assert prof.delete(f"/courses/{cid}/roster/{ann_id}").status_code == 204
    assert len(prof.get(f"/courses/{cid}/roster").json()) == 3
    assert lecture["ann"].get(f"/courses/{cid}").status_code == 404


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


# --- live updates -----------------------------------------------------------------

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
        assert prof_ws.receive_json() == {"type": "poll_closed", "poll_id": poll["id"]}
        # The student got no results message (results hidden), so the next one is the close:
        assert ann_ws.receive_json() == {"type": "poll_closed", "poll_id": poll["id"]}


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


# --- running under a path prefix (e.g. huskypoll.cse.uconn.edu/cse1010) -----------

HOST = "https://huskypoll.cse.uconn.edu"
# The test client talks plain http to the same host (its cookie handling skips wss://).
CLIENT_BASE = "http://huskypoll.cse.uconn.edu"


def prefixed_app(tmp_path, prefix):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        name = prefix.strip("/").replace("/", "_")
        settings = Settings(db_path=tmp_path / f"{name}.db", media_dir=tmp_path / f"media_{name}",
                            secret_key="test-secret", dev_login=True, public_url=f"{HOST}{prefix}")
    return create_app(settings)


@pytest.mark.parametrize("prefix", ["/cse1010", "/test-version1", "/courses/fall-2027/cse2050"])
def test_app_works_under_a_path_prefix(tmp_path, prefix):
    app = prefixed_app(tmp_path, prefix)
    c = TestClient(app, base_url=CLIENT_BASE, follow_redirects=False)
    # Works whether the reverse proxy keeps the prefix or strips it
    assert c.get(f"{prefix}/health").status_code == 200
    assert c.get("/health").status_code == 200
    assert f"{prefix}/openapi.json" in c.get(f"{prefix}/docs").text

    r = c.post(f"{prefix}/auth/dev-login", json={"email": "pat.prof@uconn.edu", "net_id": "prf00001", "role": "instructor"})
    assert f"path={prefix}" in r.headers["set-cookie"]
    assert c.get(f"{prefix}/me").status_code == 200

    # Every URL the API hands out includes the prefix
    login_redirect = c.get(f"{prefix}/auth/login").headers["location"]
    assert f"service=https%3A%2F%2Fhuskypoll.cse.uconn.edu{prefix.replace('/', '%2F')}%2Fauth%2Fcas%2Fcallback" in login_redirect
    img = c.post(f"{prefix}/media", files={"file": ("a.png", tiny_png())}).json()
    assert img["url"].startswith(f"{HOST}{prefix}/media/")
    assert c.get(img["url"].replace(HOST, "")).content == tiny_png()
    cid = c.post(f"{prefix}/courses", json={"term": "T", "subject": "CSE", "catalog": "1010", "title": "Intro"}).json()["id"]
    q = c.post(f"{prefix}/questions", json={"type": "mc_single", "body_md": "?", "body_media_id": img["id"],
                                            "options": [{"text_md": "a", "is_correct": True}, {"text_md": "b"}]}).json()
    assert q["body_media_url"] == img["url"]
    # The test client sends WebSocket requests to its default host, so pass the login cookie explicitly
    cookie = {"cookie": f"huskypoll_session={c.cookies.get('huskypoll_session')}"}
    with c.websocket_connect(f"{prefix}/ws/courses/{cid}", headers=cookie) as ws:
        assert ws.receive_json()["type"] == "hello"
        poll = c.post(f"{prefix}/courses/{cid}/polls", json={"question_id": q["id"]}).json()
        assert ws.receive_json()["type"] == "poll_opened"
    assert poll["join_url"] == f"{HOST}{prefix}/join/{poll['access_code']}"
    assert c.get(f"{prefix}/polls/{poll['id']}/qr.svg").status_code == 200

    # CAS sends the user back to the frontend under the same prefix
    c.get(f"{prefix}/auth/login", params={"next": "/courses/1"})
    app.state.cas_validator = lambda s, t: {"net_id": "jos10001", "email": "jonathan.smith@uconn.edu"}
    assert c.get(f"{prefix}/auth/cas/callback", params={"ticket": "x"}).headers["location"] == f"{HOST}{prefix}/courses/1"


def test_two_copies_on_one_domain_keep_separate_logins(tmp_path):
    a = TestClient(prefixed_app(tmp_path, "/cse1010"), base_url=CLIENT_BASE)
    b_app = prefixed_app(tmp_path, "/test-version1")
    a.post("/cse1010/auth/dev-login", json={"email": "pat.prof@uconn.edu", "net_id": "prf00001", "role": "instructor"})
    assert a.get("/cse1010/me").status_code == 200
    # Same browser (same cookie jar) visiting the other copy is not logged in there
    b = TestClient(b_app, base_url=CLIENT_BASE, cookies=a.cookies)
    assert b.get("/test-version1/me").status_code == 401


def test_frontend_can_live_elsewhere(tmp_path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        app = create_app(Settings(db_path=tmp_path / "x.db", media_dir=tmp_path / "m", secret_key="k", dev_login=True,
                                  public_url=f"{HOST}/cse1010/api", frontend_url=f"{HOST}/cse1010/"))
    c = TestClient(app, base_url=CLIENT_BASE)
    c.post("/cse1010/api/auth/dev-login", json={"email": "pat.prof@uconn.edu", "net_id": "prf00001", "role": "instructor"})
    cid = c.post("/cse1010/api/courses", json={"term": "T", "subject": "C", "catalog": "1", "title": "t"}).json()["id"]
    q = c.post("/cse1010/api/questions", json={"type": "free_text", "body_md": "?"}).json()
    poll = c.post(f"/cse1010/api/courses/{cid}/polls", json={"question_id": q["id"]}).json()
    assert poll["join_url"] == f"{HOST}/cse1010/join/{poll['access_code']}"


@pytest.mark.parametrize("bad", ["huskypoll.cse.uconn.edu", "ftp://x.edu", "https://x.edu/a?b=1", "https://"])
def test_bad_public_url_rejected(tmp_path, bad):
    with pytest.raises(ValueError, match="public_url"):
        Settings(db_path=tmp_path / "x.db", secret_key="k", public_url=bad)


# --- account roles ----------------------------------------------------------------

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


# --- the whole site: frontend at SITE_URL/, API at SITE_URL/api ----------------------

def site_app(tmp_path, site, dist=None, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return create_app(Settings(db_path=tmp_path / "site.db", media_dir=tmp_path / "media", secret_key="k",
                                   dev_login=True, site_url=site, frontend_dist=dist, **kw))


def fake_dist(tmp_path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<!doctype html><html><head><meta charset="UTF-8" />'
                                     '<script type="module" src="./assets/app.js"></script></head>'
                                     '<body><div id="root"></div></body></html>')
    (dist / "assets" / "app.js").write_text("console.log('hi')")
    (dist / "favicon.svg").write_text("<svg/>")
    return dist


def test_default_api_lives_under_api(tmp_path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        app = create_app(Settings(db_path=tmp_path / "d.db", media_dir=tmp_path / "m", secret_key="k"))
    c = TestClient(app)
    assert c.get("/api/health").json() == {"ok": True}
    assert "/api/openapi.json" in c.get("/api/docs").text


@pytest.mark.parametrize("path", ["/cse1010/api/health", "/api/health", "/health"])
def test_site_api_any_proxy_style(tmp_path, path):
    c = TestClient(site_app(tmp_path, f"{HOST}/cse1010"), base_url=CLIENT_BASE)
    assert c.get(path).json() == {"ok": True}


def test_site_urls_point_at_the_right_places(tmp_path):
    app = site_app(tmp_path, f"{HOST}/cse1010")
    c = TestClient(app, base_url=CLIENT_BASE, follow_redirects=False)
    r = c.post("/cse1010/api/auth/dev-login", json={"email": "pat.prof@uconn.edu", "net_id": "prf00001",
                                                     "role": "instructor"})
    assert "path=/cse1010/api" in r.headers["set-cookie"]
    assert "cse1010%2Fapi%2Fauth%2Fcas%2Fcallback" in c.get("/cse1010/api/auth/login").headers["location"]
    img = c.post("/cse1010/api/media", files={"file": ("a.png", tiny_png())}).json()
    assert img["url"].startswith(f"{HOST}/cse1010/api/media/")
    cid = c.post("/cse1010/api/courses", json={"term": "T", "subject": "C", "catalog": "1", "title": "t"}).json()["id"]
    q = c.post("/cse1010/api/questions", json={"type": "free_text", "body_md": "?"}).json()
    poll = c.post(f"/cse1010/api/courses/{cid}/polls", json={"question_id": q["id"]}).json()
    assert poll["join_url"] == f"{HOST}/cse1010/join/{poll['access_code']}"   # a frontend page
    c.get("/cse1010/api/auth/login", params={"next": "/courses/1"})
    app.state.cas_validator = lambda s, t: {"net_id": "jos10001", "email": "jonathan.smith@uconn.edu"}
    assert c.get("/cse1010/api/auth/cas/callback", params={"ticket": "x"}).headers["location"] == f"{HOST}/cse1010/courses/1"


@pytest.mark.parametrize("prefix_kept", [True, False])
def test_site_serves_the_frontend(tmp_path, prefix_kept):
    app = site_app(tmp_path, f"{HOST}/cse1010", dist=fake_dist(tmp_path))
    c = TestClient(app, base_url=CLIENT_BASE, follow_redirects=False)
    p = "/cse1010" if prefix_kept else ""   # with or without the proxy stripping the prefix

    for page in ("/", "/courses/3", "/join/ABCDE"):   # React routes all get index.html
        r = c.get(p + page)
        assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
        assert '<base href="/cse1010/">' in r.text
        assert '"apiBase": "/cse1010/api"' in r.text and '"basePath": "/cse1010"' in r.text
    asset = c.get(p + "/assets/app.js")
    assert asset.text == "console.log('hi')" and "immutable" in asset.headers["cache-control"]
    assert c.get(p + "/favicon.svg").text == "<svg/>"
    assert c.get(p + "/assets/missing.js").status_code == 404
    assert c.get(p + "/api/health").json() == {"ok": True}
    assert c.post(p + "/courses", json={}).status_code == 405
    if prefix_kept:
        r = c.get("/cse1010?x=1")
        assert r.status_code == 308 and r.headers["location"] == "/cse1010/?x=1"

    # Login and live updates through the same site. (When the proxy strips the prefix the
    # browser still sends the /cse1010/api cookie; the test client can't know that, so pass it.)
    c.post(p + "/api/auth/dev-login", json={"email": "pat.prof@uconn.edu", "net_id": "prf00001", "role": "instructor"})
    cookie = {"cookie": f"huskypoll_session={c.cookies.get('huskypoll_session')}"}
    cid = c.post(p + "/api/courses", headers=cookie,
                 json={"term": "T", "subject": "C", "catalog": "1", "title": "t"}).json()["id"]
    with c.websocket_connect(f"{p}/api/ws/courses/{cid}", headers=cookie) as ws:
        assert ws.receive_json()["type"] == "hello"


def test_site_at_domain_root(tmp_path):
    c = TestClient(site_app(tmp_path, HOST, dist=fake_dist(tmp_path)), base_url=CLIENT_BASE)
    r = c.get("/courses/3")
    assert '<base href="/">' in r.text and '"apiBase": "/api"' in r.text
    assert c.get("/api/health").json() == {"ok": True}


def test_frontend_files_cannot_escape_dist(tmp_path):
    (tmp_path / "secret.txt").write_text("top secret")
    c = TestClient(site_app(tmp_path, f"{HOST}/cse1010", dist=fake_dist(tmp_path)), base_url=CLIENT_BASE)
    for path in ("/cse1010/../secret.txt", "/cse1010/%2e%2e/secret.txt", "/cse1010/assets/../../secret.txt"):
        assert "top secret" not in c.get(path).text


def test_frontend_dist_without_build_is_a_clear_error(tmp_path):
    with pytest.raises(RuntimeError, match="npm run build"):
        site_app(tmp_path, HOST, dist=tmp_path / "nothing-here")
