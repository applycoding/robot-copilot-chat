# 04 Mock LLM provider

## Goal

The mock LLM provider proposes tool calls with zero network traffic, which keeps CI and classroom laptops reliable. You will trace regex routing from operator phrases to MissionPlan actions, including patrol, photo, and keep-out flyover demos. Canonical place lookup shares normalization with the site loader so BARN and the barn mean the same Barn target.

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
