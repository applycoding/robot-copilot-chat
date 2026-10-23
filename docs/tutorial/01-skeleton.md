# 01 Application skeleton and persistence

## Goal

You are reading tutorial chapter 01 about SQLite store bootstrap in robot-copilot-chat. Chapter 01 links SQLite store bootstrap to validators, confirmation hashes, and local simulation gates. Learning note 01-1: FastAPI `create_app` wires site geometry, vehicles, orchestrator, templates, and guarded routers in a fixed order. Learning note 01-2: The store encapsulates SQLModel engines, monotonic string ids, and transactional commits for chat outcomes. Learning note 01-3: bootstrap_id_factory scans existing rows so restarted dev servers continue id sequences without collisions. Learning note 01-4: Store.from_url creates tables on boot, which keeps docker-less tutorials approachable for new contributors. Learning note 01-5: Orchestrator methods never open raw SQL; they call store helpers that enforce optimistic concurrency. Learning note 01-6: Conversation generation counters let new chat supersede stale missions awaiting confirmation. Learning note 01-7: Mission revisions retain provider metadata per attempt so audits can reconstruct model provenance. Learning note 01-8: Runs are unique per mission id, preventing double execution if a browser retries confirm. Learning note 01-9: Clock injection supports deterministic created_at fields inside unit tests for id factories. Learning note 01-10: Provider registry construction happens once per process, sharing timeouts loaded from app.toml. Learning note 01-11: Lifespan hooks close provider HTTP clients cleanly when uvicorn shuts down. Learning note 01-12: OpenAPI endpoints are disabled to reduce attack surface in classroom deployments. Learning note 01-13: Validation error handler normalizes Pydantic failures into stable JSON the UI can render. Learning note 01-14: Chat responses include kind plan, help, decline, or error so the front end can branch predictably. Learning note 01-15: Greeting messages like hello should return kind help with mission None, clearing any prior map overlay. Learning note 01-16: Static JavaScript modules import map and playback helpers without inline event handlers. Learning note 01-17: API routes live in a dedicated module included after orchestrator construction. Learning note 01-18: Next chapters load site TOML; this one focuses on persistence seams around orchestrator.chat.

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
