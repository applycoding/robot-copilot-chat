from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.responses import HTMLResponse

from robot_copilot import __version__
from robot_copilot.api import build_router
from robot_copilot.geometry import SiteGeometry
from robot_copilot.llm.base import LLMProvider
from robot_copilot.llm.registry import build_provider
from robot_copilot.orchestrator import Orchestrator
from robot_copilot.redact import configure_redaction, install_redact_filter
from robot_copilot.settings import AppSettings, load_settings
from robot_copilot.site import load_site
from robot_copilot.store import Store
from robot_copilot.vehicles import load_vehicles


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

    from robot_copilot.security import RequestGuardMiddleware

    app.add_middleware(
        RequestGuardMiddleware,
        allowed_hosts=settings.allowed_hosts,
        max_body_bytes=settings.max_body_bytes,
    )

    app.state.orchestrator = orchestrator
    app.state.settings = settings
    return app


