from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from robot_copilot.plan import DeclineRequest
from robot_copilot.site import Site, normalize_name, resolve_place
from robot_copilot.validator.issues import (
    IssueCode,
    ResolvedPlan,
    ValidationReport,
)


def _step(action_index: int | None) -> str:
    if action_index is None:
        return ""
    return f"Step {action_index + 1}: "


TEMPLATES: Final[dict[IssueCode, tuple[str, str]]] = {
    IssueCode.SCHEMA: ("Schema error at {location}: {detail}", "Fix the JSON structure."),
    IssueCode.MALFORMED_OUTPUT: (
        "Model output was malformed: {reason}",
        "Try rephrasing your request.",
    ),
    IssueCode.VEHICLE_MISMATCH: (
        "Plan vehicle {got} does not match session vehicle {expected}.",
        "Regenerate the plan for the selected vehicle.",
    ),
    IssueCode.UNSUPPORTED_ACTION_FOR_VEHICLE: (
        "{step}Action {action} is not supported for this vehicle.",
        "Remove unsupported actions or switch vehicle.",
    ),
    IssueCode.SEQUENCE: (
        "{step}Action is not allowed in the current flight state.",
        "Reorder actions.",
    ),
    IssueCode.UNKNOWN_PLACE: (
        "{step}Unknown place {place}.{suggestions}",
        "Use a listed place name.",
    ),
    IssueCode.BAD_POINT_INDEX: (
        "{step}Invalid point index; valid range is {min} to {max}.",
        "Set point_index within the valid range.",
    ),
    IssueCode.ALTITUDE_LOW: (
        "{step}Altitude {altitude_m} m is below the minimum {min} m.",
        "Increase altitude.",
    ),
    IssueCode.ALTITUDE_HIGH: (
        "{step}Altitude {altitude_m} m exceeds the maximum {max} m.",
        "Try {max} m or lower.",
    ),
    IssueCode.ALTITUDE_ON_GROUND_VEHICLE: (
        "{step}Rovers cannot use altitude {altitude_m} m.",
        "Remove altitude from rover actions.",
    ),
    IssueCode.SPEED_HIGH: (
        "{step}Speed {speed_mps} m/s exceeds the maximum {max} m/s.",
        "Reduce speed.",
    ),
    IssueCode.SPEED_NONPOSITIVE: (
        "{step}Speed must be greater than zero.",
        "Set a positive speed.",
    ),
    IssueCode.HOVER_INVALID: (
        "{step}Hover duration must be greater than zero.",
        "Increase hover time.",
    ),
    IssueCode.HOVER_TOO_LONG: (
        "{step}Hover {seconds} s exceeds the maximum {max} s.",
        "Shorten the hover.",
    ),
    IssueCode.TOO_MANY_ACTIONS: (
        "Plan has {count} actions; the maximum is {max}.",
        "Remove extra actions.",
    ),
    IssueCode.OUTSIDE_GEOFENCE: (
        "{step}Path leaves the geofence.",
        "Stay inside the site boundary.",
    ),
    IssueCode.ENTERS_KEEP_OUT: (
        "{step}Path enters keep-out zone {keep_out}.",
        "Route around the keep-out.",
    ),
    IssueCode.TOO_LONG_DISTANCE: (
        "Total distance {distance_m} m exceeds the limit {max} m.",
        "Shorten the mission.",
    ),
    IssueCode.TOO_LONG_DURATION: (
        "Total duration exceeds the limit.",
        "Shorten the mission.",
    ),
    IssueCode.BATTERY_INSUFFICIENT: (
        "Battery starts at {pct}% ({start_wh} Wh); the reserve alone is {reserve_wh} Wh.",
        "Increase battery or shorten the mission.",
    ),
    IssueCode.RTH_RESERVE_VIOLATED: (
        "{step}Not enough battery left for return-home reserve.",
        "Shorten the mission or increase battery.",
    ),
    IssueCode.RTH_PATH_BLOCKED: (
        "{step}Direct return-home path is blocked.",
        "Move to a position with a clear path home.",
    ),
    IssueCode.MUST_END_AT_HOME: (
        "Mission must end at home.",
        "Add return_home or land at home.",
    ),
}


def explain_issue(
    code: IssueCode,
    action_index: int | None,
    params: Mapping[str, object],
) -> tuple[str, str]:
    tmpl, hint_tmpl = TEMPLATES[code]
    p = dict(params)
    p["step"] = _step(action_index)
    if code == IssueCode.UNKNOWN_PLACE:
        sug = p.get("suggestions", "")
        p["suggestions"] = f" Did you mean {sug}?" if sug else ""
    try:
        message = tmpl.format(**p)
    except KeyError:
        message = tmpl
    try:
        hint = hint_tmpl.format(**p)
    except KeyError:
        hint = hint_tmpl
    return message, hint


def _fmt_dist(m: float) -> str:
    return f"{m / 1000:.2f} km"


def _fmt_dur(s: float) -> str:
    sec = round(s)
    mins, sec = divmod(sec, 60)
    if mins:
        return f"{mins} min {sec} s"
    return f"{sec} s"


def _fmt_wh(w: float) -> str:
    return f"{w:.1f} Wh"


def describe_plan(resolved: ResolvedPlan, site: Site) -> str:
    plan = resolved.plan
    stats = resolved.stats

    takeoff_txt: str | None = None
    for action in plan.actions:
        if action.type == "takeoff":
            takeoff_txt = f"Take off to {action.altitude_m:.0f} m"
            break

    visits: list[tuple[str, int, int]] = []
    current_display: str | None = None
    current_pts = 1
    current_photos = 0

    def flush() -> None:
        nonlocal current_display, current_pts, current_photos
        if current_display is not None:
            visits.append((current_display, current_pts, current_photos))
        current_display = None
        current_photos = 0

    for action in plan.actions:
        if action.type == "goto" and action.place:
            place = resolve_place(site, action.place)
            display = place.name if place else action.place
            pts = len(place.points) if place and place.kind == "path" else 1
            if current_display is None or normalize_name(current_display) != normalize_name(
                display
            ):
                flush()
                current_display = display
                current_pts = pts
        elif action.type == "photo":
            current_photos += 1
        elif action.type == "return_home":
            flush()
            break
    flush()

    parts: list[str] = []
    if takeoff_txt:
        parts.append(takeoff_txt)
    for display, pts, photos in visits:
        seg = f"visit {display}"
        if pts > 1:
            seg = f"visit {display} ({pts} points)"
        if photos:
            word = "photo" if photos == 1 else "photos"
            seg = f"{seg} taking {photos} {word}"
        parts.append(seg)
    if any(a.type == "return_home" for a in plan.actions):
        parts.append("then return home and land")

    head = ", ".join(parts)
    return (
        f"{head}. {_fmt_dist(stats.distance_m)}, {_fmt_dur(stats.duration_s)}, "
        f"uses {_fmt_wh(stats.energy_wh)} of {_fmt_wh(stats.battery_start_wh)}; "
        f"ends with {_fmt_wh(stats.battery_end_wh)} (reserve {_fmt_wh(stats.reserve_wh)})."
    )


def describe_report(report: ValidationReport, site: Site, max_issues: int = 20) -> str:
    if report.ok and report.resolved:
        return describe_plan(report.resolved, site)
    lines = [i.message for i in report.issues[:max_issues]]
    extra = len(report.issues) - max_issues
    if extra > 0:
        lines.append(f"and {extra} more")
    return " ".join(lines)


def describe_decline(decline: DeclineRequest) -> str:
    return decline.reason
