from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal, cast

from robot_copilot.geometry import SiteGeometry
from robot_copilot.llm.base import (
    ChatTurn,
    IssueBrief,
    LLMProvider,
    ProposalRequest,
    ProviderError,
    ProviderResult,
    RepairContext,
)
from robot_copilot.plan import DeclineRequest, MissionPlan
from robot_copilot.schemas import ChatRequest, ChatResponse, MissionStatus, MissionView, RunView
from robot_copilot.settings import AppSettings
from robot_copilot.sim.simulator import simulate
from robot_copilot.site import Site
from robot_copilot.store import Mission, MissionRevision, Run, Store
from robot_copilot.tools import build_site_summary, build_system_prompt, tool_specs
from robot_copilot.validator import ValidationContext, validate, validate_raw
from robot_copilot.validator.explain import describe_decline, describe_report
from robot_copilot.validator.issues import XYZ, IssueCode, Leg, ValidationIssue, ValidationReport
from robot_copilot.vehicles import DroneProfile, RoverProfile, VehicleKind


class ConflictCode(StrEnum):
    PLAN_HASH_MISMATCH = "plan_hash_mismatch"
    NOT_CONFIRMABLE = "not_confirmable"
    CONFIRMATION_EXPIRED = "confirmation_expired"
    REVALIDATION_FAILED = "revalidation_failed"
    NOT_REPAIRABLE = "not_repairable"
    REPAIR_LIMIT = "repair_limit"
    STALE = "stale"
    NO_VALID_PLAN = "no_valid_plan"


class ConflictError(Exception):
    def __init__(self, code: ConflictCode, message: str) -> None:
        self.code = code
        super().__init__(message)


class Orchestrator:
    def __init__(
        self,
        provider: LLMProvider,
        store: Store,
        site: Site,
        geometry: SiteGeometry,
        vehicles: Mapping[VehicleKind, DroneProfile | RoverProfile],
        settings: AppSettings,
        clock: Callable[[], datetime],
    ) -> None:
        self._provider = provider
        self._store = store
        self._site = site
        self._geometry = geometry
        self._vehicles = vehicles
        self._settings = settings
        self._clock = clock
        self._locks: dict[str, asyncio.Lock] = {}
        self._sem = asyncio.Semaphore(settings.provider_concurrency)

    def _ctx(self, vehicle: VehicleKind, battery_pct: int) -> ValidationContext:
        return ValidationContext(
            site=self._site,
            geometry=self._geometry,
            vehicle=self._vehicles[vehicle],
            battery_pct=battery_pct,
        )

    def _lock(self, conv_id: str) -> asyncio.Lock:
        if conv_id not in self._locks:
            self._locks[conv_id] = asyncio.Lock()
        return self._locks[conv_id]

    async def chat(self, req: ChatRequest) -> ChatResponse:
        conv_id = req.conversation_id
        if not conv_id:
            conv = self._store.create_conversation()
            conv_id = conv.id
        async with self._lock(conv_id):
            g = self._store.add_message_and_bump_generation(conv_id, "user", req.message.strip())
            self._store.supersede_open_missions(conv_id, g)

        try:
            result = await self._call_provider(req, None)
        except ProviderError:
            async with self._lock(conv_id):
                self._store.commit_chat_result(
                    conversation_id=conv_id,
                    generation=g,
                    assistant_message="The AI provider is unavailable; no plan was created.",
                    mission=None,
                    revision=None,
                    events=[],
                )
            return ChatResponse(
                conversation_id=conv_id,
                kind="error",
                assistant_message="The AI provider is unavailable; no plan was created.",
                mission=None,
            )

        async with self._lock(conv_id):
            return self._commit_chat(conv_id, g, req, result)

    async def _call_provider(
        self, req: ChatRequest, repair: RepairContext | None
    ) -> ProviderResult:
        summary = build_site_summary(self._site, self._vehicles[req.vehicle])
        prompt = build_system_prompt(summary, req.vehicle)
        history_raw = self._store.recent_turns(
            req.conversation_id or "", self._settings.history_turns
        )
        history = [
            ChatTurn(
                role=cast(
                    Literal["user", "assistant"], r if r in ("user", "assistant") else "user"
                ),
                content=c,
            )
            for r, c in history_raw
        ]
        preq = ProposalRequest(
            system_prompt=prompt,
            history=history,
            user_message=req.message.strip(),
            vehicle=req.vehicle,
            site_summary=summary,
            tools=tool_specs(),
            repair=repair,
        )
        try:
            async with self._sem:
                async with asyncio.timeout(self._settings.operation_timeout_s):
                    return await self._provider.propose(preq)
        except ProviderError:
            raise
        except TimeoutError as exc:
            raise ProviderError("timeout", "operation timed out") from exc

    def _commit_chat(
        self, conv_id: str, g: int, req: ChatRequest, result: ProviderResult
    ) -> ChatResponse:
        ctx = self._ctx(req.vehicle, req.battery_pct)
        assistant = ""
        kind = "help"
        mission_view = None

        if result.kind == "text":
            assistant = result.text or ""
            ok = self._store.commit_chat_result(
                conversation_id=conv_id,
                generation=g,
                assistant_message=assistant,
                mission=None,
                revision=None,
                events=[],
            )
            if not ok:
                raise ConflictError(ConflictCode.STALE, "Conversation changed; retry.")
            return ChatResponse(
                conversation_id=conv_id, kind="help", assistant_message=assistant, mission=None
            )

        mid = self._store._id()
        events: list[tuple[str, dict[str, object]]] = []

        if result.kind == "decline":
            decline = DeclineRequest.model_validate(result.tool_args)
            assistant = describe_decline(decline)
            kind = "decline"
            mission = Mission(
                id=mid,
                conversation_id=conv_id,
                generation=g,
                vehicle=req.vehicle,
                battery_pct=req.battery_pct,
                user_message=req.message.strip(),
                status="declined",
                repair_attempts=0,
                max_repairs=self._settings.max_repairs,
                revision=1,
            )
            rev = MissionRevision(
                id=self._store._id(),
                mission_id=mid,
                revision=1,
                attempt=0,
                provider=result.provider,
                model=result.model,
                result_kind="decline",
                decline_json=json.dumps(decline.model_dump(mode="json")),
                created_at=self._store._clock().isoformat(),
            )
            events.append(("declined", {}))
            ok = self._store.commit_chat_result(
                conversation_id=conv_id,
                generation=g,
                assistant_message=assistant,
                mission=mission,
                revision=rev,
                events=events,
            )
            if not ok:
                raise ConflictError(ConflictCode.STALE, "Conversation changed; retry.")
            mission_row = self._store.get_mission(mid)
            saved_rev = self._store.get_latest_revision(mid)
            assert mission_row is not None
            mission_view = self._build_view(mission_row, saved_rev, ctx)
            return ChatResponse(
                conversation_id=conv_id,
                kind=kind,
                assistant_message=assistant,
                mission=mission_view,
            )

        plan = None
        report = None
        if result.kind == "plan":
            plan, report = validate_raw(result.tool_args or {}, ctx)
        elif result.kind == "malformed":
            reason = result.malformed_reason or "unknown"
            report_issues = [
                ValidationIssue(
                    code=IssueCode.MALFORMED_OUTPUT,
                    severity="error",
                    action_index=None,
                    params=(("reason", reason),),
                    message=f"Model output was malformed: {reason}",
                    hint="Try rephrasing.",
                )
            ]
            from robot_copilot.validator.issues import VALIDATOR_VERSION, ValidationReport

            report = ValidationReport(
                ok=False,
                issues=tuple(report_issues),
                resolved=None,
                plan_hash=None,
                validator_version=VALIDATOR_VERSION,
            )

        status = "valid" if report and report.ok else "invalid"
        assistant = describe_report(report, self._site) if report else ""
        kind = "plan"
        mission = Mission(
            id=mid,
            conversation_id=conv_id,
            generation=g,
            vehicle=req.vehicle,
            battery_pct=req.battery_pct,
            user_message=req.message.strip(),
            status=status,
            repair_attempts=0,
            max_repairs=self._settings.max_repairs,
            revision=1,
            plan_hash=report.plan_hash if report else None,
            validated_at=self._clock().isoformat() if report and report.ok else None,
        )
        rev = MissionRevision(
            id=self._store._id(),
            mission_id=mid,
            revision=1,
            attempt=0,
            provider=result.provider,
            model=result.model,
            result_kind=result.kind,
            plan_json=json.dumps(plan.model_dump(mode="json"))
            if plan
            else json.dumps(result.tool_args or {}),
            report_json=json.dumps(report.model_dump(mode="json")) if report else None,
            created_at=self._clock().isoformat(),
        )
        events.append(("proposed", {}))
        if report and report.ok:
            events.append(("validated", {}))
        ok = self._store.commit_chat_result(
            conversation_id=conv_id,
            generation=g,
            assistant_message=assistant,
            mission=mission,
            revision=rev,
            events=events,
        )
        if not ok:
            raise ConflictError(ConflictCode.STALE, "Conversation changed; retry.")
        mission_row = self._store.get_mission(mid)
        saved_rev = self._store.get_latest_revision(mid)
        assert mission_row is not None
        mission_view = self._build_view(mission_row, saved_rev, ctx, report)
        return ChatResponse(
            conversation_id=conv_id, kind=kind, assistant_message=assistant, mission=mission_view
        )

    async def repair(self, mission_id: str) -> ChatResponse:
        m = self._store.get_mission(mission_id)
        if m is None:
            raise KeyError(mission_id)
        if m.status == "repair_exhausted" or (
            m.status == "invalid" and m.repair_attempts >= m.max_repairs
        ):
            raise ConflictError(ConflictCode.REPAIR_LIMIT, "Repair limit reached.")
        if m.status != "invalid":
            raise ConflictError(ConflictCode.NOT_REPAIRABLE, "Mission is not repairable.")

        if not self._store.reserve_repair(mission_id, m.revision, m.repair_attempts):
            raise ConflictError(ConflictCode.STALE, "Mission changed; retry.")

        m = self._store.get_mission(mission_id)
        assert m is not None
        rev_row = self._store.get_latest_revision(mission_id)
        prev_plan = json.loads(rev_row.plan_json) if rev_row and rev_row.plan_json else None
        report = json.loads(rev_row.report_json) if rev_row and rev_row.report_json else {}
        issues = [
            IssueBrief(code=i["code"], action_index=i.get("action_index"), message=i["message"])
            for i in report.get("issues", [])
        ]
        repair_ctx = RepairContext(
            attempt=m.repair_attempts,
            previous_plan=prev_plan,
            issues=issues,
        )
        chat_req = ChatRequest(
            conversation_id=m.conversation_id,
            message=m.user_message,
            vehicle=m.vehicle,  # type: ignore[arg-type]
            battery_pct=m.battery_pct,
        )
        try:
            result = await self._call_provider(chat_req, repair_ctx)
        except ProviderError as exc:
            async with self._lock(m.conversation_id):
                self._finish_repair_error(mission_id, exc)
            return ChatResponse(
                conversation_id=m.conversation_id,
                kind="error",
                assistant_message="The AI provider is unavailable; no plan was created.",
                mission=self.get_mission(mission_id),
            )

        async with self._lock(m.conversation_id):
            return self._commit_repair(m, result)

    def _finish_repair_error(self, mission_id: str, exc: ProviderError) -> None:
        m = self._store.get_mission(mission_id)
        if m is None:
            return
        status = "repair_exhausted" if m.repair_attempts >= m.max_repairs else "invalid"
        generation = self._store.get_conversation_generation(m.conversation_id)
        self._store.commit_repair_failure(
            mission_id,
            m.revision,
            m.repair_attempts,
            generation,
            status,
            {"kind": exc.kind},
        )

    def _commit_repair(self, m: Mission, result: ProviderResult) -> ChatResponse:
        ctx = self._ctx(m.vehicle, m.battery_pct)  # type: ignore[arg-type]
        conv = self._store.get_mission(m.id)
        assert conv is not None
        (self._store.recent_turns(m.conversation_id, 1))
        # get generation from conversation
        g = self._store.get_conversation_generation(m.conversation_id)

        plan = None
        report = None
        status = "invalid"
        if result.kind == "decline":
            status = "declined"
        elif result.kind == "plan":
            plan, report = validate_raw(result.tool_args or {}, ctx)
            status = "valid" if report.ok else "invalid"
        elif result.kind == "malformed" or result.kind == "text":
            status = "invalid"

        if m.repair_attempts >= m.max_repairs and status == "invalid":
            status = "repair_exhausted"

        rev = MissionRevision(
            id=self._store._id(),
            mission_id=m.id,
            revision=m.revision,
            attempt=m.repair_attempts,
            provider=result.provider,
            model=result.model,
            result_kind=result.kind,
            plan_json=json.dumps(plan.model_dump(mode="json"))
            if plan
            else rev_row.plan_json
            if (rev_row := self._store.get_latest_revision(m.id))
            else None,
            report_json=json.dumps(report.model_dump(mode="json")) if report else None,
            created_at=self._clock().isoformat(),
        )
        events: list[tuple[str, dict[str, object]]] = [("repair_requested", {})]
        if status == "valid":
            events.append(("validated", {}))
        elif status == "declined":
            events.append(("declined", {}))
        elif status == "repair_exhausted":
            events.append(("repair_failed", {}))

        ok = self._store.commit_repair(
            mission_id=m.id,
            generation=g,
            rev=m.revision,
            attempts=m.repair_attempts,
            status=status,
            plan_hash=report.plan_hash if report and report.ok else m.plan_hash,
            validated_at=self._clock() if report and report.ok else None,
            revision=rev,
            events=events,
        )
        if not ok:
            raise ConflictError(ConflictCode.STALE, "Mission changed; retry.")
        assistant = describe_report(report, self._site) if report else (result.text or "")
        m3 = self._store.get_mission(m.id)
        saved_rev = self._store.get_latest_revision(m.id)
        assert m3 is not None
        view = self._build_view(
            m3, saved_rev, ctx, report, adjustment_notice=result.adjustment_notice
        )
        assistant_msg = assistant
        if result.adjustment_notice:
            assistant_msg = f"{result.adjustment_notice}\n\n{assistant_msg}"
        return ChatResponse(
            conversation_id=m.conversation_id,
            kind="plan",
            assistant_message=assistant_msg,
            mission=view,
        )

    async def confirm_and_execute(self, mission_id: str, plan_hash: str) -> RunView:
        m = self._store.get_mission(mission_id)
        if m is None:
            raise KeyError(mission_id)
        async with self._lock(m.conversation_id):
            return self._confirm(mission_id, plan_hash)

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

    def get_mission(self, mission_id: str) -> MissionView:
        m = self._store.get_mission(mission_id)
        if m is None:
            raise KeyError(mission_id)
        rev = self._store.get_latest_revision(mission_id)
        ctx = self._ctx(m.vehicle, m.battery_pct)  # type: ignore[arg-type]
        return self._build_view(m, rev, ctx)

    def get_commands(self, mission_id: str) -> list[Leg]:
        m = self._store.get_mission(mission_id)
        if m is None:
            raise KeyError(mission_id)
        if m.status not in ("valid", "executed"):
            raise ConflictError(ConflictCode.NO_VALID_PLAN, "No valid plan available.")
        rev = self._store.get_latest_revision(mission_id)
        if not rev or not rev.plan_json:
            raise ConflictError(ConflictCode.REVALIDATION_FAILED, "Plan missing.")
        plan = MissionPlan.model_validate_json(rev.plan_json)
        ctx = self._ctx(m.vehicle, m.battery_pct)  # type: ignore[arg-type]
        report = validate(plan, ctx)
        if not report.ok or not report.resolved:
            raise ConflictError(ConflictCode.REVALIDATION_FAILED, "Plan no longer validates.")
        if m.plan_hash and report.plan_hash != m.plan_hash:
            raise ConflictError(ConflictCode.REVALIDATION_FAILED, "Plan hash changed.")
        return list(report.resolved.legs)

    def get_run(self, run_id: str) -> RunView:
        run = self._store.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        from robot_copilot.sim.telemetry import FinalState, Frame, PhotoEvent

        return RunView(
            id=run.id,
            mission_id=run.mission_id,
            status=run.status,
            frames=[Frame.model_validate(x) for x in json.loads(run.frames_json)],
            photos=[PhotoEvent.model_validate(x) for x in json.loads(run.photos_json)],
            final_state=FinalState.model_validate(json.loads(run.final_state_json)),
        )

    def _build_view(
        self,
        m: Mission,
        rev: MissionRevision | None,
        ctx: ValidationContext,
        report: ValidationReport | None = None,
        adjustment_notice: str | None = None,
    ) -> MissionView:
        plan = None
        issues: list[ValidationIssue] = []
        stats = None
        path_preview: list[XYZ] = []
        if rev and rev.plan_json:
            try:
                plan = MissionPlan.model_validate_json(rev.plan_json)
            except Exception:
                plan = None
        if report is None and rev and rev.report_json:
            from robot_copilot.validator.issues import ValidationReport

            report = ValidationReport.model_validate_json(rev.report_json)
        if report:
            issues = list(report.issues)
            if report.resolved:
                stats = report.resolved.stats
                path_preview = [leg.end for leg in report.resolved.legs if leg.kind == "move"]
        explanation = describe_report(report, self._site) if report else ""
        can_repair = m.status == "invalid" and m.repair_attempts < m.max_repairs
        expires = None
        can_confirm = m.status == "valid"
        if m.validated_at and can_confirm:
            expires = datetime.fromisoformat(m.validated_at) + timedelta(
                seconds=self._settings.confirm_ttl_s
            )
        return MissionView(
            id=m.id,
            status=MissionStatus(m.status),
            revision=m.revision,
            vehicle=m.vehicle,  # type: ignore[arg-type]
            battery_pct=m.battery_pct,
            plan=plan,
            plan_hash=m.plan_hash,
            explanation=explanation,
            adjustment_notice=adjustment_notice,
            issues=issues,
            stats=stats,
            path_preview=path_preview,
            repair_attempts=m.repair_attempts,
            max_repairs=m.max_repairs,
            can_repair=can_repair,
            can_confirm=can_confirm,
            confirm_expires_at=expires,
        )
