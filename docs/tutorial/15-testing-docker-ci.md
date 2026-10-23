# 15 Testing, Docker, and CI

## Goal

You will see how the repo stays offline after install: socket guards, env scrubbing, property tests, and the farm-day golden JSON scenario. Docker packages the same factory entrypoint with a documented loopback bind and volume for SQLite. GitHub Actions jobs pin third-party actions by SHA and run gitleaks without live API keys.

Property tests generate valid plans then mutate single rules to match an analytic oracle, giving stronger coverage than hand-picked examples alone. Socket guards complement fail-closed HTTP transports in provider unit tests. Playwright uses free ports and instance nonces so parallel CI shards do not collide on SQLite paths. Take brief notes linking each excerpt to the checkpoint test before you continue to the next chapter.

## Files

- `tests/scenario/test_farm_day.py`
- `tests/repo/test_ci_pins.py`
- `src/robot_copilot/main.py`

## Walkthrough

1. Farm-day scenario replays scripted chat, repair, confirm, and decline steps. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
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
```

Quantized summaries in the golden file catch unintended validator drift. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

2. CI pin tests freeze action SHAs declared in workflow YAML. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
def test_ci_pins():
    text = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "permissions:" in text and "contents: read" in text
    assert "ubuntu-24.04" in text
    assert "secrets." not in text
    for line in text.splitlines():
        if "uses:" in line:
            assert re.search(r"@[0-9a-f]{40}\s+# v", line), line
    assert "uv run --no-sync" in text
```

Pinning prevents tag-moving supply-chain surprises on unattended runners. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

3. Application entry stays the same factory whether you run uvicorn locally or in the container. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
def create_app(
    settings: AppSettings | None = None,
    *,
    provider: LLMProvider | None = None,
    clock: Callable[[], datetime] | None = None,
    id_factory: Callable[[], str] | None = None,
) -> FastAPI:
```

Production image builds skip dev-only Playwright browsers while still calling `create_app` from the Dockerfile CMD. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

## Try it

```bash
RCC_DOTENV=off .venv/bin/python -m pytest tests/scenario/test_farm_day.py -q --no-header
```

Expected tail:

```
1 passed
```

## Exercise

Run `tests/repo/test_hygiene.py` and note which grep forbids inline script in static JavaScript. When you finish, run the checkpoint pytest node to confirm your understanding matches automated expectations.

## Checkpoint

- `tests/scenario/test_farm_day.py::test_farm_day_scenario`
