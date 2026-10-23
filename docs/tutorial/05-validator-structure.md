# 05 Structure validation

## Goal

Structure validation is the first deterministic pass after a plan parses. It enforces vehicle-specific action sequences before any coordinates are computed. Rover takeoff is the classic teaching failure: ground vehicles cannot enter the flight state table used for drones. Issues carry action_index so the UI and explain templates cite the same step numbers.

Structure validation enforces allowed action sequences before any geometry computations run. validate_structure walks actions while tracking flight state for drones and drive state for rovers. Rover missions reject takeoff because ground vehicles cannot leave the terrain model used here.

Drone missions require takeoff before goto unless operating under explicit hover-only teaching examples. Land and return_home transitions reset altitude expectations checked later by spatial modules. Issue helpers attach action_index so explanations can cite step numbers understood by operators.

_issue centralizes code construction with optional params consumed by explain_issue templates. Unsupported verbs for a vehicle emit unsupported_action_for_vehicle with the offending index. Empty action lists fail fast with dedicated codes rather than confusing spatial errors.

Photo actions without prior goto may be flagged depending on vehicle and teaching policy encoded in tables. Structure rules cooperate with provider mock templates so intentionally bad plans surface in pytest. Validation short-circuits on first structural failure when configured, keeping reports easy to read.

Mission summaries do not affect structure results; only typed actions matter here. Structure issues still include stable codes exportable to repair briefs for provider prompts. Downstream spatial validation assumes structure already rejected impossible state transitions.

Teaching stacks use structure tests to show why typed plans beat free-form natural language. Rover takeoff plans demonstrate False outcomes with explicit enum values in tutorials. After editing structure tables, update unit tests and tutorial checkpoints together.

## Files

- `src/robot_copilot/validator/structure.py`
- `src/robot_copilot/validator/issues.py`
- `tests/unit/test_structure.py`

## Walkthrough

1. validate_structure is the authoritative transition table for mission actions per vehicle profile.

<!-- segment: src/robot_copilot/validator/structure.py validate_structure -->

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
```

When it returns issues, later passes may still run for diagnostics but ok stays false.

2. _issue builds Issue records with consistent param dicts used by explanation templates and repair briefs.

<!-- segment: src/robot_copilot/validator/structure.py _issue -->

```python
def _issue(
    code: IssueCode,
    action_index: int | None,
    params: dict[str, Any],
    message: str = "",
    hint: str = "",
) -> ValidationIssue:
    from robot_copilot.validator.explain import explain_issue

    msg, h = explain_issue(code, action_index, params) if not message else (message, hint)
    return ValidationIssue(
        code=code,
        severity="error",
        action_index=action_index,
        params=tuple(sorted(params.items())),
        message=msg,
        hint=h,
    )
```

Centralizing construction avoids duplicated string formatting across validator modules.
## Try it

```bash
RCC_DOTENV=off uv run --no-sync python -c "
from robot_copilot.plan import MissionPlan, Takeoff, Land
from robot_copilot.validator import validate
from robot_copilot.validator.context import ValidationContext
from robot_copilot.site import load_site
from robot_copilot.geometry import SiteGeometry
from robot_copilot.vehicles import load_vehicles
from pathlib import Path
site = load_site(Path('config/sites/demo_farm.toml'))
geom = SiteGeometry.build(site)
vehicles = load_vehicles(Path('config/vehicles.toml'))
ctx = ValidationContext(site=site, geometry=geom, vehicle=vehicles['rover'], battery_pct=80)
plan = MissionPlan(vehicle='rover', summary='bad', actions=(Takeoff(type='takeoff', altitude_m=5), Land(type='land')))
r = validate(plan, ctx)
print(r.ok, r.issues[0].code.value)
"
```

### Expected

```
False unsupported_action_for_vehicle
```

## Exercise

Name the flight state immediately after a drone takeoff according to validate_structure.

## Checkpoint

- `tests/unit/test_structure.py::test_rover_takeoff_rejected`
