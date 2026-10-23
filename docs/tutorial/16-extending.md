# 16 Extending the stack

## Goal

Extending the stack means updating schemas, validators, simulator motion, mock regex routes, and tool_specs together so providers cannot invent silent new action types. build_site_summary compresses places for prompts without dumping full coordinate lists. Demo farm consistency tests lock patrol calibration so README phrases and tutorial Try it commands stay truthful.

## Files

- `src/robot_copilot/tools.py`
- `src/robot_copilot/llm/mock.py`
- `tests/unit/test_demo_site_consistency.py`

## Walkthrough

1. tool_specs returns the tool definition list passed into Anthropic, OpenAI, and Gemini clients.

<!-- segment: src/robot_copilot/tools.py tool_specs -->

```python
def tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name=PROPOSE_TOOL,
            description="Propose a mission plan as structured actions.",
            parameters=inline_schema(MissionPlan),
        ),
        ToolSpec(
            name=DECLINE_TOOL,
            description="Decline a mission request that cannot be fulfilled safely.",
            parameters=inline_schema(DeclineRequest),
        ),
    ]
```

Keeping schemas centralized prevents incompatible tool names across providers.

2. build_site_summary walks Site objects to produce prompt-friendly metadata used in ProposalRequest payloads.

<!-- segment: src/robot_copilot/tools.py build_site_summary -->

```python
def build_site_summary(site: Site, vehicle: DroneProfile | RoverProfile) -> SiteSummary:
    places = [
        {
            "name": p.name,
            "aliases": list(p.aliases),
            "kind": p.kind,
            "point_count": len(p.points),
        }
        for p in site.places
    ]
    limits: dict[str, float] = {
        "max_actions": float(vehicle.max_actions),
        "max_distance_m": vehicle.max_distance_m,
        "max_duration_s": vehicle.max_duration_s,
        "max_hover_s": vehicle.max_hover_s,
        "max_speed_mps": vehicle.max_speed_mps,
    }
    if isinstance(vehicle, DroneProfile):
        limits.update(
            {
                "min_altitude_m": vehicle.min_altitude_m,
                "max_altitude_m": vehicle.max_altitude_m,
                "default_altitude_m": vehicle.default_altitude_m,
            }
        )
    return SiteSummary(
        site_name=site.name,
        places=places,
        keep_outs=[k.name for k in site.keep_out],
        limits=limits,
    )
```

Place entries include kinds, aliases, and point counts consumed by mock canonicalization helpers.
## Try it

```bash
RCC_DOTENV=off uv run --no-sync pytest tests/unit/test_demo_site_consistency.py::test_patrol_calibration -q --no-header
```

### Expected

```
1 passed
```

## Exercise

Add a dummy alias in demo_farm.toml, run consistency tests, then revert the alias.

## Checkpoint

- `tests/unit/test_demo_site_consistency.py::test_patrol_calibration`
