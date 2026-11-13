"""Poll endpoints: lecture flow, timed polls, question types, poll sets and codes.

Run with: python -m pytest -q tests/test_api_polls.py
"""

from __future__ import annotations

from tests.helpers import login


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
    # Participation is earned for answering, whether or not the answer was correct.
    assert ann.get(f"/courses/{cid}/my-participation").json() == {
        "polls": 1, "answered": 1, "correct": 0, "points": 1.0, "points_possible": 1.0}

    # Reopen: students only, answers hidden again, late answers accepted, then close again
    assert ann.post(f"/polls/{poll['id']}/reopen").status_code in (403, 404)
    reopened = prof.post(f"/polls/{poll['id']}/reopen").json()
    assert reopened["status"] == "open" and reopened["access_code"] == poll["access_code"]
    assert ann.get(f"/polls/{poll['id']}").json()["question"]["explanation_md"] is None
    assert bob.post(f"/polls/{poll['id']}/responses", json={"option_ids": [right]}).status_code == 200
    assert prof.post(f"/polls/{poll['id']}/reopen").status_code == 400
    prof.post(f"/polls/{poll['id']}/close")

    # Export and log
    csv = prof.get(f"/courses/{cid}/export/participation.csv")
    assert csv.headers["content-type"].startswith("text/csv")
    header, ann_row, bob_row = csv.text.strip().splitlines()
    assert header.startswith("Username,W1-") and header.endswith("-PART")
    assert ann_row == "AAB11111,100" and bob_row == "BBA22222,100"
    sessions = prof.get(f"/courses/{cid}/participation/sessions").json()
    assert len(sessions) == 1 and sessions[0]["column"] == header.split(",")[1]
    assert sessions[0]["exported_at"] is not None  # the download above included it
    only_username = prof.get(f"/courses/{cid}/export/participation.csv", params={"dates": "2000-01-01"})
    assert only_username.text.strip().splitlines()[0] == "Username"
    events = {e["event_type"] for e in prof.get(f"/courses/{cid}/events").json()}
    assert {"poll_open", "response_submit", "response_update", "poll_close", "export_participation"} <= events


def test_timed_poll_countdown_and_add_time(lecture):
    prof, ann, cid, q = lecture["prof"], lecture["ann"], lecture["cid"], lecture["q"]

    poll = prof.post(f"/courses/{cid}/polls", json={"question_id": q["id"], "duration_seconds": 120}).json()
    assert poll["duration_seconds"] == 120 and poll["closes_at"]
    assert 118 <= poll["seconds_remaining"] <= 120

    # Students see the same deadline, without comparing clocks themselves.
    seen = ann.get(f"/polls/{poll['id']}").json()
    assert 118 <= seen["seconds_remaining"] <= 120
    option = seen["question"]["options"][0]["id"]
    assert ann.post(f"/polls/{poll['id']}/responses", json={"option_ids": [option]}).status_code == 200

    # Only an instructor can add time.
    assert ann.post(f"/polls/{poll['id']}/extend", json={"seconds": 60}).status_code == 403
    extended = prof.post(f"/polls/{poll['id']}/extend", json={"seconds": 60}).json()
    assert 178 <= extended["seconds_remaining"] <= 180

    # Adding time to a closed poll opens it again, so late students can answer.
    prof.post(f"/polls/{poll['id']}/close")
    reopened = prof.post(f"/polls/{poll['id']}/extend", json={"seconds": 30}).json()
    assert reopened["status"] == "open" and reopened["closed_at"] is None
    assert 28 <= reopened["seconds_remaining"] <= 30

    # Omitting the duration uses the one-minute default.
    default = prof.post(f"/courses/{cid}/polls", json={"question_id": q["id"]}).json()
    assert default["duration_seconds"] == 60
    assert 58 <= default["seconds_remaining"] <= 60

    # An explicit null still means no timer, and that poll cannot be extended.
    plain = prof.post(f"/courses/{cid}/polls", json={"question_id": q["id"], "duration_seconds": None}).json()
    assert plain["duration_seconds"] is None and plain["seconds_remaining"] is None
    r = prof.post(f"/polls/{plain['id']}/extend", json={"seconds": 60})
    assert r.status_code == 400 and "no timer" in r.json()["detail"]

    # The duration box is in minutes, so silly values are rejected up front.
    assert prof.post(f"/courses/{cid}/polls", json={"question_id": q["id"], "duration_seconds": 0}).status_code == 422
    assert prof.post(f"/courses/{cid}/polls", json={"question_id": q["id"], "duration_seconds": 1}).status_code == 422


def test_quick_poll_then_add_answer_and_regrade(lecture):
    prof, ann, bob, cid = lecture["prof"], lecture["ann"], lecture["bob"], lecture["cid"]
    poll = prof.post(f"/courses/{cid}/polls/quick", json={
        "type": "mc_single", "body_md": "Typed in lecture", "options": [{"text_md": "A"}, {"text_md": "B"}]}).json()
    assert poll["duration_seconds"] == 60  # quick polls get the one-minute default too
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


def test_poll_set_asks_questions_one_at_a_time(lecture):
    prof, ann, cid, q1 = lecture["prof"], lecture["ann"], lecture["cid"], lecture["q"]
    q2 = prof.post("/questions", json={"type": "numeric", "body_md": "3*3?", "numeric_answer": 9}).json()
    q3 = prof.post("/questions", json={"type": "free_text", "body_md": "Name a sort."}).json()

    r = prof.post(f"/courses/{cid}/polls/set", json={"question_ids": [q2["id"], q1["id"], q3["id"]]})
    assert r.status_code == 201, r.text
    first, second, third = r.json()
    assert [p["status"] for p in (first, second, third)] == ["open", "draft", "draft"]
    assert [p["duration_seconds"] for p in (first, second, third)] == [60, 60, 60]  # one-minute default
    assert first["question"]["id"] == q2["id"]  # the order the instructor chose
    assert first["position"] < second["position"] < third["position"]
    code = first["access_code"]

    # students see only what has been asked
    listed = ann.get(f"/courses/{cid}/polls").json()
    assert [p["id"] for p in listed] == [first["id"]]
    assert ann.get(f"/polls/{second['id']}").status_code == 404
    assert ann.post(f"/polls/{second['id']}/responses", json={"option_ids": []}).status_code >= 400

    assert ann.post(f"/polls/{first['id']}/responses", json={"numeric_answer": 9}).status_code == 200
    assert prof.post(f"/polls/{first['id']}/close").status_code == 200

    # between questions the code still finds the set
    between = ann.get(f"/polls/by-code/{code}").json()
    assert between["id"] == first["id"] and between["status"] == "closed"

    # the next question keeps the same code
    nxt = prof.post(f"/polls/{second['id']}/open").json()
    assert nxt["status"] == "open" and nxt["access_code"] == code
    assert ann.get(f"/polls/by-code/{code}").json()["id"] == second["id"]
    assert prof.post(f"/polls/{second['id']}/open").status_code == 400  # already open

    # a queued question can be dropped before it is asked, but not after
    assert prof.delete(f"/polls/{second['id']}").status_code == 400
    assert ann.delete(f"/polls/{third['id']}").status_code == 403
    assert prof.delete(f"/polls/{third['id']}").status_code == 204
    assert prof.post(f"/polls/{second['id']}/close").status_code == 200
    assert ann.get(f"/polls/by-code/{code}").status_code == 404  # nothing left in the set


def test_poll_set_needs_an_instructor_and_questions(lecture):
    ann, prof, cid, q = lecture["ann"], lecture["prof"], lecture["cid"], lecture["q"]
    assert ann.post(f"/courses/{cid}/polls/set", json={"question_ids": [q["id"]]}).status_code == 403
    assert prof.post(f"/courses/{cid}/polls/set", json={"question_ids": []}).status_code == 422
    r = prof.post(f"/courses/{cid}/polls/set", json={"question_ids": [q["id"]], "open_first": False})
    assert r.json()[0]["status"] == "draft"


def test_anyone_with_the_code_can_answer(app, lecture):
    prof, cid, q = lecture["prof"], lecture["cid"], lecture["q"]
    visitor = login(app, "vis12345@uconn.edu")
    poll = prof.post(f"/courses/{cid}/polls", json={"question_id": q["id"]}).json()
    right = next(o["id"] for o in q["options"] if o["is_correct"])

    # without the code: nothing
    assert visitor.get(f"/polls/{poll['id']}").status_code == 404
    assert visitor.get(f"/courses/{cid}/polls", params={"session_id": poll["session_id"]}).status_code == 404

    # with the code: this lecture's poll, and nothing else in the course
    found = visitor.get(f"/polls/by-code/{poll['access_code']}")
    assert found.status_code == 200 and found.json()["question"]["options"][0].get("is_correct") is None
    assert visitor.post(f"/polls/{poll['id']}/responses", json={"option_ids": [right]}).status_code == 200
    assert len(visitor.get(f"/courses/{cid}/polls", params={"session_id": poll["session_id"]}).json()) == 1
    assert visitor.get(f"/courses/{cid}/polls").status_code == 404
    assert visitor.get(f"/courses/{cid}").status_code == 404
    assert visitor.get(f"/courses/{cid}/history").status_code == 404
    assert visitor.get("/courses").json() == []
    with visitor.websocket_connect(f"/ws/courses/{cid}") as ws:
        assert ws.receive_json()["role"] == "guest"

    # results and the answer key once closed
    assert visitor.get(f"/polls/{poll['id']}/results").status_code == 403  # not shared yet
    prof.patch(f"/polls/{poll['id']}", json={"show_results": True})
    assert visitor.get(f"/polls/{poll['id']}/results").json()["responses"] == 1
    prof.post(f"/polls/{poll['id']}/close")
    closed = visitor.get(f"/polls/{poll['id']}").json()
    assert closed["my_response"]["is_correct"] is True

    # the instructor sees who wasn't on the roster; grades cover the roster only
    rows = prof.get(f"/polls/{poll['id']}/responses").json()
    assert [r["on_roster"] for r in rows] == [False]
    totals = prof.get(f"/courses/{cid}/participation").json()
    assert "vis12345" not in [t["net_id"] for t in totals] and len(totals) == 2
    ann_row = next(t for t in totals if t["net_id"] == "aab11111")
    assert ann_row["answered"] == 0
