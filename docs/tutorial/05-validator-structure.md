# 05 Validator structure and sequencing

Structure validation runs before spatial and energy checks. It enforces vehicle capabilities (rovers cannot take off), altitude and speed limits, hover bounds, action counts, and legal state transitions such as requiring takeoff before cruise altitude on drones.

Rover plans that include `takeoff` fail fast with `UNSUPPORTED_ACTION_FOR_VEHICLE`:

Hover and photo actions have their own bounds (`HOVER_TOO_LONG`, etc.). The structure pass tracks simulated flight state (`ground`, `air`, `at_home`) so illegal transitions surface as `SEQUENCE` issues. Combining structure with vehicle profiles prevents rovers from carrying altitude on goto actions even when the mock provider accidentally emits takeoff.

## Files

- `src/robot_copilot/validator/structure.py`
- `src/robot_copilot/vehicles.py`
- `tests/unit/test_structure.py`

```python
    if isinstance(action, Takeoff):
        if not is_drone:
            issues.append(
                _issue(IssueCode.UNSUPPORTED_ACTION_FOR_VEHICLE, idx, {"action": "takeoff"})
            )
        else:
            drone = veh
            assert isinstance(drone, DroneProfile)
            alt = action.altitude_m
            if alt < drone.min_altitude_m:
                issues.append(
                    _issue(
                        IssueCode.ALTITUDE_LOW,
                        idx,
                        {"altitude_m": alt, "min": drone.min_altitude_m},
                    )
                )
```

Sequence rules also ensure photos follow movement, `return_home` appears where required, and plans do not exceed `max_actions` from the vehicle profile.



This chapter ties to the integration story in `tests/scenario/farm_day.json`: replay those steps after reading so you see how validator-structure behaves inside a long conversation with repairs, declines, and confirmations. Cross-check any prose claims against `PLAN.md` criterion numbers when you are preparing a portfolio review.
## Exercise

Validate a rover plan that begins with `takeoff` at 30 m and list every issue code returned before spatial checks run.

## Checkpoint

- `tests/unit/test_structure.py::test_rover_takeoff_rejected`
