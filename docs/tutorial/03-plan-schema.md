# 03 Mission plan schema

## Goal

You will learn the strict Pydantic models that every provider must emit before validation runs. Actions are a discriminated union with `extra=forbid` and `strict=True`, so booleans encoded as strings or surprise fields fail fast. Chat requests are validated separately from mission plans, which keeps API bounds independent from aerial semantics.

Decline requests use their own model so providers can refuse unsafe language without fabricating motion. The validator never trusts summaries or provider prose when hashing; only typed actions matter. When you export JSON schema for tools, keep it aligned with `plan.py` because strict mode rejects coercions that older APIs might have allowed.

## Files

- `src/robot_copilot/plan.py`
- `src/robot_copilot/schemas.py`
- `src/robot_copilot/validator/__init__.py`

## Walkthrough

1. Each `goto` must choose exactly one of a named place or explicit coordinates. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
    @model_validator(mode="after")
    def _exactly_one_target(self) -> Self:
        has_place = self.place is not None
        has_xy = self.xy is not None
        if has_place == has_xy:
            raise ValueError("exactly one of place or xy required")
        return self
```

Letting both or neither target through would make spatial resolution ambiguous. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

2. The top-level `MissionPlan` bundles vehicle, display summary, and ordered actions. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
class MissionPlan(_Strict):
    vehicle: Literal["drone", "rover"]
    summary: str = Field(max_length=280)
    actions: tuple[Action, ...] = Field(min_length=1, max_length=200)
```

Summary text is capped and never enters the confirmation hash, so UI copy can differ from hashed structure. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

3. `plan_hash` mixes canonical plan JSON with site fingerprint, vehicle profile, battery percent, and validator version. Skim imports at the top of the module when a helper name in the excerpt is unfamiliar.

```python
def plan_hash(plan: MissionPlan, ctx: ValidationContext) -> str:
    payload = "|".join(
        [
            canonical_json(plan.model_dump(mode="json")),
            ctx.site.fingerprint(),
            canonical_json(ctx.vehicle.model_dump(mode="json")),
            str(ctx.battery_pct),
            VALIDATOR_VERSION,
        ]
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _schema_issues(exc: ValidationError) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err["loc"])
        params = {"location": loc, "detail": err["msg"]}
        msg, hint = explain_issue(IssueCode.SCHEMA, _action_index_from_loc(loc), params)
        issues.append(
            ValidationIssue(
                code=IssueCode.SCHEMA,
                severity="error",
                action_index=_action_index_from_loc(loc),
                params=(("location", loc), ("detail", err["msg"])),
                message=msg,
                hint=hint,
            )
        )
    return issues


def _action_index_from_loc(loc: str) -> int | None:
    parts = loc.split(".")
    for i, p in enumerate(parts):
        if p == "actions" and i + 1 < len(parts) and parts[i + 1].isdigit():
            return int(parts[i + 1])
    return None


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


def validate_raw(
    tool_args: Mapping[str, object],
    ctx: ValidationContext,
) -> tuple[MissionPlan | None, ValidationReport]:
    try:
        raw = json.dumps(tool_args, allow_nan=False)
        plan = MissionPlan.model_validate_json(raw)
    except (ValidationError, TypeError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            issues = _schema_issues(exc)
        else:
            msg, hint = explain_issue(IssueCode.SCHEMA, None, {"location": "", "detail": str(exc)})
            issues = [
                ValidationIssue(
                    code=IssueCode.SCHEMA,
                    severity="error",
                    action_index=None,
                    params=(("detail", str(exc)),),
                    message=msg,
                    hint=hint,
                )
            ]
        report = ValidationReport(
            ok=False,
            issues=tuple(sorted(issues, key=issue_sort_key)),
            resolved=None,
            plan_hash=None,
            validator_version=VALIDATOR_VERSION,
        )
        return None, report
    report = validate(plan, ctx)
    return plan, report
```

Tampering with any of those inputs breaks confirm-time revalidation even if the database row still looks valid. Scroll one screen above and below the excerpt in your editor to see private helpers and logging hooks.

## Try it

```bash
RCC_DOTENV=off .venv/bin/python -c "
from pydantic import ValidationError
from robot_copilot.plan import Goto, XY
try:
    Goto(type='goto', place='Barn', xy=XY(x_m=1,y_m=2))
except ValidationError as e:
    print(e.errors()[0]['msg'])
"
```

Expected:

```
Value error, exactly one of place or xy required
```

## Exercise

Construct a `MissionPlan` with a rover vehicle and a `takeoff` action in a REPL and note which issue code structure validation emits. When you finish, run the checkpoint pytest node to confirm your understanding matches automated expectations.

## Checkpoint

- `tests/unit/test_plan_schema.py::test_raw_json_schema_errors`
