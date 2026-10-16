"""Settings, read from environment variables (a .env file is not required).

The app never assumes it runs at the root of a domain. Set HUSKYPOLL_SITE_URL
to the full address people type, path included, for example:

    https://huskypoll.cse.uconn.edu
    https://huskypoll.cse.uconn.edu/cse1010
    https://huskypoll.cse.uconn.edu/test-version1

The web pages live at SITE_URL/ and the API at SITE_URL/api. Every address
the server produces (login return, image links, QR codes, join links, the
login cookie's path) is built from these settings. The reverse proxy may pass
the path prefix through or strip it - both work. Several copies can share a
domain under different paths without sharing logins.

| Variable                    | Default                      | Meaning |
| HUSKYPOLL_SITE_URL          | http://localhost:8000        | Full address of the site, including any path prefix |
| HUSKYPOLL_PUBLIC_URL        | SITE_URL/api                 | Full address of the API (only if it isn't SITE_URL/api) |
| HUSKYPOLL_FRONTEND_URL      | SITE_URL                     | Full address of the web pages (only if they're elsewhere) |
| HUSKYPOLL_FRONTEND_DIST     | (none)                       | Built frontend folder (frontend/dist) to serve at SITE_URL/ |
| HUSKYPOLL_DB                | huskypoll.db                 | SQLite database file |
| HUSKYPOLL_MEDIA_DIR         | media                        | Folder for uploaded images |
| HUSKYPOLL_SECRET_KEY        | (random each start)          | Signs login cookies - MUST be set in production |
| HUSKYPOLL_CAS_URL           | https://login.uconn.edu/cas  | UConn CAS server (confirm with ITS) |
| HUSKYPOLL_DEV_LOGIN         | 0                            | 1 = enable /auth/dev-login (NEVER in production) |
| HUSKYPOLL_CORS_ORIGINS      | (none)                       | Extra frontend origins allowed to call the API |
| HUSKYPOLL_ADMIN_NETIDS      | (none)                       | Comma-separated NetIDs made admins at login |
| HUSKYPOLL_INSTRUCTOR_NETIDS | (none)                       | Comma-separated NetIDs made (at least) instructors at login |
| HUSKYPOLL_SECURE_COOKIES    | 0                            | 1 = cookies only over HTTPS (set in production) |
"""
from __future__ import annotations

import os
import secrets
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


def _flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def _list(name: str) -> list[str]:
    return [x.strip() for x in os.environ.get(name, "").split(",") if x.strip()]


@dataclass
class Settings:
    db_path: Path = field(default_factory=lambda: Path(os.environ.get("HUSKYPOLL_DB", "huskypoll.db")))
    media_dir: Path = field(default_factory=lambda: Path(os.environ.get("HUSKYPOLL_MEDIA_DIR", "media")))
    secret_key: str = field(default_factory=lambda: os.environ.get("HUSKYPOLL_SECRET_KEY", ""))
    site_url: str = field(default_factory=lambda: os.environ.get("HUSKYPOLL_SITE_URL", ""))
    public_url: str = field(default_factory=lambda: os.environ.get("HUSKYPOLL_PUBLIC_URL", ""))
    frontend_url: str = field(default_factory=lambda: os.environ.get("HUSKYPOLL_FRONTEND_URL", ""))
    frontend_dist: Path | None = field(
        default_factory=lambda: Path(os.environ["HUSKYPOLL_FRONTEND_DIST"]) if os.environ.get("HUSKYPOLL_FRONTEND_DIST") else None)
    cas_url: str = field(default_factory=lambda: os.environ.get("HUSKYPOLL_CAS_URL", "https://login.uconn.edu/cas").rstrip("/"))
    dev_login: bool = field(default_factory=lambda: _flag("HUSKYPOLL_DEV_LOGIN"))
    cors_origins: list[str] = field(default_factory=lambda: _list("HUSKYPOLL_CORS_ORIGINS"))
    admin_net_ids: list[str] = field(default_factory=lambda: [x.lower() for x in _list("HUSKYPOLL_ADMIN_NETIDS")])
    instructor_net_ids: list[str] = field(default_factory=lambda: [x.lower() for x in _list("HUSKYPOLL_INSTRUCTOR_NETIDS")])
    secure_cookies: bool = field(default_factory=lambda: _flag("HUSKYPOLL_SECURE_COOKIES"))

    @property
    def base_path(self) -> str:
        """Path prefix of the API, e.g. '/cse1010/api' ('' when the API is at a domain root)."""
        return urlsplit(self.public_url).path.rstrip("/")

    @property
    def site_base_path(self) -> str:
        """Path prefix of the whole site, e.g. '/cse1010' ('' at a domain root)."""
        return urlsplit(self.site_url).path.rstrip("/")

    def api_url(self, path: str) -> str:
        """Absolute URL of an API route: api_url('/media/abc') -> https://host/cse1010/media/abc"""
        return f"{self.public_url}/{path.lstrip('/')}"

    def frontend_link(self, path: str = "/") -> str:
        """Absolute URL of a frontend page: frontend_link('/join/ABCDE')."""
        return f"{self.frontend_url}/{path.lstrip('/')}"

    def __post_init__(self) -> None:
        for name in ("site_url", "public_url", "frontend_url"):
            value = getattr(self, name).rstrip("/")
            if value:
                parts = urlsplit(value)
                if parts.scheme not in ("http", "https") or not parts.netloc or parts.query or parts.fragment:
                    raise ValueError(f"{name} must look like https://host or https://host/some/path, got {value!r}")
            setattr(self, name, value)
        if not self.secret_key:
            warnings.warn("HUSKYPOLL_SECRET_KEY is not set: using a random key, so logins reset on every "
                          "restart. Set it in production.", stacklevel=2)
            self.secret_key = secrets.token_urlsafe(32)
        # Fill in whichever addresses weren't given.
        if not self.site_url:
            if self.public_url:
                self.site_url = self.public_url.removesuffix("/api")
            else:
                self.site_url = "http://localhost:8000"
        if not self.public_url:
            self.public_url = f"{self.site_url}/api"
        if not self.frontend_url:
            self.frontend_url = self.site_url
        if self.frontend_dist is not None:
            self.frontend_dist = Path(self.frontend_dist)
            if not self.public_url.startswith(self.site_url + "/"):
                raise ValueError("to serve the frontend, the API must live under the site address "
                                 f"(site {self.site_url}, API {self.public_url})")
        if self.dev_login:
            warnings.warn("HUSKYPOLL_DEV_LOGIN is on: anyone can log in as anyone. Never use this in production.",
                          stacklevel=2)
