"""Helpers shared by the backend test files."""
from __future__ import annotations

import struct
import warnings
import zlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.config import Settings

TESTS_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = TESTS_DIR.parent
SAMPLE_ROSTER = BACKEND_ROOT / "samples" / "studentadmin-template.xlsx"
# Kept for tests that build paths relative to the backend directory.
ROOT = BACKEND_ROOT


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


def login(app, email, net_id=None, first=None, last=None, role=None) -> TestClient:
    c = TestClient(app)
    r = c.post("/auth/dev-login", json={"email": email, "net_id": net_id, "first_name": first, "last_name": last,
                                        "role": role})
    assert r.status_code == 200, r.text
    return c


def _fails(db, sql, params=None, match=None):
    with pytest.raises(IntegrityError, match=match), db.begin_nested():
        db.execute(text(sql), params or {})


def _count(db, table, where="1=1", **params):
    return db.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}"), params).scalar()
