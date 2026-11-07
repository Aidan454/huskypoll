"""HTTP auth: health check, dev login, CAS login and the DB dependency.

Run with: python -m pytest -q tests/test_api_auth.py
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.app import create_app
from app.routers.auth import parse_cas_response
from tests.helpers import make_settings


def test_health_and_login_required(app):
    c = TestClient(app)
    assert c.get("/health").json() == {"ok": True}
    assert c.get("/me").status_code == 401
    assert c.get("/courses").status_code == 401


def test_db_dependency_commits_before_the_response():
    """A client may fetch a row right after creating it, so get_db must commit
    before the response is sent (scope="function", not the FastAPI default)."""
    from app.deps import get_db
    from app.routers import auth, courses, polls, questions, users

    def walk(dependant):
        for sub in dependant.dependencies:
            if sub.call is get_db:
                assert sub.scope == "function", "use Depends(get_db, scope='function')"
            walk(sub)

    for module in (auth, courses, polls, questions, users):
        for route in module.router.routes:
            dependant = getattr(route, "dependant", None)
            if dependant is not None:
                walk(dependant)


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
