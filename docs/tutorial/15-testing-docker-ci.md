# 15 Test pyramid and golden scenario

## Goal

Learn how **test pyramid and golden scenario** fits into robot-copilot-chat: the LLM proposes, the validator decides, and a human confirms before simulation.

## Concepts

- Typed `MissionPlan` actions are the only executable input.
- Validation is pure, deterministic, and uses full floating-point precision.
- The mock provider makes local development and CI possible without API keys.
- Loopback-only exposure and request guards reduce attack surface for this demo.

## Files

- `tests/conftest.py`
- `tests/scenario/test_farm_day.py`
- `tests/property/test_validator_invariants.py`
- `.github/workflows/ci.yml`
- `Dockerfile`

## Run it

```bash
uv sync --locked
# Run the farm day scenario locally.
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --reload
```

## Checkpoint

- `tests/scenario/test_farm_day.py::test_farm_day_scenario`
- `tests/repo/test_ci_pins.py`
- `tests/test_conftest_self.py::test_scrub_env_strips_secrets_and_proxy`

## Exercises

1. Run the checkpoint tests with `uv run --no-sync pytest <node-id> -q`.
2. Change one config value and predict which test should fail first.
3. Skim `PLAN.md` for the matching section and compare it to the code you opened.

