"""Roster endpoints: import, re-import and dropping missing students.

Run with: python -m pytest -q tests/test_api_roster.py
"""

from __future__ import annotations

from tests.helpers import ROOT


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


def test_roster_csv_reimport_and_drop_missing(lecture):
    prof, cid = lecture["prof"], lecture["cid"]
    # New StudentAdmin export: Bob is still in, Ann dropped the course, Cat joined.
    csv = b"NetID,Email\r\nbba22222,BOB.BAKER@uconn.edu\r\nCCA33333,Cat.Cole@UConn.edu\r\n"
    r = prof.post(f"/courses/{cid}/roster/import", files={"file": ("roster.csv", csv, "text/csv")})
    assert r.status_code == 200
    res = r.json()
    assert (res["enrolled"], res["unchanged"], res["dropped"]) == (1, 1, 0)
    assert [u["net_id"] for u in res["added"]] == ["cca33333"]
    assert [u["net_id"] for u in res["missing"]] == ["aab11111"]
    assert len(prof.get(f"/courses/{cid}/roster").json()) == 3  # nobody dropped yet

    r = prof.post(f"/courses/{cid}/roster/drop", json={"user_ids": [u["id"] for u in res["missing"]]})
    assert r.json() == {"dropped": 1}
    assert {e["user"]["net_id"] for e in prof.get(f"/courses/{cid}/roster").json()} == {"bba22222", "cca33333"}
    assert lecture["ann"].post(f"/courses/{cid}/roster/drop", json={"user_ids": []}).status_code in (403, 404)

    bad = prof.post(f"/courses/{cid}/roster/import", files={"file": ("x.csv", b"foo,bar\n1,2\n")})
    assert bad.status_code == 400 and "header row" in bad.json()["detail"]
