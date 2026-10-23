# 03 Plan schema and validation entry

## Goal

You are reading tutorial chapter 03 about typed actions in robot-copilot-chat. Chapter 03 links typed actions to validators, confirmation hashes, and local simulation gates. Learning note 03-1: MissionPlan bundles vehicle, summary, and an ordered action list validated by Pydantic models. Learning note 03-2: ChatRequest carries conversation id, user text, vehicle choice, and battery percent into orchestrator.chat. Learning note 03-3: Goto actions require exactly one of place or xy, preventing ambiguous targets from reaching spatial code. Learning note 03-4: Takeoff and land actions include altitudes vetted later against vehicle profiles and structure rules. Learning note 03-5: Hover seconds must be positive floats; photo actions optionally carry human labels for playback markers. Learning note 03-6: return_home terminates sequences and triggers energy return legs independent of explicit land commands. Learning note 03-7: Raw JSON schema tests lock provider tool shapes so cloud models cannot invent new action types silently. Learning note 03-8: validate orchestrates structure, spatial, and energy passes, accumulating Issue objects with stable codes. Learning note 03-9: ValidationContext threads site, geometry, vehicle profile, and battery percentage through each pass. Learning note 03-10: Reports include ok flag, issues, resolved plan, stats, and plan_hash used by confirmation and simulation. Learning note 03-11: Decline tools capture provider refusals before a MissionPlan exists, mapping to kind decline responses. Learning note 03-12: Repair context reuses the same schema with issue briefs fed back into provider prompts. Learning note 03-13: Plan hashes cover canonical JSON so single-field edits change confirmation requirements predictably. Learning note 03-14: Structure rules encode allowed action sequences per vehicle, rejecting rover takeoff early. Learning note 03-15: Spatial rules consume resolved coordinates after place expansion and path indexing. Learning note 03-16: Energy rules estimate watt-hours using speeds and hover draws from vehicle.toml parameters. Learning note 03-17: Explanations read the same issue codes produced here, keeping UI copy aligned with validator truth. Learning note 03-18: Understanding this entrypoint clarifies why provider output still requires deterministic gatekeeping.

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
