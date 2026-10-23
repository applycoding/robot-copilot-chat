from __future__ import annotations

import json

from sqlmodel import Session, select

from robot_copilot.store import MissionRevision, Run


def _run_count(client) -> int:
    store = client.app.state.orchestrator._store
    with Session(store._engine) as session:
        return len(session.exec(select(Run)).all())


def test_wrong_hash_no_run(client):
    before = _run_count(client)
    r = client.post("/api/chat", json={"message": "inspect the north fence"})
    mid = r.json()["mission"]["id"]
    r2 = client.post(f"/api/missions/{mid}/confirm", json={"plan_hash": "0" * 64})
    assert r2.status_code == 409
    assert r2.json()["detail"]["code"] == "plan_hash_mismatch"
    assert _run_count(client) == before


def test_confirm_creates_run(client):
    before = _run_count(client)
    r = client.post("/api/chat", json={"message": "take a photo of the barn"})
    mid = r.json()["mission"]["id"]
    ph = r.json()["mission"]["plan_hash"]
    r2 = client.post(f"/api/missions/{mid}/confirm", json={"plan_hash": ph})
    assert r2.status_code == 200
    assert _run_count(client) == before + 1


def test_chat_text_no_run(client):
    before = _run_count(client)
    client.post("/api/chat", json={"message": "hello"})
    assert _run_count(client) == before


def test_not_confirmable_after_execute(client):
    r = client.post("/api/chat", json={"message": "take a photo of the barn"})
    mid = r.json()["mission"]["id"]
    ph = r.json()["mission"]["plan_hash"]
    client.post(f"/api/missions/{mid}/confirm", json={"plan_hash": ph})
    r2 = client.post(f"/api/missions/{mid}/confirm", json={"plan_hash": ph})
    assert r2.status_code == 409
    assert r2.json()["detail"]["code"] == "not_confirmable"


def test_tampered_report_json_does_not_change_frames(client):
    r = client.post("/api/chat", json={"message": "take a photo of the barn"})
    mid = r.json()["mission"]["id"]
    ph = r.json()["mission"]["plan_hash"]
    store = client.app.state.orchestrator._store
    with Session(store._engine) as session:
        rev = session.exec(
            select(MissionRevision).where(MissionRevision.mission_id == mid)
        ).first()
        assert rev and rev.report_json
        report = json.loads(rev.report_json)
        if report.get("resolved") and report["resolved"].get("legs"):
            report["resolved"]["legs"][0]["end"]["x_m"] = 9999.0
        rev.report_json = json.dumps(report)
        session.add(rev)
        session.commit()
    run = client.post(f"/api/missions/{mid}/confirm", json={"plan_hash": ph})
    assert run.status_code == 200
    frames = run.json()["frames"]
    assert all(abs(f["x_m"]) < 500 for f in frames)


def test_tampered_plan_json_revalidation_failed(client):
    r = client.post("/api/chat", json={"message": "take a photo of the barn"})
    mid = r.json()["mission"]["id"]
    ph = r.json()["mission"]["plan_hash"]
    store = client.app.state.orchestrator._store
    with Session(store._engine) as session:
        rev = session.exec(
            select(MissionRevision).where(MissionRevision.mission_id == mid)
        ).first()
        assert rev and rev.plan_json
        plan = json.loads(rev.plan_json)
        plan["actions"].insert(1, {"type": "goto", "place": "No Such Place"})
        rev.plan_json = json.dumps(plan)
        session.add(rev)
        session.commit()
    r2 = client.post(f"/api/missions/{mid}/confirm", json={"plan_hash": ph})
    assert r2.status_code == 409
    assert r2.json()["detail"]["code"] == "revalidation_failed"
    assert _run_count(client) == 0
