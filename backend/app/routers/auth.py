"""Login with UConn CAS, plus a developer login for local testing.

Flow (CAS protocol 3.0):
  1. Frontend sends the browser to   GET /auth/login?next=/courses
  2. We redirect to UConn CAS; the user signs in there.
  3. CAS redirects back to           GET /auth/cas/callback?ticket=ST-...
  4. We validate the ticket with CAS (server to server), get the NetID and
     attributes, apply the email rules (services.record_login), set a signed
     session cookie and redirect to the frontend.

UConn is moving to Microsoft Entra ID; when ITS registers the app, an Entra
(OpenID Connect) login can be added here alongside CAS without touching the
rest of the API, because everything else only uses request.session["user_id"].
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from huskypoll_db import services as svc
from huskypoll_db.models import User

from .. import schemas as s
from ..config import Settings
from ..deps import current_user, get_db, get_settings
from ..serializers import user_out

router = APIRouter(tags=["auth"])
CAS_NS = {"cas": "http://www.yale.edu/tp/cas"}


def _safe_next(next_: str | None) -> str:
    """`next` is a page path relative to the frontend's base URL (e.g. "/courses/3",
    not "/cse1010/courses/3"). Only such paths are allowed (prevents open redirects)."""
    if next_ and next_.startswith("/") and not next_.startswith("//"):
        return next_
    return "/"


def _service_url(settings: Settings) -> str:
    return settings.api_url("/auth/cas/callback")


def validate_cas_ticket(settings: Settings, ticket: str) -> dict:
    """Ask CAS whether the ticket is genuine. Returns {"net_id", "email", "first_name", "last_name"}."""
    resp = httpx.get(f"{settings.cas_url}/p3/serviceValidate",
                     params={"service": _service_url(settings), "ticket": ticket}, timeout=10)
    resp.raise_for_status()
    return parse_cas_response(resp.text)


def parse_cas_response(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    ok = root.find("cas:authenticationSuccess", CAS_NS)
    if ok is None:
        fail = root.find("cas:authenticationFailure", CAS_NS)
        raise HTTPException(401, f"UConn login failed: {(fail.text or '').strip() if fail is not None else 'unknown'}")
    attrs = {}
    a = ok.find("cas:attributes", CAS_NS)
    if a is not None:
        for el in a:
            attrs[el.tag.split("}")[-1].lower()] = (el.text or "").strip()
    net_id = (ok.findtext("cas:user", default="", namespaces=CAS_NS) or "").strip()

    def first(*names):  # attribute names vary by CAS setup; confirm UConn's with ITS
        return next((attrs[n] for n in names if attrs.get(n)), None)

    return {
        "net_id": net_id,
        "email": first("mail", "email", "uconnemail") or (f"{net_id}@uconn.edu" if net_id else None),
        "first_name": first("givenname", "firstname", "given_name"),
        "last_name": first("sn", "lastname", "surname", "family_name"),
    }


def _log_in(request: Request, db: Session, settings: Settings, info: dict, dev_role: str | None = None) -> User:
    try:
        net_id = (info.get("net_id") or "").strip() or None
        email = info.get("email") or (f"{net_id}@uconn.edu" if net_id else "")
        user = svc.record_login(db, email=email, net_id=net_id,
                                first_name=info.get("first_name"), last_name=info.get("last_name"),
                                ip_address=request.client.host if request.client else None)
    except svc.HuskyPollError as exc:
        raise HTTPException(403, str(exc))
    if user.net_id in settings.admin_net_ids:
        svc.promote(user, "admin")
    elif user.net_id in settings.instructor_net_ids:
        svc.promote(user, "instructor")
    if dev_role:  # development login only
        user.role = dev_role
    db.flush()
    request.session.clear()
    request.session["user_id"] = user.id
    return user


@router.get("/auth/login", summary="Start UConn login (redirects to CAS)")
def login(request: Request, settings: Annotated[Settings, Depends(get_settings)], next: str | None = None):
    request.session["login_next"] = _safe_next(next)
    return RedirectResponse(f"{settings.cas_url}/login?{urlencode({'service': _service_url(settings)})}")


@router.get("/auth/cas/callback", include_in_schema=False)
def cas_callback(request: Request, ticket: str, db: Annotated[Session, Depends(get_db)],
                 settings: Annotated[Settings, Depends(get_settings)]):
    next_ = request.session.get("login_next", "/")
    info = request.app.state.cas_validator(settings, ticket)
    _log_in(request, db, settings, info)
    return RedirectResponse(settings.frontend_link(_safe_next(next_)), status_code=303)


@router.post("/auth/dev-login", response_model=s.UserOut,
             summary="Developer login (only when HUSKYPOLL_DEV_LOGIN=1)")
def dev_login(body: s.DevLogin, request: Request, db: Annotated[Session, Depends(get_db)],
              settings: Annotated[Settings, Depends(get_settings)]):
    if not settings.dev_login:
        raise HTTPException(404, "Not found")
    return user_out(_log_in(request, db, settings, body.model_dump(exclude={"role"}), dev_role=body.role))


@router.post("/auth/logout", status_code=204, summary="Log out")
def logout(request: Request):
    request.session.clear()


@router.get("/me", response_model=s.UserOut, summary="Who is logged in")
def me(user: Annotated[User, Depends(current_user)]):
    return user_out(user)
