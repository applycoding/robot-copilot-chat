# 16 Adding sites, vehicles, and actions

## Goal

Learn how **adding sites, vehicles, and actions** fits into robot-copilot-chat: the LLM proposes, the validator decides, and a human confirms before simulation.

## Concepts

- Typed `MissionPlan` actions are the only executable input.
- Validation is pure, deterministic, and uses full floating-point precision.
- The mock provider makes local development and CI possible without API keys.
- Loopback-only exposure and request guards reduce attack surface for this demo.

## Files

- `config/sites/demo_farm.toml`
- `src/robot_copilot/plan.py`
- `src/robot_copilot/validator/structure.py`
- `src/robot_copilot/llm/mock.py`

## Run it

```bash
uv sync --locked
# Add a place and extend mock rules with tests.
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --reload
```

## Checkpoint

- `tests/unit/test_demo_site_consistency.py`

## Exercises

1. Run the checkpoint tests with `uv run --no-sync pytest <node-id> -q`.
2. Change one config value and predict which test should fail first.
3. Skim `PLAN.md` for the matching section and compare it to the code you opened.

