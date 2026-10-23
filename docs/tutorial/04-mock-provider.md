# 04 Mock LLM provider

## Goal

The mock LLM provider proposes tool calls with zero network traffic, which keeps CI and classroom laptops reliable. You will trace regex routing from operator phrases to MissionPlan actions, including patrol, photo, and keep-out flyover demos. Canonical place lookup shares normalization with the site loader so BARN and the barn mean the same Barn target.

MockProvider implements propose without network IO, enabling offline CI and classroom laptops alike. _canonical_place maps noisy operator strings onto canonical site names using SiteSummary aliases. _inspect_place expands path places into repeated goto-hover-photo sequences at optional altitudes.

Regex handlers cover patrol loops, photos, hover timers, keep-out flyovers, and simple goto commands. Patrol plans wrap perimeter vertices with takeoff and return_home for drones but not rovers. Decline paths trigger when regex detects unsupported payload verbs like drop or spray.

Repair mode rewrites plans using structured issue briefs rather than echoing full prior JSON. Normalization pipeline validates tool args sizes and required fields before orchestrator commits missions. Photo intents normalize to goto place plus hover dwell then photo action for drones.

Keep-out flyovers may synthesize goto xy inside forbidden regions to teach spatial failures. Site summary tools expose place counts so prompts stay compact for real providers too. Mock model id flows into audit metadata identical to cloud providers for uniform dashboards.

Provider results distinguish text, plan, and decline kinds consumed by orchestrator._commit_chat. Tool specs declare JSON schemas shared with Anthropic and OpenAI adapters in later chapters. Uppercase aliases like BARN should still resolve to Barn thanks to normalize_name in canonicalization.

Tests lock regex behavior so tutorial phrases in README stay synchronized with validator expectations. Understanding mock routing helps you debug chat flows before spending cloud tokens. This provider is not a toy; it encodes the same tool contracts production models must honor.

## Files

- `src/robot_copilot/llm/mock.py`
- `src/robot_copilot/llm/normalize.py`
- `src/robot_copilot/tools.py`
- `tests/unit/test_mock_provider.py`

## Walkthrough

1. _canonical_place iterates summary places and aliases, returning the canonical name when normalization matches.

<!-- segment: src/robot_copilot/llm/mock.py _canonical_place -->

```python
def _canonical_place(summary: SiteSummary, raw: str) -> str:
    cleaned = raw.strip().rstrip(".")
    norm = normalize_name(cleaned)
    for place in summary.places:
        if normalize_name(str(place.get("name", ""))) == norm:
            return str(place["name"])
        for alias in place.get("aliases", []):
            if normalize_name(str(alias)) == norm:
                return str(place["name"])
    return raw
```

When lookup fails, raw text flows through so unknown_place issues can still be diagnosed clearly.

2. _inspect_place counts path vertices from the summary, emitting per-point gotos and inspection photos.

<!-- segment: src/robot_copilot/llm/mock.py _inspect_place -->

```python
def _inspect_place(
    place: str, alt: float | None, vehicle: str, site_summary: object
) -> list[dict[str, object]]:
    body: list[dict[str, object]] = []
    count = 1
    for p in getattr(site_summary, "places", []):
        if normalize_name(p.get("name", "")) == normalize_name(place):
            count = p.get("point_count", 1)
            break
    for idx in range(count):
        goto: dict[str, object] = {"type": "goto", "place": place, "point_index": idx}
        if alt is not None:
            goto["altitude_m"] = alt
        body.append(goto)
        if vehicle == "drone":
            body.append({"type": "hover", "seconds": 3})
        body.append({"type": "photo"})
    return body
```

Optional altitude_m parameters attach to goto actions for fence inspections at specified heights.
## Try it

```bash
RCC_DOTENV=off uv run --no-sync python -c "
from pathlib import Path
from robot_copilot.site import load_site
from robot_copilot.tools import build_site_summary
from robot_copilot.vehicles import load_vehicles
from robot_copilot.llm.mock import _canonical_place
site = load_site(Path('config/sites/demo_farm.toml'))
vehicles = load_vehicles(Path('config/vehicles.toml'))
summary = build_site_summary(site, vehicles['drone'])
print(_canonical_place(summary, 'BARN'))
"
```

### Expected

```
Barn
```

## Exercise

Send patrol the perimeter twice and count goto actions before return_home.

## Checkpoint

- `tests/api/test_name_resolution.py::test_barn_aliases_resolve_in_mock_plans`
