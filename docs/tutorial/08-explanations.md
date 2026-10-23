# 08 Human-readable explanations

## Goal

You will map machine issue codes to stable sentences and hints for chat, repair, and confirmation summaries. Templates live beside sorting metadata so translators could swap wording without touching geometry math. Plan descriptions compress resolved legs into a single assistant line with rounded stats for display only.

Hints are short on purpose; the chat UI shows messages while repair prompts include codes and params. Decline descriptions use a separate template path so unsupported payload language reads differently from validator errors. Rounding for display happens only inside describe helpers, never inside stored reports, which keeps simulator inputs aligned with validation math.

## Files

- `src/robot_copilot/validator/explain.py`
- `src/robot_copilot/validator/issues.py`
- `src/robot_copilot/orchestrator.py`

## Walkthrough

1. The `TEMPLATES` table pairs message patterns with hints for every `IssueCode`. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
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
```

Params such as `{place}` are filled from sorted issue tuples so ordering stays deterministic. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

2. `describe_plan` walks resolved actions to build the North Fence style summary string. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
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
        verb = "Visit" if plan.vehicle == "rover" else "visit"
        seg = f"{verb} {display}"
        if pts > 1:
            seg = f"{verb} {display} ({pts} points)"
        if photos:
            word = "photo" if photos == 1 else "photos"
            seg = f"{seg} taking {photos} {word}"
        parts.append(seg)
    if any(a.type == "return_home" for a in plan.actions):
        if plan.vehicle == "rover":
            parts.append("then return to the dock and park")
        else:
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
```

Grouping consecutive gotos to the same place keeps photo counts readable in the chat pane. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

3. Orchestrator imports `describe_report` when formatting validation results for the client. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
from robot_copilot.validator.explain import describe_decline, describe_report
from robot_copilot.validator.issues import XYZ, IssueCode, Leg, ValidationIssue, ValidationReport
```

Keeping formatting out of FastAPI routes prevents duplicate copy when CLI tools appear later. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

## Try it

```bash
RCC_DOTENV=off .venv/bin/python -c "
from robot_copilot.validator.explain import explain_issue
from robot_copilot.validator.issues import IssueCode
msg, hint = explain_issue(IssueCode.ALTITUDE_HIGH, 0, {'altitude_m': 120, 'max': 80})
print(msg)
print(hint)
"
```

Expected:

```
Step 1: Altitude 120 m exceeds the maximum 80 m.
Try 80 m or lower.
```

## Exercise

Add a temporary template entry for a fake issue in a branch and confirm tests fail until you remove it. When you finish, run the checkpoint pytest node to confirm your understanding matches automated expectations.

## Checkpoint

- `tests/unit/test_explain.py::test_describe_plan_north_fence`
