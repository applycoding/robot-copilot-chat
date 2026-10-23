# 10 Confirmation and execution

## Goal

You are reading tutorial chapter 10 about plan hash CAS in robot-copilot-chat. Chapter 10 links plan hash CAS to validators, confirmation hashes, and local simulation gates. Learning note 10-1: Confirmation requires clients to POST the plan_hash shown alongside valid missions. Learning note 10-2: Orchestrator._confirm verifies mission status, hash equality, and optimistic concurrency before simulation. Learning note 10-3: Store.commit_confirmation writes runs, updates mission status, and records audit events atomically. Learning note 10-4: Wrong hashes return HTTP 409 with plan_hash_mismatch detail codes for programmatic clients. Learning note 10-5: Confirm TTL from settings retires stale missions that operators left open too long. Learning note 10-6: Double confirm attempts should fail cleanly without creating duplicate run rows. Learning note 10-7: Generation counters invalidate confirms when new chat supersedes awaiting missions. Learning note 10-8: Executed missions hide confirm buttons in the UI and freeze repair affordances. Learning note 10-9: Simulation starts only after confirmation succeeds, never directly from chat responses. Learning note 10-10: Audit trails capture operator intent even when confirmation fails due to hash drift. Learning note 10-11: Mission revisions store plan JSON snapshots used to recompute hashes for comparisons. Learning note 10-12: Browser execute flow posts confirm then initializes playback with returned frames. Learning note 10-13: CAS failures surface stale conflict codes so clients can refresh mission views. Learning note 10-14: Teaching stacks emphasize hashes because JSON pretty-printing can change without semantic edits. Learning note 10-15: Hash algorithms live in validator modules to keep confirm and simulate aligned. Learning note 10-16: Provider changes between chat and confirm should change hashes, blocking outdated confirms. Learning note 10-17: Integration tests cover wrong hash paths without needing manual UI clicking. Learning note 10-18: Portfolio discussions should mention human confirmation as authorization, not cosmetic UX.

## Files

- `src/robot_copilot/orchestrator.py`
- `src/robot_copilot/store.py`
- `tests/api/test_confirm_guard.py`

## Walkthrough

1. Orchestrator._confirm orchestrates hash checks, store CAS, and simulate invocation behind a conversation lock.

<!-- segment: src/robot_copilot/orchestrator.py Orchestrator._confirm -->

```python
    def _confirm(self, mission_id: str, phash: str) -> RunView:
        m = self._store.get_mission(mission_id)
        if m is None:
            raise KeyError(mission_id)
        if m.status != "valid":
            self._store.audit(mission_id, "confirm_rejected", {"reason": "not_confirmable"})
            raise ConflictError(ConflictCode.NOT_CONFIRMABLE, "Mission cannot be confirmed.")
        if m.plan_hash != phash:
            self._store.audit(mission_id, "confirm_rejected", {"reason": "hash"})
            raise ConflictError(ConflictCode.PLAN_HASH_MISMATCH, "Plan hash does not match.")
        if m.validated_at is None:
            raise ConflictError(ConflictCode.NOT_CONFIRMABLE, "Mission cannot be confirmed.")
        validated = datetime.fromisoformat(m.validated_at)
        if self._clock() - validated > timedelta(seconds=self._settings.confirm_ttl_s):
            self._store.audit(mission_id, "confirm_rejected", {"reason": "expired"})
            raise ConflictError(ConflictCode.CONFIRMATION_EXPIRED, "Confirmation window expired.")

        rev = self._store.get_latest_revision(mission_id)
        if rev is None or not rev.plan_json:
            raise ConflictError(ConflictCode.REVALIDATION_FAILED, "Stored plan missing.")
        plan = MissionPlan.model_validate_json(rev.plan_json)
        ctx = self._ctx(m.vehicle, m.battery_pct)  # type: ignore[arg-type]
        report = validate(plan, ctx)
        if not report.ok or report.plan_hash != phash:
            self._store.audit(mission_id, "confirm_rejected", {"reason": "revalidation"})
            raise ConflictError(ConflictCode.REVALIDATION_FAILED, "Plan no longer validates.")

        sim = simulate(report, ctx)
        run = Run(
            id=self._store._id(),
            mission_id=mission_id,
            plan_hash=phash,
            status=sim.status,
            frames_json=json.dumps([f.model_dump(mode="json") for f in sim.frames]),
            photos_json=json.dumps([p.model_dump(mode="json") for p in sim.photos]),
            final_state_json=json.dumps(sim.final_state.model_dump(mode="json")),
            created_at=self._clock().isoformat(),
        )
        ttl_cutoff = self._clock() - timedelta(seconds=self._settings.confirm_ttl_s)
        run_id = run.id
        ok = self._store.commit_confirmation(
            mission_id,
            m.revision,
            phash,
            ttl_cutoff,
            run,
            [("confirmed", {}), (sim.status, {})],
        )
        if not ok:
            raise ConflictError(ConflictCode.NOT_CONFIRMABLE, "Mission cannot be confirmed.")
        return RunView(
            id=run_id,
            mission_id=mission_id,
            status=sim.status,
            frames=list(sim.frames),
            photos=list(sim.photos),
            final_state=sim.final_state,
        )
```

ConflictError mapping ensures API layer returns consistent HTTP status codes for each failure mode.

2. Store.commit_confirmation persists run telemetry and flips mission status to executed or aborted based on simulation.

<!-- segment: src/robot_copilot/store.py Store.commit_confirmation -->

```python
    def commit_confirmation(
        self,
        mission_id: str,
        rev: int,
        plan_hash: str,
        validated_not_before: datetime,
        run: Run,
        events: list[tuple[str, dict[str, Any]]],
    ) -> bool:
        with Session(self._engine) as session:
            m = session.get(Mission, mission_id)
            if m is None or m.status != "valid" or m.revision != rev or m.plan_hash != plan_hash:
                return False
            if m.validated_at is None:
                return False
            val_at = _require_aware(datetime.fromisoformat(m.validated_at))
            if val_at < _require_aware(validated_not_before):
                return False
            m.status = "executed" if run.status == "executed" else "aborted"
            session.add(m)
            session.add(run)
            for kind, detail in events:
                self._audit(session, mission_id, kind, detail)
            try:
                session.commit()
            except Exception:
                session.rollback()
                return False
            return True
```

SQLite transactions keep runs unique per mission id even under concurrent client retries.
## Try it

```bash
RCC_DOTENV=off uv run --no-sync python -c "
from fastapi.testclient import TestClient
from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env
s = load_settings(env=default_settings_env(), dotenv_enabled=False)
c = TestClient(create_app(s), base_url='http://localhost')
chat = c.post('/api/chat', json={'message':'photo of barn','vehicle':'drone','battery_pct':80}).json()
mid = chat['mission']['id']
bad = c.post('/api/missions/' + mid + '/confirm', json={'plan_hash':'0'*64})
print(bad.status_code, bad.json()['detail']['code'])
"
```

### Expected

```
409 plan_hash_mismatch
```

## Exercise

Inspect audit events after a failed confirm and note the stored reason for hash mismatch.

## Checkpoint

- `tests/api/test_confirm_guard.py::test_wrong_hash_no_run`
