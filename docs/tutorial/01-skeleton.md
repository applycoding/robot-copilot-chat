# 01 Application skeleton and routing

The ASGI factory `create_app` wires settings, site geometry, vehicles, SQLite, the orchestrator, templates, static files, API routes, validation error handling, and request-guard middleware. Tests inject `provider`, `clock`, and `id_factory` so behavior is deterministic without editing production code.

Identifier generation must survive process restarts when the database file persists (Docker volumes). `Store.from_url` calls `bootstrap_id_factory`, which scans existing `id####` values before issuing new ones:

`create_app` also registers a custom `RequestValidationError` handler that omits echoed input fields, matching API hardening requirements. Static files are mounted at `/static` with cache-friendly paths for `app.js`, `map.js`, and `playback.js`. The HTML shell in `templates/index.html` intentionally avoids inline script to satisfy the content security policy emitted by middleware.

## Files

- `src/robot_copilot/main.py`
- `src/robot_copilot/store.py`
- `src/robot_copilot/api.py`

```python
def bootstrap_id_factory(engine: Engine) -> Callable[[], str]:
    max_n = 0
    with Session(engine) as session:
        for model in (Conversation, Message, Mission, MissionRevision, Run, AuditEvent):
            for row in session.exec(select(model)).all():
                match = _ID_RE.match(str(getattr(row, "id", "")))
                if match:
                    max_n = max(max_n, int(match.group(1)))
    counter = max_n

    def gen() -> str:
        nonlocal counter
        counter += 1
        return f"id{counter:04d}"

    return gen
```

API handlers stay thin: `api.py` delegates to `Orchestrator` and maps `ConflictError` to HTTP 409 with stable `detail.code` values.



This chapter ties to the integration story in `tests/scenario/farm_day.json`: replay those steps after reading so you see how skeleton behaves inside a long conversation with repairs, declines, and confirmations. Cross-check any prose claims against `PLAN.md` criterion numbers when you are preparing a portfolio review.
## Exercise

Trace a POST to `/api/chat` from `api.py` into `orchestrator.chat` and list the three persistence objects created for a successful plan (conversation message, mission, revision).

## Checkpoint

- `tests/api/test_id_persistence.py::test_id_factory_resumes_after_restart`
