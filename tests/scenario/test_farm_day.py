from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

SCENARIO = Path(__file__).with_name("farm_day.json")
GOLDEN = Path(__file__).with_name("farm_day.golden.json")


@pytest.fixture
def scenario_steps():
    return json.loads(SCENARIO.read_text())["steps"]


def test_farm_day_scenario(client, fake_clock, scenario_steps):
    state: dict = {"mission_id": None, "plan_hash": None, "prior_mission_id": None}
    for step in scenario_steps:
        action = step["action"]
        if action == "chat":
            body = {
                "conversation_id": state.get("conversation_id"),
                "message": step["message"],
                "vehicle": step.get("vehicle", "drone"),
                "battery_pct": step.get("battery_pct", 100),
            }
            r = client.post("/api/chat", json=body)
            assert r.status_code == step.get("expect_status", 200)
            data = r.json()
            state["conversation_id"] = data["conversation_id"]
            if step.get("kind"):
                assert data["kind"] == step["kind"]
            if data.get("mission"):
                state["prior_mission_id"] = state.get("mission_id")
                state["mission_id"] = data["mission"]["id"]
                state["plan_hash"] = data["mission"].get("plan_hash")
                if step.get("mission_status"):
                    assert data["mission"]["status"] == step["mission_status"]
                if step.get("min_actions"):
                    assert len(data["mission"]["plan"]["actions"]) >= step["min_actions"]
                if step.get("issue_codes"):
                    codes = {i["code"] for i in data["mission"]["issues"]}
                    for c in step["issue_codes"]:
                        assert c in codes
        elif action == "repair":
            mid = state["mission_id"]
            r = client.post(f"/api/missions/{mid}/repair", json={})
            if step.get("expect_code"):
                assert r.status_code == 409
                assert r.json()["detail"]["code"] == step["expect_code"]
                continue
            assert r.status_code == 200
            data = r.json()
            if step.get("mission_status"):
                assert data["mission"]["status"] == step["mission_status"]
            if step.get("repair_attempts") is not None:
                assert data["mission"]["repair_attempts"] == step["repair_attempts"]
            state["plan_hash"] = data["mission"].get("plan_hash")
        elif action == "confirm":
            r = client.post(
                f"/api/missions/{state['mission_id']}/confirm",
                json={"plan_hash": state["plan_hash"]},
            )
            assert r.status_code == 200
            run = r.json()
            assert run["status"] == step.get("run_status", "executed")
            if step.get("min_photos"):
                assert len(run["photos"]) >= step["min_photos"]
        elif action == "confirm_wrong":
            r = client.post(
                f"/api/missions/{state['mission_id']}/confirm",
                json={"plan_hash": "0" * 64},
            )
            assert r.status_code == 409
            assert r.json()["detail"]["code"] == step["expect_code"]
        elif action == "confirm_again":
            r = client.post(
                f"/api/missions/{state['mission_id']}/confirm",
                json={"plan_hash": state["plan_hash"]},
            )
            assert r.status_code == 409
        elif action == "confirm_prior":
            r = client.post(
                f"/api/missions/{state['prior_mission_id']}/confirm",
                json={"plan_hash": state.get("plan_hash") or ("0" * 64)},
            )
            assert r.status_code == 409
        elif action == "repair_then_expire":
            r = client.post(f"/api/missions/{state['mission_id']}/repair", json={})
            assert r.status_code == 200
            state["plan_hash"] = r.json()["mission"].get("plan_hash")
            fake_clock.advance(step.get("advance_seconds", 601))
            r = client.post(
                f"/api/missions/{state['mission_id']}/confirm",
                json={"plan_hash": state["plan_hash"]},
            )
            assert r.status_code == 409
            assert r.json()["detail"]["code"] == step["expect_code"]


def test_farm_day_golden(client, fake_clock, scenario_steps):
    if not GOLDEN.exists() and os.environ.get("UPDATE_GOLDEN") != "1":
        pytest.skip("golden file missing; run with UPDATE_GOLDEN=1")
    test_farm_day_scenario(client, fake_clock, scenario_steps)
    if os.environ.get("UPDATE_GOLDEN") == "1":
        snapshot = _snapshot(client)
        GOLDEN.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
        return
    expected = json.loads(GOLDEN.read_text())
    assert _snapshot(client) == expected


def _snapshot(client):
    import hashlib

    from sqlmodel import Session, select

    from robot_copilot.json_util import canonical_json, quantize_obj
    from robot_copilot.store import AuditEvent, Mission, Run

    store = client.app.state.orchestrator._store
    with Session(store._engine) as session:
        runs = list(session.exec(select(Run)).all())
        audits = list(session.exec(select(AuditEvent).order_by(AuditEvent.at)).all())
        missions = list(session.exec(select(Mission)).all())
    status_hist: dict[str, int] = {}
    for m in missions:
        status_hist[m.status] = status_hist.get(m.status, 0) + 1
    run_payload = []
    for run in runs:
        fs = __import__("json").loads(run.final_state_json)
        run_payload.append(
            {
                "status": run.status,
                "final_state": fs,
                "photos": len(__import__("json").loads(run.photos_json)),
            }
        )
    frames_all = []
    for run in runs:
        frames_all.extend(__import__("json").loads(run.frames_json))
    frame_sha = hashlib.sha256(canonical_json(quantize_obj(frames_all)).encode()).hexdigest()
    return quantize_obj(
        {
            "run_count": len(runs),
            "executed_runs": sum(1 for r in runs if r.status == "executed"),
            "aborted_runs": sum(1 for r in runs if r.status == "aborted"),
            "runs": run_payload,
            "total_photos": sum(len(__import__("json").loads(r.photos_json)) for r in runs),
            "mission_status_histogram": status_hist,
            "audit_kinds": [a.kind for a in audits],
            "frames_sha256": frame_sha,
        }
    )
