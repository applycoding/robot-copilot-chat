from __future__ import annotations

from sqlmodel import Session, select

from robot_copilot.store import Run


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
