# 01 Application skeleton and persistence

## Goal

FastAPI boots a single SQLite-backed application where chat, confirmation, and repair share one orchestrator and one store. This chapter follows persistence seams: how monotonic string ids survive restarts, how missions and runs relate, and why the mock provider is wired before routes go live. You will see where chat responses pick up kind plan versus kind help.

## Files

- `src/robot_copilot/main.py`
- `src/robot_copilot/store.py`
- `src/robot_copilot/orchestrator.py`
- `src/robot_copilot/api.py`

## Walkthrough

1. Id generation resumes after restarts by scanning every persisted table for the highest `idNNNN` suffix.

<!-- segment: src/robot_copilot/store.py bootstrap_id_factory -->

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

The factory closure increments a counter so new rows stay sortable during demos without UUIDs.

2. Store.from_url is the supported entry for tests and production: it builds the engine, creates schema, and injects ids.

<!-- segment: src/robot_copilot/store.py Store.from_url -->

```python
    def from_url(
        cls,
        url: str,
        clock: Callable[[], datetime],
        id_factory: Callable[[], str] | None = None,
    ) -> Store:
        engine = create_engine(url, connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(engine)
        ids = id_factory or bootstrap_id_factory(engine)
        return cls(engine, clock, ids)
```

Passing a custom id_factory is rare but useful when you need deterministic sequences in property tests.
## Try it

```bash
RCC_DOTENV=off uv run --no-sync python -c "
from fastapi.testclient import TestClient
from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env
s = load_settings(env=default_settings_env(), dotenv_enabled=False)
c = TestClient(create_app(s), base_url='http://localhost')
r = c.post('/api/chat', json={'message':'hello','vehicle':'drone','battery_pct':80}).json()
print(r['kind'], r.get('mission'))
"
```

### Expected

```
help None
```

## Exercise

Trace POST /api/chat into orchestrator.chat and list persistence rows created on first contact.

## Checkpoint

- `tests/api/test_id_persistence.py::test_id_factory_resumes_after_restart`
