# 04 Mock language model provider

## Goal

You will read the deterministic mock that powers local demos without API keys. Regex routes map natural phrases to tool calls, then `normalize` enforces the single-call contract shared by every real provider. Repair turns reuse the same code path with structured issue briefs so tests can predict altitude fixes and decline behavior.

Patrol phrases parse loop counts from words like twice so natural language tests stay readable in README tables. Vehicle wrapping inserts takeoff and land for drones while rovers skip altitude-bearing steps. When a phrase matches decline rules, the mock still returns a single tool call so normalization can mark the mission as non-confirmable without throwing inside the orchestrator.

## Files

- `src/robot_copilot/llm/mock.py`
- `src/robot_copilot/llm/normalize.py`
- `src/robot_copilot/llm/base.py`

## Walkthrough

1. `MockProvider.propose` branches between first chat and repair based on `request.repair`. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
    async def propose(self, request: ProposalRequest) -> ProviderResult:
        if request.repair is not None:
            return self._repair(request)
        return self._chat(request)

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

Keeping repair inside the same class guarantees golden scenarios stay stable when cloud SDKs change. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

2. Inspect routing uses canonical place names from the site summary before building actions. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
def _canonical_place(summary: SiteSummary, raw: str) -> str:
    cleaned = raw.strip().rstrip(".")
    norm = normalize_name(cleaned)
    for place in summary.places:
        if normalize_name(str(place.get("name", ""))) == norm:
            return str(place["name"])
        for alias in place.get("aliases", []):
            if normalize_name(str(alias)) == norm:
                return str(place["name"])
    return raw


_DECLINE_ISSUES = {
    IssueCode.UNKNOWN_PLACE,
    IssueCode.ENTERS_KEEP_OUT,
    IssueCode.OUTSIDE_GEOFENCE,
    IssueCode.RTH_PATH_BLOCKED,
    IssueCode.MALFORMED_OUTPUT,
}
```

Aliases in TOML therefore affect mock plans exactly the way they affect validation suggestions. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

3. `normalize` is the choke point that turns raw tool calls into `ProviderResult` kinds. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
def normalize(
    calls: Sequence[tuple[str, str | Mapping[str, object]]],
    text: str | None,
    stop: Literal["complete", "max_tokens", "refused", "blocked"],
    *,
    provider: str,
    model: str,
    max_args_bytes: int,
    max_text_chars: int = 4000,
) -> ProviderResult:
    usage = Usage()
    truncated = (text or "")[:max_text_chars] if text else None

    if stop in ("max_tokens",) and calls:
        return ProviderResult(
            kind="malformed",
            malformed_reason="incomplete",
            provider=provider,
            model=model,
            usage=usage,
        )
    if stop == "refused":
        return ProviderResult(
            kind="malformed",
            malformed_reason="refused",
            provider=provider,
            model=model,
            usage=usage,
        )
    if stop == "blocked":
        return ProviderResult(
            kind="malformed",
            malformed_reason="blocked",
            provider=provider,
            model=model,
            usage=usage,
        )
    if not calls and not text:
        return ProviderResult(
            kind="malformed",
            malformed_reason="empty",
            provider=provider,
            model=model,
            usage=usage,
        )
    if len(calls) >= 2:
        return ProviderResult(
            kind="malformed",
            malformed_reason="multiple_tool_calls",
            provider=provider,
            model=model,
            usage=usage,
        )
    if len(calls) == 1:
        name, args = calls[0]
        if name not in (PROPOSE_TOOL, DECLINE_TOOL):
            return ProviderResult(
                kind="malformed",
                malformed_reason="unknown_tool",
                provider=provider,
                model=model,
                usage=usage,
            )
        if isinstance(args, str):
            try:
                parsed = json.loads(args)
            except json.JSONDecodeError:
                return ProviderResult(
                    kind="malformed",
                    malformed_reason="bad_arguments",
                    provider=provider,
                    model=model,
                    usage=usage,
                )
        else:
            parsed = dict(args)
        raw_bytes = json.dumps(parsed, allow_nan=False).encode()
        if len(raw_bytes) > max_args_bytes:
            return ProviderResult(
                kind="malformed",
                malformed_reason="too_large",
                provider=provider,
                model=model,
                usage=usage,
            )
        if not isinstance(parsed, dict):
            return ProviderResult(
                kind="malformed",
                malformed_reason="bad_arguments",
                provider=provider,
                model=model,
                usage=usage,
            )
        try:
            if name == PROPOSE_TOOL:
                MissionPlan.model_validate_json(json.dumps(parsed, allow_nan=False))
                return ProviderResult(
                    kind="plan",
                    tool_args=parsed,
                    provider=provider,
                    model=model,
                    usage=usage,
                )
            DeclineRequest.model_validate_json(json.dumps(parsed, allow_nan=False))
            return ProviderResult(
                kind="decline",
                tool_args=parsed,
                provider=provider,
                model=model,
                usage=usage,
            )
        except Exception:
            return ProviderResult(
                kind="malformed",
                malformed_reason="bad_arguments",
                provider=provider,
                model=model,
                usage=usage,
            )
    return ProviderResult(
        kind="text",
        text=truncated or "",
        provider=provider,
        model=model,
        usage=usage,
    )
```

Refusals, blocked outputs, and multiple calls become non-confirmable malformed results before the orchestrator stores a mission. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

## Try it

```bash
RCC_DOTENV=off .venv/bin/python -c "
from fastapi.testclient import TestClient
from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env
s = load_settings(env=default_settings_env(), dotenv_enabled=False)
c = TestClient(create_app(s), base_url='http://localhost')
r = c.post('/api/chat', json={'message':'inspect the barn','vehicle':'drone','battery_pct':80})
print(r.json()['kind'], r.json()['mission']['status'])
"
```

Expected:

```
plan valid
```

## Exercise

Send `patrol the perimeter twice` with the mock and count how many `goto` actions appear before `return_home`. When you finish, run the checkpoint pytest node to confirm your understanding matches automated expectations.

## Checkpoint

- `tests/api/test_name_resolution.py::test_barn_aliases_resolve_in_mock_plans`
