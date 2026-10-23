from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from robot_copilot import __version__
from robot_copilot.orchestrator import ConflictError, Orchestrator
from robot_copilot.schemas import (
    ChatRequest,
    ChatResponse,
    ConfirmRequest,
    HealthView,
    MissionView,
    RepairRequest,
    RunView,
)
from robot_copilot.settings import AppSettings


def build_router(orchestrator: Orchestrator, settings: AppSettings, site_name: str) -> APIRouter:
    router = APIRouter()

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

    @router.get("/api/site")
    def get_site(request: Request) -> dict[str, Any]:
        site = orchestrator._site
        geom = orchestrator._geometry
        return {
            "name": site.name,
            "home": site.home,
            "geofence": site.geofence,
            "keep_outs": [
                {"name": n, "polygon": list(p.exterior.coords)} for n, p in geom.keep_outs
            ],
            "places": [
                {
                    "name": p.name,
                    "kind": p.kind,
                    "points": p.points,
                    "aliases": p.aliases,
                }
                for p in site.places
            ],
        }

    @router.post("/api/chat", response_model=ChatResponse)
    async def chat(body: ChatRequest) -> ChatResponse:
        from robot_copilot.llm.base import ProviderError

        try:
            return await orchestrator.chat(body)
        except ConflictError as exc:
            raise _conflict(exc) from exc
        except ProviderError:
            return ChatResponse(
                conversation_id=body.conversation_id or "",
                kind="error",
                assistant_message="The AI provider is unavailable; no plan was created.",
                mission=None,
            )

    @router.post("/api/missions/{mission_id}/repair", response_model=ChatResponse)
    async def repair(mission_id: str, _body: RepairRequest) -> ChatResponse:
        try:
            return await orchestrator.repair(mission_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc
        except ConflictError as exc:
            raise _conflict(exc) from exc

    @router.post("/api/missions/{mission_id}/confirm", response_model=RunView)
    async def confirm(mission_id: str, body: ConfirmRequest) -> RunView:
        try:
            return await orchestrator.confirm_and_execute(mission_id, body.plan_hash)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc
        except ConflictError as exc:
            raise _conflict(exc) from exc

    @router.get("/api/missions/{mission_id}", response_model=MissionView)
    def get_mission(mission_id: str) -> MissionView:
        try:
            return orchestrator.get_mission(mission_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc

    @router.get("/api/missions/{mission_id}/commands")
    def get_commands(mission_id: str) -> list[dict[str, Any]]:
        try:
            legs = orchestrator.get_commands(mission_id)
            return [leg.model_dump(mode="json") for leg in legs]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc
        except ConflictError as exc:
            raise _conflict(exc) from exc

    @router.get("/api/runs/{run_id}", response_model=RunView)
    def get_run(run_id: str) -> RunView:
        try:
            return orchestrator.get_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc

    return router


def _conflict(exc: ConflictError) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": exc.code.value, "message": str(exc)},
    )
