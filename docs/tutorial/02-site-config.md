# 02 Site TOML, vehicles, and geometry

## Goal

Learn how **site toml, vehicles, and geometry** fits into robot-copilot-chat: the LLM proposes, the validator decides, and a human confirms before simulation.

## Concepts

- Typed `MissionPlan` actions are the only executable input.
- Validation is pure, deterministic, and uses full floating-point precision.
- The mock provider makes local development and CI possible without API keys.
- Loopback-only exposure and request guards reduce attack surface for this demo.

## Files

- `config/sites/demo_farm.toml`
- `config/vehicles.toml`
- `src/robot_copilot/site.py`
- `src/robot_copilot/geometry.py`
- `src/robot_copilot/vehicles.py`

## Run it

```bash
uv sync --locked
# Load the demo farm and inspect named places.
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --reload
```

## Checkpoint

- `tests/unit/test_site.py`
- `tests/unit/test_vehicles.py`

## Exercises

1. Run the checkpoint tests with `uv run --no-sync pytest <node-id> -q`.
2. Change one config value and predict which test should fail first.
3. Skim `PLAN.md` for the matching section and compare it to the code you opened.

