# 03 Plan schema and validation entry

## Goal

Mission plans are typed Pydantic models, not loose JSON blobs. This chapter connects HTTP ChatRequest bodies to validate, the single entry for structure, spatial, and energy passes. You will see why mutually exclusive fields like place versus xy are rejected at parse time and how issue codes stay stable for explanations and repair briefs.

## Files

- `src/robot_copilot/schemas.py`
- `src/robot_copilot/plan.py`
- `src/robot_copilot/validator/__init__.py`
- `tests/unit/test_plan_schema.py`

## Walkthrough

1. ChatRequest is the HTTP-facing contract mirroring POST /api/chat bodies validated before orchestrator work.

<!-- segment: src/robot_copilot/schemas.py ChatRequest -->

```python
class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=2000)
    vehicle: VehicleKind = "drone"
    battery_pct: int = Field(default=100, ge=1, le=100)

    @field_validator("message")
    @classmethod
    def _strip_message(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("message must not be empty or whitespace only")
        return s
```

Optional conversation_id lets browsers continue threads while generation counters protect against stale writes.

2. validate is the single front door for deterministic checks; orchestrator never reimplements geometry math inline.

<!-- segment: src/robot_copilot/validator/__init__.py validate -->

```python
def validate(plan: MissionPlan, ctx: ValidationContext) -> ValidationReport:
    issues = validate_structure(plan, ctx)
    if issues:
        issues_sorted = tuple(sorted(issues, key=issue_sort_key))
        return ValidationReport(
            ok=False,
            issues=issues_sorted,
            resolved=None,
            plan_hash=plan_hash(plan, ctx),
            validator_version=VALIDATOR_VERSION,
        )

    resolved = build_resolved(plan, ctx)
    end_state = final_state_after_plan(plan, ctx)
    issues.extend(check_spatial_and_energy(resolved, ctx, end_state))
    issues_sorted = tuple(sorted(issues, key=issue_sort_key))
    ok = not any(i.severity == "error" for i in issues_sorted)
    return ValidationReport(
        ok=ok,
        issues=issues_sorted,
        resolved=resolved if ok else None,
        plan_hash=plan_hash(plan, ctx),
        validator_version=VALIDATOR_VERSION,
    )
```

Downstream simulator and explanation modules consume ValidationReport objects emitted here.
## Try it

```bash
RCC_DOTENV=off uv run --no-sync python -c "
from pydantic import ValidationError
from robot_copilot.plan import Goto, XY
try:
    Goto(type='goto', place='Barn', xy=XY(x_m=1,y_m=2))
except ValidationError as e:
    print(e.errors()[0]['msg'])
"
```

### Expected

```
Value error, exactly one of place or xy required
```

## Exercise

Build a rover MissionPlan containing takeoff in a REPL and note the structure issue code.

## Checkpoint

- `tests/unit/test_plan_schema.py::test_raw_json_schema_errors`
