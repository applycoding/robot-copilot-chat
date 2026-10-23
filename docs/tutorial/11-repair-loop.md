# 11 Repair loop and provider budget

## Goal

You will follow invalid missions back through the provider with structured issue briefs and attempt accounting. The orchestrator refuses repair when status is not invalid, when CAS reservation fails, or when attempts exceed `max_repairs`. Provider errors during repair still consume attempts so missions cannot spin forever.

Repair messages include structured issue briefs rather than raw JSON both to save tokens and to keep prompts stable. Exhausted repair transitions missions to a terminal status so the UI can offer start-over language instead of spinning forever. Provider timeouts count as attempts because the spec treats unavailable models as consumed budget. Take brief notes linking each excerpt to the checkpoint test before you continue to the next chapter.

## Files

- `src/robot_copilot/orchestrator.py`
- `src/robot_copilot/store.py`
- `src/robot_copilot/llm/mock.py`

## Walkthrough

1. `repair` checks limits, reserves the attempt, then rebuilds `RepairContext`. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
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
        view = self._build_view(m3, saved_rev, ctx, report)
        return ChatResponse(
            conversation_id=m.conversation_id,
            kind="plan",
            assistant_message=assistant,
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

Returning `STALE` on reservation failure tells the UI to refresh mission JSON before retrying. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

2. Mock repair paths adjust altitude and other fields based on issue codes. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
    def _repair(self, request: ProposalRequest) -> ProviderResult:
        repair = request.repair
        assert repair is not None
        issues = repair.issues
        for iss in issues:
            if iss.code in {c.value for c in _DECLINE_ISSUES}:
                return normalize(
                    [
                        (
                            DECLINE_TOOL,
                            {
                                "reason": f"Cannot repair: {iss.message}",
                                "category": "unsupported",
                            },
                        )
                    ],
                    None,
                    "complete",
                    provider=self.name,
                    model=self.model,
                    max_args_bytes=32768,
                )

        plan_dict = copy.deepcopy(repair.previous_plan or {})
        raw_actions = plan_dict.get("actions")
        actions: list[dict[str, object]] = (
            list(raw_actions) if isinstance(raw_actions, list) else []
        )
        attempt = repair.attempt

        for iss in issues:
            code = iss.code
            idx = iss.action_index
            if code in (IssueCode.ALTITUDE_LOW.value, IssueCode.ALTITUDE_HIGH.value):
                if idx is not None and idx < len(actions):
                    a = actions[idx]
                    if a.get("type") == "takeoff" or (
                        a.get("type") == "goto" and "altitude_m" in a
                    ):
                        a["altitude_m"] = 120.0 if code == IssueCode.ALTITUDE_HIGH.value else 10.0
            elif code == IssueCode.SPEED_HIGH.value and idx is not None:
                actions[idx]["speed_mps"] = 15.0
            elif code == IssueCode.HOVER_TOO_LONG.value and idx is not None:
                actions[idx]["seconds"] = 120.0
            elif code in (
                IssueCode.UNSUPPORTED_ACTION_FOR_VEHICLE.value,
                IssueCode.ALTITUDE_ON_GROUND_VEHICLE.value,
            ):
                actions = [a for a in actions if a.get("type") not in ("takeoff", "land")]
                for a in actions:
                    if a.get("type") == "goto":
                        a.pop("altitude_m", None)
            elif code == IssueCode.MUST_END_AT_HOME.value:
                if not actions or actions[-1].get("type") != "return_home":
                    actions.append({"type": "return_home"})
            elif code in (
                IssueCode.BATTERY_INSUFFICIENT.value,
                IssueCode.RTH_RESERVE_VIOLATED.value,
                IssueCode.TOO_LONG_DISTANCE.value,
                IssueCode.TOO_LONG_DURATION.value,
            ):
                loops = _patrol_loops(normalize_name(request.user_message))
                if loops is not None:
                    new_loops = max(1, loops // (2**attempt))
                    actions = _patrol_wrapped(new_loops, request.vehicle)

        plan_dict["actions"] = actions
        return normalize(
            [(PROPOSE_TOOL, plan_dict)],
            render_repair_message(repair),
            "complete",
            provider=self.name,
            model=self.model,
            max_args_bytes=32768,
        )


def _patrol_loops(text: str) -> int | None:
    m = re.search(
        r"patrol the perimeter(?: "
        r"(\d+|once|twice|three|four|five|six|seven|eight|nine|ten) times)?",
        text,
    )
    if not m:
        return None
    token = m.group(1)
    if token is None:
        return 1
    if token.isdigit():
        return int(token)
    return _NUMBER_WORDS.get(token, 1)


def _patrol_body(loops: int) -> list[dict[str, object]]:
    body: list[dict[str, object]] = []
    for _ in range(loops):
        for idx in range(5):
            body.append({"type": "goto", "place": "Perimeter", "point_index": idx})
    return body


def _patrol_wrapped(loops: int, vehicle: str) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    if vehicle == "drone":
        actions.append({"type": "takeoff", "altitude_m": 30.0})
    actions.extend(_patrol_body(loops))
    actions.append({"type": "return_home"})
    return actions


def _inspect_place(
    place: str, alt: float | None, vehicle: str, site_summary: object
) -> list[dict[str, object]]:
    body: list[dict[str, object]] = []
    count = 1
    for p in getattr(site_summary, "places", []):
        if normalize_name(p.get("name", "")) == normalize_name(place):
            count = p.get("point_count", 1)
            break
    for idx in range(count):
        goto: dict[str, object] = {"type": "goto", "place": place, "point_index": idx}
        if alt is not None:
            goto["altitude_m"] = alt
        body.append(goto)
        if vehicle == "drone":
            body.append({"type": "hover", "seconds": 3})
        body.append({"type": "photo"})
    return body


def _photo_place(place: str, vehicle: str) -> list[dict[str, object]]:
    body: list[dict[str, object]] = [{"type": "goto", "place": place}]
    if vehicle == "drone":
        body.append({"type": "hover", "seconds": 5.0})
    body.append({"type": "photo"})
    return body


def _fly_keepout(name: str, request: ProposalRequest) -> list[dict[str, object]] | None:
    summary = request.site_summary
    keep_outs = getattr(summary, "keep_outs", [])
    for ko in keep_outs:
        if normalize_name(ko) == normalize_name(name) or normalize_name(name) in normalize_name(ko):
            return [{"type": "goto", "xy": {"x_m": -140.0, "y_m": 120.0}}]
    return None
```

Deterministic repair makes farm-day golden tests reproducible without cloud keys. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

3. Chat uses the same provider semaphore as repair to cap concurrent SDK calls. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
        self._locks: dict[str, asyncio.Lock] = {}
        self._sem = asyncio.Semaphore(settings.provider_concurrency)
```

Semaphore sizing comes from `config/app.toml` and is asserted in guard tests. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

## Try it

```bash
RCC_DOTENV=off .venv/bin/python -c "
from fastapi.testclient import TestClient
from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env
s = load_settings(env=default_settings_env(), dotenv_enabled=False)
c = TestClient(create_app(s), base_url='http://localhost')
chat = c.post('/api/chat', json={'message':'inspect north fence at 30m','vehicle':'drone','battery_pct':15}).json()
mid = chat['mission']['id']
r = c.post(f'/api/missions/{mid}/repair').json()
print(r['kind'], r['mission']['status'])
"
```

Expected after mock repair:

```
plan valid
```

## Exercise

Set `max_repairs` to zero on a mission row in a test database and confirm repair returns HTTP 409 with `repair_limit`. When you finish, run the checkpoint pytest node to confirm your understanding matches automated expectations.

## Checkpoint

- `tests/api/test_repair_provider_error.py::test_repair_provider_error_unsticks_mission`
