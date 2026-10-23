# Project overview and safety model

## Goal

Work through **project overview and safety model** with the real robot-copilot-chat sources open beside this page.

## Concepts

- Typed plans, validator authority, and human confirmation before simulation.
- Chapter focus: project overview.

## Files

- `src/robot_copilot/main.py`
- `PLAN.md` (normative behavior)

## Run it

```bash
uv sync --locked
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --host 127.0.0.1 --port 8000
```


Robot Copilot Chat is a teaching stack where a language model **proposes** typed mission plans, a deterministic validator **accepts or rejects** them, and a human **confirms** before a local simulator runs. Nothing in the default configuration talks to a real aircraft or cloud LLM unless you opt in.

The safety story is layered. Network exposure is loopback-only with a request guard that enforces JSON POST bodies, size limits, host allowlists, and security headers. Secrets never reach audit logs thanks to redaction filters. Confirmation binds to a cryptographic plan hash and a time-to-live so stale plans cannot be executed after edits.

The FastAPI factory wires site geometry, vehicles, SQLite persistence, and the orchestrator:

```python

def create_app(
    settings: AppSettings | None = None,
    *,
    provider: LLMProvider | None = None,
    clock: Callable[[], datetime] | None = None,
    id_factory: Callable[[], str] | None = None,
) -> FastAPI:
    settings = settings or load_settings(dotenv_enabled=True)
    site = load_site(settings.site_path)
    vehicles = load_vehicles(settings.vehicles_path)
    geometry = SiteGeometry.build(site)

    db_path = settings.db_url.replace("sqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    clock_fn = clock or (lambda: datetime.now(tz=UTC))
    store = Store.from_url(settings.db_url, clock_fn, id_factory)
    prov = provider or build_provider(settings)
    configure_redaction(settings.api_key)
    install_redact_filter()

```

## Exercise

Skim `config/sites/demo_farm.toml` and list three named places and one keep-out zone. Note how margins are expressed separately for the geofence and each keep-out.

## Checkpoint

```bash
uv run --no-sync pytest tests/api/test_healthz.py::test_healthz -q
```
## Exercises

Apply the checkpoint below, then read on.

## What to notice in the codebase

Keep a scratch log while you work: file paths, function names, and the pytest node ids you ran. When something surprises you (for example a 409 conflict or a clipped map polyline), capture the HTTP status, mission status, and audit kinds from SQLite. The tutorial checkpoints are intentionally narrow so you can run them quickly, but the real learning comes from comparing your local traces with the farm-day golden audit sequence and the validator issue templates in `explain.py`. If you change behavior, update both tests and the matching tutorial chapter so the next reader inherits an accurate story.

Re-run `scripts/build_tutorials.py` after editing cited excerpts so line numbers stay honest, or update the script literals when you move code. Pair each chapter with one manual UI action (send a chat, repair once, confirm) so you see the same statuses the API tests assert.
