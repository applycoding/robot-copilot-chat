# 10 Confirmation, store, and concurrency

## Goal

You will trace how missions move from valid to executed under per-conversation locks and revision compare-and-swap rules. SQLite stores plans, reports, runs, and audit events with UTC timestamps. Confirm rejects stale hashes, expired TTLs, and plans that fail revalidation against the current site and battery context.

Mission revisions store provider metadata per attempt so audits can reconstruct which model proposed a plan. Runs are unique per mission id, preventing double execution if a client retries confirm. Generation counters on conversations let the store supersede open missions when users send new chat while another plan awaits confirmation. Take brief notes linking each excerpt to the checkpoint test before you continue to the next chapter.

## Files

- `src/robot_copilot/store.py`
- `src/robot_copilot/orchestrator.py`
- `src/robot_copilot/schemas.py`

## Walkthrough

1. `reserve_repair` increments revision and repair attempts before any provider I/O. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
    def reserve_repair(self, mission_id: str, rev: int, attempts: int) -> bool:
        with Session(self._engine) as session:
            m = session.get(Mission, mission_id)
            if m is None:
                return False
            if m.status != "invalid" or m.revision != rev or m.repair_attempts != attempts:
                return False
            m.status = "repairing"
            m.revision = rev + 1
            m.repair_attempts = attempts + 1
            session.add(m)
            session.commit()
            return True

    def commit_repair_failure(
        self,
        mission_id: str,
        rev: int,
        attempts: int,
        generation: int,
        status: str,
        detail: dict[str, Any],
    ) -> bool:
        with Session(self._engine) as session:
            m = session.get(Mission, mission_id)
            conv = session.get(Conversation, m.conversation_id if m else "")
            if (
                m is None
                or conv is None
                or conv.generation != generation
                or m.status != "repairing"
                or m.revision != rev
                or m.repair_attempts != attempts
            ):
                return False
            m.status = status
            session.add(m)
            self._audit(session, mission_id, "provider_error", detail)
            session.commit()
            return True

    def commit_repair(
        self,
        *,
        mission_id: str,
        generation: int,
        rev: int,
        attempts: int,
        status: str,
        plan_hash: str | None,
        validated_at: datetime | None,
        revision: MissionRevision,
        events: list[tuple[str, dict[str, Any]]],
    ) -> bool:
        with Session(self._engine) as session:
            m = session.get(Mission, mission_id)
            conv = session.get(Conversation, m.conversation_id if m else "")
            if (
                m is None
                or conv is None
                or conv.generation != generation
                or m.status != "repairing"
                or m.revision != rev
                or m.repair_attempts != attempts
            ):
                return False
            m.status = status
            m.plan_hash = plan_hash
            m.validated_at = _iso(validated_at) if validated_at else None
            session.add(m)
            session.add(revision)
            for kind, detail in events:
                self._audit(session, mission_id, kind, detail)
            session.commit()
            return True

    def commit_chat_result(
        self,
        *,
        conversation_id: str,
        generation: int,
        assistant_message: str | None,
        mission: Mission | None,
        revision: MissionRevision | None,
        events: list[tuple[str, dict[str, Any]]],
    ) -> bool:
        with Session(self._engine) as session:
            conv = session.get(Conversation, conversation_id)
            if conv is None or conv.generation != generation:
                self._audit_stale(session, mission.id if mission else None)
                return False
            if assistant_message:
                session.add(
                    Message(
                        id=self._id(),
                        conversation_id=conversation_id,
                        role="assistant",
                        content=assistant_message,
                        created_at=_iso(self._clock()),
                    )
                )
            if mission and revision:
                session.add(mission)
                session.add(revision)
                for kind, detail in events:
                    self._audit(session, mission.id, kind, detail)
            session.commit()
            return True

    def commit_confirmation(
        self,
        mission_id: str,
        rev: int,
        plan_hash: str,
        validated_not_before: datetime,
        run: Run,
        events: list[tuple[str, dict[str, Any]]],
    ) -> bool:
        with Session(self._engine) as session:
            m = session.get(Mission, mission_id)
            if m is None or m.status != "valid" or m.revision != rev or m.plan_hash != plan_hash:
                return False
            if m.validated_at is None:
                return False
            val_at = _require_aware(datetime.fromisoformat(m.validated_at))
            if val_at < _require_aware(validated_not_before):
                return False
            m.status = "executed" if run.status == "executed" else "aborted"
            session.add(m)
            session.add(run)
            for kind, detail in events:
                self._audit(session, mission_id, kind, detail)
            try:
                session.commit()
            except Exception:
                session.rollback()
                return False
            return True

    def get_conversation_generation(self, conversation_id: str) -> int:
        with Session(self._engine) as session:
            conv = session.get(Conversation, conversation_id)
            return conv.generation if conv is not None else 0

    def audit(self, mission_id: str | None, kind: str, detail: dict[str, Any]) -> None:
        with Session(self._engine) as session:
            self._audit(session, mission_id, kind, detail)
            session.commit()

    def _audit(
        self, session: Session, mission_id: str | None, kind: str, detail: dict[str, Any]
    ) -> None:
        session.add(
            AuditEvent(
                id=self._id(),
                mission_id=mission_id,
                kind=kind,
                detail_json=json.dumps(redact_obj(detail)),
                at=_iso(self._clock()),
            )
        )

    def _audit_stale(self, session: Session, mission_id: str | None) -> None:
        self._audit(session, mission_id, "stale_discarded", {})

    def get_mission(self, mission_id: str) -> Mission | None:
        with Session(self._engine) as session:
            m = session.get(Mission, mission_id)
            if m is not None:
                session.expunge(m)
            return m

    def get_latest_revision(self, mission_id: str) -> MissionRevision | None:
        with Session(self._engine) as session:
            revs = session.exec(
                select(MissionRevision)
                .where(MissionRevision.mission_id == mission_id)
                .order_by(MissionRevision.revision.desc())  # type: ignore[attr-defined]
            ).all()
            if not revs:
                return None
            rev = revs[0]
            session.expunge(rev)
            return rev

    def get_run(self, run_id: str) -> Run | None:
        with Session(self._engine) as session:
            return session.get(Run, run_id)

    def get_run_for_mission(self, mission_id: str) -> Run | None:
        with Session(self._engine) as session:
            runs = session.exec(select(Run).where(Run.mission_id == mission_id)).all()
            return runs[0] if runs else None

    def list_audit_events(self) -> list[AuditEvent]:
        with Session(self._engine) as session:
            return list(session.exec(select(AuditEvent).order_by(AuditEvent.at)).all())
```

Reserving first prevents double repair calls from exhausting the budget twice. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

2. `_confirm` re-loads the stored plan JSON and validates before simulation. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
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
            issues=issues,
            stats=stats,
            path_preview=path_preview,
            repair_attempts=m.repair_attempts,
            max_repairs=m.max_repairs,
            can_repair=can_repair,
            can_confirm=can_confirm,
            confirm_expires_at=expires,
        )
```

Hash equality alone is insufficient if TOML or vehicle files changed since validation. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

3. Orchestrator acquires a per-conversation `asyncio.Lock` around confirm. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
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
            issues=issues,
            stats=stats,
            path_preview=path_preview,
            repair_attempts=m.repair_attempts,
            max_repairs=m.max_repairs,
            can_repair=can_repair,
            can_confirm=can_confirm,
            confirm_expires_at=expires,
        )
```

Parallel confirm and chat requests therefore serialize per thread, not globally. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

## Try it

```bash
RCC_DOTENV=off .venv/bin/python -c "
from fastapi.testclient import TestClient
from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env
s = load_settings(env=default_settings_env(), dotenv_enabled=False)
c = TestClient(create_app(s), base_url='http://localhost')
chat = c.post('/api/chat', json={'message':'photo of barn','vehicle':'drone','battery_pct':80}).json()
bad = c.post(f"/api/missions/{chat['mission']['id']}/confirm", json={'plan_hash':'deadbeef'}).status_code
print(bad)
"
```

Expected:

```
409
```

## Exercise

Read audit events after a failed confirm and list which `reason` field is stored for a hash mismatch. When you finish, run the checkpoint pytest node to confirm your understanding matches automated expectations.

## Checkpoint

- `tests/api/test_confirm_guard.py::test_wrong_hash_no_run`
