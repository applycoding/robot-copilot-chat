# 08 Human-readable explanations

## Goal

You are reading tutorial chapter 08 about issue templates and plan copy in robot-copilot-chat. Chapter 08 links issue templates and plan copy to validators, confirmation hashes, and local simulation gates. Learning note 08-1: explain_issue maps IssueCode values to operator sentences and short remediation hints. Learning note 08-2: Templates use Python format placeholders filled from validator param dicts per issue instance. Learning note 08-3: Step prefixes derive from action_index so multi-step plans read naturally in the UI. Learning note 08-4: describe_plan composes visit sentences, takeoff lines, and statistics into confirmation summaries. Learning note 08-5: _plan_visit_segments groups gotos and photos per place for readable visit summaries. Learning note 08-6: Distance, duration, and energy appear with consistent unit formatting helpers. Learning note 08-7: Rover copy uses dock language while drone copy mentions landing at home. Learning note 08-8: describe_report falls back to issue messages when plans are not ok, truncating long lists. Learning note 08-9: describe_decline converts provider decline tools into chat-friendly sentences. Learning note 08-10: Explanations never leak secrets; they consume already redacted issue messages only. Learning note 08-11: North Fence describe_plan tests lock phrasing used in browser confirmation dialogs. Learning note 08-12: Unknown place templates optionally append suggestion clauses when params include aliases. Learning note 08-13: Battery insufficient templates can mention ending watt-hours when params provide end_wh. Learning note 08-14: Explanation modules stay free of FastAPI imports so unit tests remain lightweight. Learning note 08-15: Orchestrator stores explanation strings on mission views returned to the browser. Learning note 08-16: Repair prompts include issue briefs distilled from the same codes templates understand. Learning note 08-17: Changing IssueCode enums requires updating templates and pytest snapshots together. Learning note 08-18: Readable copy is part of safety culture; operators should not read raw JSON in modals.

## Files

- `src/robot_copilot/validator/explain.py`
- `src/robot_copilot/validator/issues.py`
- `tests/unit/test_explain.py`

## Walkthrough

1. explain_issue selects template pairs, formats messages, and returns hint strings for UI tooltips.

<!-- segment: src/robot_copilot/validator/explain.py explain_issue -->

```python
def explain_issue(
    code: IssueCode,
    action_index: int | None,
    params: Mapping[str, object],
) -> tuple[str, str]:
    tmpl, hint_tmpl = TEMPLATES[code]
    p = dict(params)
    if code == IssueCode.BATTERY_INSUFFICIENT and "end_wh" not in p:
        tmpl = "Battery at {pct}% ({start_wh} Wh) is below the required {reserve_wh} Wh reserve."
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
```

KeyError guards keep explanations resilient when params omit optional formatting fields.

2. describe_plan turns resolved stats into a single paragraph suitable for confirm dialogs and audit logs.

<!-- segment: src/robot_copilot/validator/explain.py describe_plan -->

```python
def describe_plan(resolved: ResolvedPlan, site: Site) -> str:
    plan = resolved.plan
    stats = resolved.stats

    takeoff_txt: str | None = None
    for action in plan.actions:
        if action.type == "takeoff":
            takeoff_txt = f"Take off to {action.altitude_m:.0f} m"
            break

    visits = _plan_visit_segments(plan, site)

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
```

Visit aggregation collapses repeated gotos to the same place into one readable clause.
## Try it

```bash
RCC_DOTENV=off uv run --no-sync python -c "
from robot_copilot.validator.explain import explain_issue
from robot_copilot.validator.issues import IssueCode
msg, hint = explain_issue(IssueCode.ALTITUDE_HIGH, 0, {'altitude_m': 120, 'max': 80})
print(msg)
print(hint)
"
```

### Expected

```
Step 1: Altitude 120 m exceeds the maximum 80 m.
Try 80 m or lower.
```

## Exercise

Add a fake IssueCode template on a branch and observe pytest failures until removed.

## Checkpoint

- `tests/unit/test_explain.py::test_describe_plan_north_fence`
