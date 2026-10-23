# 03 Mission plan schema

Executable input is always a `MissionPlan`: a vehicle, a short summary string (display only), and an ordered action list. Pydantic models use `extra=forbid` and strict typing so provider JSON cannot smuggle unknown keys.

Each `goto` must target exactly one of `place` or `xy`:

`MissionPlan.summary` is capped in length and never participates in confirmation hashing. Hashing uses canonical JSON over the plan, vehicle profile, site fingerprint, and validator version so tampering or vehicle switches invalidate stored hashes. The validator entrypoint `validate()` returns a `ValidationReport` with optional `ResolvedPlan` legs used by both the simulator and map preview endpoints.

## Files

- `src/robot_copilot/plan.py`
- `src/robot_copilot/schemas.py`
- `src/robot_copilot/validator/__init__.py`

```python
    @model_validator(mode="after")
    def _exactly_one_target(self) -> Self:
        has_place = self.place is not None
        has_xy = self.xy is not None
        if has_place == has_xy:
            raise ValueError("exactly one of place or xy required")
        return self
```

Chat requests are validated separately in `schemas.py` (vehicle enum, battery percent bounds, stripped non-empty message). Whitespace-only chat returns HTTP 422 without echoing the raw input.



This chapter ties to the integration story in `tests/scenario/farm_day.json`: replay those steps after reading so you see how plan-schema behaves inside a long conversation with repairs, declines, and confirmations. Cross-check any prose claims against `PLAN.md` criterion numbers when you are preparing a portfolio review.
## Exercise

In a REPL, construct a `Goto` with both `place` and `xy` set and observe the validation error before the plan reaches the spatial stage.

## Checkpoint

- `tests/unit/test_plan_schema.py`
