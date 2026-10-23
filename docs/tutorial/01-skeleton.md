# 01 Application skeleton and routing

## Goal

You will see how a single FastAPI factory assembles settings, site data, SQLite persistence, the orchestrator, templates, and API routes without hiding dependencies in globals. That composition matters because every integration test can inject a mock provider, a fixed clock, and a custom id factory while production uses real settings from disk. You will also understand why identifier generation resumes after restart when the database file survives, which Docker volumes rely on.

Routing stays in `api.py` so OpenAPI models remain the public contract while the orchestrator owns business rules. When you add a new endpoint, you should extend schemas first, then call a single orchestrator method, and only then adjust templates or static assets if the UI needs new fields. The lifespan hook closes the active provider so Anthropic, OpenAI, and Gemini clients do not leak sockets during hot reload in development. Pay attention to how `RCC_ROOT` resolves config paths when you run from Docker versus a git checkout, because misconfigured roots look like mysterious 404s on static files even though Python imports succeed.

## Files

- `src/robot_copilot/main.py`
- `src/robot_copilot/store.py`
- `src/robot_copilot/api.py`

## Walkthrough

1. Open `main.py` and study `create_app`, the only place that wires the stack together. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

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

    orchestrator = Orchestrator(prov, store, site, geometry, vehicles, settings, clock_fn)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await prov.aclose()

    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"version": __version__},
        )

    app.include_router(build_router(orchestrator, settings, site.name))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {"loc": err["loc"], "msg": err["msg"], "type": err["type"]} for err in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    from robot_copilot.security import RequestGuardMiddleware

    app.add_middleware(
        RequestGuardMiddleware,
        allowed_hosts=settings.allowed_hosts,
        max_body_bytes=settings.max_body_bytes,
    )

    app.state.orchestrator = orchestrator
    app.state.settings = settings
    return app
```

The factory disables OpenAPI URLs, mounts static assets, registers the API router, scrubs validation echoes, and installs request-guard middleware after the orchestrator exists. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

2. Next inspect `bootstrap_id_factory` in `store.py`, which scans existing rows before issuing new `id####` values. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

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

Scanning every persisted table prevents duplicate ids when a container restarts with the same SQLite file. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

3. Finally read the `/healthz` handler in `api.py`, which proves the database connection is alive. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
    @router.get("/healthz", response_model=HealthView)
    def healthz(request: Request) -> HealthView:
        from sqlmodel import Session

        store = orchestrator._store
        with Session(store._engine) as session:
            session.connection().exec_driver_sql("SELECT 1")
        return HealthView(
            status="ok",
            provider=settings.provider.value,
            model=settings.model,
            site=site_name,
            version=__version__,
            instance=settings.instance_nonce,
        )
```

Health checks return provider, model, site name, and an instance nonce so Playwright tests can detect accidental process reuse. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

## Try it

From the repo root:

```bash
RCC_DOTENV=off .venv/bin/python -c "
from fastapi.testclient import TestClient
from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env
s = load_settings(env=default_settings_env(), dotenv_enabled=False)
r = TestClient(create_app(s), base_url='http://localhost').get('/healthz')
print(r.status_code, r.json()['status'], r.json()['site'])
"
```

Expected:

```
200 ok Applycoding Demo Farm
```

## Exercise

Trace POST `/api/chat` from `api.py` into `orchestrator.chat` and list the three persistence rows created on first contact (conversation, user message, assistant message). When you finish, run the checkpoint pytest node to confirm your understanding matches automated expectations.

## Checkpoint

- `tests/api/test_id_persistence.py::test_id_factory_resumes_after_restart`
