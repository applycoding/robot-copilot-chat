# 16 Extending sites, vehicles, and actions

## Goal

You will use a checklist mindset when adding a place, vehicle profile, or new action type. Every change touches schema, transition tables, resolver legs, explain templates, simulator frames, mock phrases, and pytest coverage. Skipping a layer is how portfolio demos accidentally approve unsafe motion.

Demo site consistency tests ensure README phrases still match validator outcomes after edits. When you add a vehicle, update `config/vehicles.toml`, loader tests, and mock wrapping rules together. Document the new action in tutorial checkpoints only after pytest covers schema, validator, simulator, and mock paths. Take brief notes linking each excerpt to the checkpoint test before you continue to the next chapter.

## Files

- `src/robot_copilot/plan.py`
- `src/robot_copilot/validator/structure.py`
- `src/robot_copilot/llm/mock.py`

## Walkthrough

1. New actions begin as discriminated union members in `plan.py`. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
Action = Annotated[
    Takeoff | Goto | Hover | Photo | Land | ReturnHome,
    Field(discriminator="type"),
]


class MissionPlan(_Strict):
    vehicle: Literal["drone", "rover"]
    summary: str = Field(max_length=280)
    actions: tuple[Action, ...] = Field(min_length=1, max_length=200)
```

Forgetting to update the union leaves providers unable to emit the type legally. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

2. Structure validation must learn allowed transitions for the new action. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
def validate_structure(plan: MissionPlan, ctx: ValidationContext) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    veh = ctx.vehicle
    is_drone = isinstance(veh, DroneProfile)

    if plan.vehicle != veh.kind:
        issues.append(
            _issue(IssueCode.VEHICLE_MISMATCH, None, {"expected": veh.kind, "got": plan.vehicle})
        )

    if len(plan.actions) > veh.max_actions:
        issues.append(
            _issue(
                IssueCode.TOO_MANY_ACTIONS,
                None,
                {"count": len(plan.actions), "max": veh.max_actions},
            )
        )

    state = "ground_home" if is_drone else "at_home"
    cur_alt = 0.0
    _hx, _hy = ctx.site.home

    for idx, action in enumerate(plan.actions):
        issues.extend(_check_action_structure(action, idx, ctx, state, cur_alt, is_drone))
        state, cur_alt = _transition(action, idx, ctx, state, cur_alt, is_drone, issues)

    return issues


def _check_action_structure(
    action: Action,
    idx: int,
    ctx: ValidationContext,
    state: str,
    cur_alt: float,
    is_drone: bool,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    veh = ctx.vehicle

    if isinstance(action, Takeoff):
        if not is_drone:
            issues.append(
                _issue(IssueCode.UNSUPPORTED_ACTION_FOR_VEHICLE, idx, {"action": "takeoff"})
            )
        else:
            drone = veh
            assert isinstance(drone, DroneProfile)
            alt = action.altitude_m
            if alt < drone.min_altitude_m:
                issues.append(
                    _issue(
                        IssueCode.ALTITUDE_LOW,
                        idx,
                        {"altitude_m": alt, "min": drone.min_altitude_m},
                    )
                )
            if alt > drone.max_altitude_m:
                issues.append(
                    _issue(
                        IssueCode.ALTITUDE_HIGH,
                        idx,
                        {"altitude_m": alt, "max": drone.max_altitude_m},
                    )
                )

    if isinstance(action, Land) and not is_drone:
        issues.append(_issue(IssueCode.UNSUPPORTED_ACTION_FOR_VEHICLE, idx, {"action": "land"}))

    if isinstance(action, Goto):
        if (
            not is_drone
            and action.altitude_m is not None
            and action.altitude_m not in (0, None)
            and action.altitude_m != 0
        ):
            issues.append(
                _issue(
                    IssueCode.ALTITUDE_ON_GROUND_VEHICLE,
                    idx,
                    {"altitude_m": action.altitude_m},
                )
            )
        speed = action.speed_mps if action.speed_mps is not None else veh.cruise_speed_mps
        if speed <= 0:
            issues.append(_issue(IssueCode.SPEED_NONPOSITIVE, idx, {"speed_mps": speed}))
        elif speed > veh.max_speed_mps:
            issues.append(
                _issue(IssueCode.SPEED_HIGH, idx, {"speed_mps": speed, "max": veh.max_speed_mps})
            )

        if is_drone and action.altitude_m is not None:
            drone = veh
            assert isinstance(drone, DroneProfile)
            alt = action.altitude_m
            if alt < drone.min_altitude_m:
                issues.append(
                    _issue(
                        IssueCode.ALTITUDE_LOW,
                        idx,
                        {"altitude_m": alt, "min": drone.min_altitude_m},
                    )
                )
            if alt > drone.max_altitude_m:
                issues.append(
                    _issue(
                        IssueCode.ALTITUDE_HIGH,
                        idx,
                        {"altitude_m": alt, "max": drone.max_altitude_m},
                    )
                )

        if action.place is not None:
            place = resolve_place(ctx.site, action.place)
            if place is None:
                suggestions = suggest_places(ctx.site, action.place)
                issues.append(
                    _issue(
                        IssueCode.UNKNOWN_PLACE,
                        idx,
                        {"place": action.place, "suggestions": ",".join(suggestions)},
                    )
                )
            elif place.kind == "path":
                if (
                    action.point_index is None
                    or action.point_index < 0
                    or action.point_index >= len(place.points)
                ):
                    issues.append(
                        _issue(
                            IssueCode.BAD_POINT_INDEX,
                            idx,
                            {"min": 0, "max": len(place.points) - 1},
                        )
                    )
            elif action.point_index is not None and action.point_index not in (0, None):
                if action.point_index != 0:
                    issues.append(
                        _issue(
                            IssueCode.BAD_POINT_INDEX,
                            idx,
                            {"min": 0, "max": 0},
                        )
                    )

    if isinstance(action, Hover):
        if action.seconds <= 0:
            issues.append(_issue(IssueCode.HOVER_INVALID, idx, {"seconds": action.seconds}))
        elif action.seconds > veh.max_hover_s:
            issues.append(
                _issue(
                    IssueCode.HOVER_TOO_LONG,
                    idx,
                    {"seconds": action.seconds, "max": veh.max_hover_s},
                )
            )

    return issues


def _sequence_issue(idx: int) -> ValidationIssue:
    return _issue(IssueCode.SEQUENCE, idx, {})


def _transition(
    action: Action,
    idx: int,
    ctx: ValidationContext,
    state: str,
    cur_alt: float,
    is_drone: bool,
    issues: list[ValidationIssue],
) -> tuple[str, float]:
    hx, hy = ctx.site.home

    if isinstance(action, Takeoff):
        if not is_drone:
            return state, cur_alt
        if state == "air":
            issues.append(_sequence_issue(idx))
            return state, cur_alt
        return "air", action.altitude_m

    if isinstance(action, Land):
        if not is_drone:
            return state, cur_alt
        if state != "air":
            issues.append(_sequence_issue(idx))
            return state, cur_alt
        x, y = _end_xy(action, idx, ctx, state, cur_alt)
        if math.hypot(x - hx, y - hy) <= HOME_RADIUS_M:
            return "ground_home", 0.0
        return "ground_away", 0.0

    if isinstance(action, ReturnHome):
        if is_drone:
            if state == "ground_home":
                issues.append(_sequence_issue(idx))
                return state, cur_alt
            return "ground_home", 0.0
        if state == "at_home":
            issues.append(_sequence_issue(idx))
            return state, cur_alt
        return "at_home", 0.0

    if isinstance(action, Goto):
        if is_drone and state == "ground_home":
            issues.append(_sequence_issue(idx))
            return state, cur_alt
        if not is_drone and state == "ground_home":
            issues.append(_sequence_issue(idx))
            return state, cur_alt
        x, y, alt = _resolve_target(action, ctx, cur_alt, is_drone)
        if is_drone:
            if state == "ground_away":
                issues.append(_sequence_issue(idx))
                return state, cur_alt
            return "air", alt
        if math.hypot(x - hx, y - hy) <= HOME_RADIUS_M:
            return "at_home", 0.0
        return "away", 0.0

    if isinstance(action, (Hover, Photo)):
        if is_drone:
            if state in ("ground_home", "ground_away"):
                issues.append(_sequence_issue(idx))
            return state, cur_alt
        return state, cur_alt

    return state, cur_alt


def _end_xy(
    action: Action, idx: int, ctx: ValidationContext, state: str, cur_alt: float
) -> tuple[float, float]:
    if isinstance(action, Goto):
        x, y, _ = _resolve_target(action, ctx, cur_alt, isinstance(ctx.vehicle, DroneProfile))
        return x, y
    return ctx.site.home


def _resolve_target(
    action: Goto,
    ctx: ValidationContext,
    cur_alt: float,
    is_drone: bool,
) -> tuple[float, float, float]:
    veh = ctx.vehicle
    if action.xy is not None:
        x, y = action.xy.x_m, action.xy.y_m
    else:
        place = resolve_place(ctx.site, action.place or "")
        if place is None:
            return ctx.site.home[0], ctx.site.home[1], cur_alt
        if place.kind == "path":
            pi = action.point_index or 0
            if pi < 0 or pi >= len(place.points):
                return ctx.site.home[0], ctx.site.home[1], cur_alt
            x, y = place.points[pi]
        else:
            x, y = place.points[0]
    if is_drone:
        drone = veh
        assert isinstance(drone, DroneProfile)
        alt = (
            action.altitude_m
            if action.altitude_m is not None
            else max(cur_alt, drone.default_altitude_m)
        )
    else:
        alt = 0.0
    return x, y, alt
```

Copy an existing branch and extend the state machine rather than bolting on ad hoc checks. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

3. Mock routing should recognize a phrase that exercises the action in farm-day style tests. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
    def _chat(self, request: ProposalRequest) -> ProviderResult:
        raw = request.user_message.casefold()
        text = normalize_name(request.user_message)
        vehicle = request.vehicle

        if re.search(r"\b(drop|release|spray|deliver)\b", text):
            return normalize(
                [
                    (
                        DECLINE_TOOL,
                        {"reason": "Unsupported payload action", "category": "unsupported"},
                    )
                ],
                None,
                "complete",
                provider=self.name,
                model=self.model,
                max_args_bytes=32768,
            )

        loops = _patrol_loops(text)
        if loops is not None:
            body = _patrol_body(loops)
            return self._wrap_plan(body, vehicle, "Patrol perimeter")

        m = re.search(
            r"\b(inspect|check|survey)\s+the\s+(.+?)(?:\s+at\s+(\d+(?:\.\d+)?)\s*m)?$",
            text,
        )
        if m:
            place = m.group(2).strip()
            alt = float(m.group(3)) if m.group(3) else None
            place = _canonical_place(request.site_summary, place)
            body = _inspect_place(place, alt, vehicle, request.site_summary)
            return self._wrap_plan(body, vehicle, f"Inspect {place}", rover_alt=alt)

        m = re.search(r"\b(take a )?(photo|picture) of (?:the )?(.+)$", text)
        if m:
            place = _canonical_place(request.site_summary, m.group(3).strip())
            body = _photo_place(place, vehicle)
            return self._wrap_plan(body, vehicle, f"Photo of {place}")

        m = re.search(r"\bhover (over|at) the (.+?) for (\d+(?:\.\d+)?)\s*s", text)
        if m:
            place = _canonical_place(request.site_summary, m.group(2).strip())
            seconds = float(m.group(3))
            body = [{"type": "goto", "place": place}, {"type": "hover", "seconds": seconds}]
            return self._wrap_plan(body, vehicle, f"Hover at {place}")

        m = re.search(r"\bfly over the (.+)$", text)
        if m:
            ko = m.group(1).strip()
            ko_body = _fly_keepout(ko, request)
            if ko_body is None:
                ko_body = [{"type": "goto", "place": ko}]
            return self._wrap_plan(ko_body, vehicle, f"Fly over {ko}")

        m = re.search(r"\b(fly|go|drive) to (?:the )?(.+)$", raw)
        if m:
            rest = m.group(2).strip()
            speed = None
            alt = None
            sm = re.search(r" at (\d+(?:\.\d+)?) m/s$", rest)
            if sm:
                speed = float(sm.group(1))
                rest = rest[: sm.start()].strip()
            am = re.search(r" at (\d+(?:\.\d+)?) m$", rest)
            if am:
                alt = float(am.group(1))
                rest = rest[: am.start()].strip()
            place = _canonical_place(request.site_summary, rest)
            goto: dict[str, object] = {"type": "goto", "place": place}
            if alt is not None:
                goto["altitude_m"] = alt
            if speed is not None:
                goto["speed_mps"] = speed
            body = [goto]
            if vehicle == "drone":
                body.append({"type": "hover", "seconds": 5})
            return self._wrap_plan(body, vehicle, f"Go to {place}", rover_alt=alt)

        help_text = (
            "Try: inspect the north fence; patrol the perimeter twice; "
            "take a photo of the barn; hover over the pond for 30 s."
        )
        return normalize(
            [], help_text, "complete", provider=self.name, model=self.model, max_args_bytes=32768
        )

    def _wrap_plan(
        self,
        body: list[dict[str, object]],
        vehicle: str,
        summary: str,
        *,
        rover_alt: float | None = None,
    ) -> ProviderResult:
        actions: list[dict[str, object]] = []
        if vehicle == "drone":
            actions.append({"type": "takeoff", "altitude_m": 30.0})
        elif vehicle == "rover" and rover_alt is not None:
            actions.append({"type": "takeoff", "altitude_m": rover_alt})
        actions.extend(body)
        actions.append({"type": "return_home"})
        plan = {"vehicle": vehicle, "summary": summary, "actions": actions}
        return normalize(
            [(PROPOSE_TOOL, plan)],
            None,
            "complete",
            provider=self.name,
            model=self.model,
            max_args_bytes=32768,
        )

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

Without mock coverage, CI never exercises the UI path for your feature. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

## Try it

```bash
RCC_DOTENV=off .venv/bin/python -m pytest tests/unit/test_demo_site_consistency.py -q --no-header
```

Expected:

```
1 passed
```

## Exercise

Add a dummy alias to `demo_farm.toml`, run site consistency tests, then revert the alias. When you finish, run the checkpoint pytest node to confirm your understanding matches automated expectations.

## Checkpoint

- `tests/unit/test_mock_provider.py::test_inspect_north_fence`
