# 10 Confirmation and execution

Confirmation is the trust boundary between planning and motion. The client posts the mission id and the plan hash it saw during validation. The orchestrator verifies status, hash equality, TTL, and re-runs the full validator against stored JSON before calling `simulate`. Any mismatch records `confirm_rejected` audit events with specific reasons.

At most one run exists per mission; repeat confirms return `NOT_CONFIRMABLE`.

`commit_confirmation` atomically marks the mission executed, stores the run, and appends audit events. TTL comparison uses the injected clock in tests (`FakeClock`) to simulate expiry without sleeping. Wrong-hash confirms never call the simulator, preventing partial side effects on tampered clients.

## Files

- `src/robot_copilot/orchestrator.py`
- `src/robot_copilot/store.py`
- `tests/api/test_confirm_guard.py`

```python
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
```

Successful confirmation commits frames, photos, and final state JSON for the playback UI.



This chapter ties to the integration story in `tests/scenario/farm_day.json`: replay those steps after reading so you see how confirmation behaves inside a long conversation with repairs, declines, and confirmations. Cross-check any prose claims against `PLAN.md` criterion numbers when you are preparing a portfolio review.
## Exercise

Confirm a valid mission, then attempt confirm again with the same hash and capture the 409 response code.

## Checkpoint

- `tests/api/test_confirm_guard.py`
