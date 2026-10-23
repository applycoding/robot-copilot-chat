# 11 Repair loop and provider errors

Invalid missions may enter `repairing` with a bounded attempt counter. `reserve_repair` bumps revision and attempts atomically; provider results commit new revisions and audit kinds (`repair_requested`, `validated`, `declined`, `repair_failed`). Provider transport errors call `commit_repair_failure` so missions never remain stuck in `repairing`.

Declined repairs append a `declined` audit event, matching chat declines.

`reserve_repair` rejects concurrent repairs with 409 when status or revision no longer matches. Provider errors increment attempts and return missions to `invalid` unless repair limits exhaust, in which case status becomes `repair_exhausted`. Chat during repair is serialized per conversation with asyncio locks to avoid double commits.

## Files

- `src/robot_copilot/orchestrator.py`
- `src/robot_copilot/store.py`
- `tests/api/test_repair_flow.py`

```python
        events: list[tuple[str, dict[str, object]]] = [("repair_requested", {})]
        if status == "valid":
            events.append(("validated", {}))
        elif status == "declined":
            events.append(("declined", {}))
        elif status == "repair_exhausted":
            events.append(("repair_failed", {}))
```

Farm-day covers repair success, `NOT_REPAIRABLE`, provider-error recovery, and decline after unknown-place missions.



This chapter ties to the integration story in `tests/scenario/farm_day.json`: replay those steps after reading so you see how repair-loop behaves inside a long conversation with repairs, declines, and confirmations. Cross-check any prose claims against `PLAN.md` criterion numbers when you are preparing a portfolio review.
## Exercise

Drive the pond-at-150 m mission through repair to a valid 120 m plan, then verify a second repair returns 409 `NOT_REPAIRABLE`.

## Checkpoint

- `tests/api/test_repair_provider_error.py::test_repair_provider_error_unsticks_mission`
