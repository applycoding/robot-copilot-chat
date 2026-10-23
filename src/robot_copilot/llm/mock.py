from __future__ import annotations

import copy
import re

from robot_copilot.llm.base import ProposalRequest, ProviderResult, render_repair_message
from robot_copilot.llm.normalize import normalize
from robot_copilot.site import normalize_name
from robot_copilot.tools import DECLINE_TOOL, PROPOSE_TOOL, SiteSummary
from robot_copilot.validator.issues import IssueCode

_NUMBER_WORDS = {
    "once": 1,
    "twice": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


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


class MockProvider:
    name = "mock"

    def __init__(self, model: str) -> None:
        self.model = model

    async def aclose(self) -> None:
        return None

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
