"""Path prefixes, frontend serving and site/public URL configuration.

Run with: python -m pytest -q tests/test_api_site.py
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.app import create_app
from app.config import Settings
from tests.helpers import tiny_png

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
