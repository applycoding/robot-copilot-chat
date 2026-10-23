# 07 Validator energy and reserves

Energy validation integrates piecewise consumption along resolved legs, subtracts watt-hours per segment, and tracks return-home reserve requirements. When projected end energy drops below the configured reserve, the validator emits `BATTERY_INSUFFICIENT` with `start_wh`, `end_wh`, and `reserve_wh` in issue params so explanations can describe projected end state rather than only starting capacity.

Starting below reserve alone is a distinct failure mode with its own message template branch in `explain.py`.

`reserve_wh` derives from vehicle `reserve_pct` times capacity, not the operator's starting percent alone. Return-home reserve violations (`RTH_RESERVE_VIOLATED`) can appear mid-plan before the summary `BATTERY_INSUFFICIENT` check. Energy numbers feed both issue messages and the stats block shown in confirmation summaries.

## Files

- `src/robot_copilot/validator/resolve.py`
- `src/robot_copilot/validator/energy.py`
- `config/vehicles.toml`

```python
    if stats.battery_end_wh < reserve:
        batt_params = {
            "pct": ctx.battery_pct,
            "start_wh": round(battery_start, 1),
            "end_wh": round(stats.battery_end_wh, 1),
            "reserve_wh": round(reserve, 1),
        }
        msg, hint = explain_issue(IssueCode.BATTERY_INSUFFICIENT, None, batt_params)
```

Farm-day step 19 (`patrol the perimeter four times` at 40% battery) is the reference mission for this failure.



This chapter ties to the integration story in `tests/scenario/farm_day.json`: replay those steps after reading so you see how validator-energy behaves inside a long conversation with repairs, declines, and confirmations. Cross-check any prose claims against `PLAN.md` criterion numbers when you are preparing a portfolio review.
## Exercise

Chat the farm-day patrol phrase at 40% battery and quote the battery issue sentence including projected end watt-hours.

## Checkpoint

- `tests/unit/test_regression_guards.py::test_battery_insufficient_includes_end_wh_param`
