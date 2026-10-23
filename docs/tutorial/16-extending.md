# 16 Extending the stack

## Goal

You are reading tutorial chapter 16 about tools and site summaries in robot-copilot-chat. Chapter 16 links tools and site summaries to validators, confirmation hashes, and local simulation gates. Learning note 16-1: tool_specs defines JSON schemas for propose and decline tools shared across providers. Learning note 16-2: build_site_summary compresses places and keep-outs into compact dicts for model prompts. Learning note 16-3: Adding a new action type requires plan schema updates, validator passes, simulator support, and mock routing. Learning note 16-4: Site summary point counts drive inspect loops without sending full coordinate arrays to models. Learning note 16-5: Extending demo_farm.toml demands demo site consistency tests and README updates together. Learning note 16-6: New vehicles need profiles in vehicles.toml plus structure rules and UI select options. Learning note 16-7: Tool arg byte limits protect SQLite from oversized provider payloads during normalize. Learning note 16-8: Registry changes must remain explicit; hidden auto-discovery of providers is intentionally avoided. Learning note 16-9: Hygiene and tutorial tests guard documentation quality when contributors add features. Learning note 16-10: Mock provider remains the reference implementation for tool-call behavior new clouds must match. Learning note 16-11: Path preview generation may need updates when new action types alter resolved leg lists. Learning note 16-12: Explain templates require IssueCode entries for any new validator failures introduced. Learning note 16-13: Simulation frame builders must understand geometry for new motion primitives you add. Learning note 16-14: API schemas and OpenAPI-disabled policy mean HTTP contracts change only with tests updated. Learning note 16-15: Consider property tests when adding validators to catch regressions across randomized plans. Learning note 16-16: Document new features in tutorial checkpoints only after pytest covers schema, validator, simulator, and mock paths. Learning note 16-17: Site summaries should stay small; prefer counts and names over dumping vertices. Learning note 16-18: Extension work is complete when farm day scenarios and tutorial try-it blocks still pass unchanged.

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
