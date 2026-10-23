# 02 Site configuration and place resolution

## Goal

Every validator and map overlay reads the same demo farm loaded from TOML. Here you learn how place names normalize, how aliases resolve informal operator text, and why polygon validation fails fast when a site file is inconsistent. Path places such as North Fence matter later for inspect loops, patrol geometry, and simulator frame counts.

Sites load from TOML under config/sites with geofence polygons, keep-outs, and named places. normalize_name case-folds text, strips punctuation, and removes a leading article before comparisons. Aliases on places let operators type informal labels while canonical names stay cartographer friendly.

load_site validates polygon orientation, margins, and place kind constraints before returning a Site dataclass. resolve_place walks aliases after normalization so mock regex captures need not list every spelling. Path places expose multiple vertices used by perimeter patrol mock plans and spatial energy legs.

Keep-out margins expand polygons slightly so numerical edge cases do not graze forbidden airspace. Home coordinates anchor return-home energy calculations and simulator final state checks. SiteGeometry builds spatial indexes consumed by segment_hits_keepout and geofence tests.

Vehicle profiles load separately from vehicles.toml and attach to ValidationContext per request. Demo farm includes Barn, Pond, substation keep-out, and North Fence path used throughout pytest. Site summary JSON feeds provider tools so models see counts without dumping full coordinate lists.

Changing demo_farm.toml requires consistency tests so README phrases still match validator outcomes. Invalid polygons raise SiteLoadError with human-readable problems instead of silent Shapely failures. Place kinds distinguish point targets from polylines, affecting inspect loops and visit copy.

Tutorial operators should treat site edits as contract changes reviewed by unit and scenario tests. Map rendering uses the same site payload as validators, avoiding drift between UI and physics. This chapter pairs normalization with full loader validation to show failures happen early.

## Files

- `src/robot_copilot/site.py`
- `config/sites/demo_farm.toml`
- `src/robot_copilot/geometry.py`
- `tests/unit/test_site.py`

## Walkthrough

1. normalize_name is the shared tokenization step for alias tables, keep-out names, and mock place capture groups.

<!-- segment: src/robot_copilot/site.py normalize_name -->

```python
def normalize_name(text: str) -> str:
    """Normalize free-text place labels for alias and keep-out matching.

    Case folding and punctuation stripping let operators type informal names
    while the resolver compares stable tokens.
    """
    t = text.casefold()
    t = _PUNCT_RE.sub(" ", t)
    t = " ".join(t.split())
    if t.startswith("the "):
        t = t[4:]
    return t.strip()
```

Because every matcher uses the same function, a fix here improves chat, validation, and provider tools together.

2. load_site parses TOML into typed tuples, then calls _validate_site before any mission references coordinates.

<!-- segment: src/robot_copilot/site.py load_site -->

```python
def load_site(path: Path) -> Site:
    with path.open("rb") as f:
        raw = tomllib.load(f)
    site_raw = raw.get("site", {})
    keep_outs_raw = raw.get("keep_out", [])
    places_raw = raw.get("places", [])

    def coord(c: list[float]) -> Coord:
        return (float(c[0]), float(c[1]))

    site = Site(
        id=str(site_raw["id"]),
        name=str(site_raw["name"]),
        home=coord(site_raw["home"]),
        geofence=tuple(coord(p) for p in site_raw["geofence"]),
        geofence_margin_m=float(site_raw.get("geofence_margin_m", 0)),
        keep_out=tuple(
            KeepOut(
                name=str(k["name"]),
                polygon=tuple(coord(p) for p in k["polygon"]),
                margin_m=float(k.get("margin_m", 0)),
            )
            for k in keep_outs_raw
        ),
        places=tuple(
            Place(
                name=str(p["name"]),
                aliases=tuple(str(a) for a in p.get("aliases", [])),
                kind=p["kind"],
                points=tuple(coord(pt) for pt in p["points"]),
            )
            for p in places_raw
        ),
    )
    _validate_site(site)
    return site
```

Early validation prevents orchestrator from accepting chats when the world description is internally inconsistent.
## Try it

```bash
RCC_DOTENV=off uv run --no-sync python -c "
from robot_copilot.site import load_site, resolve_place
from pathlib import Path
site = load_site(Path('config/sites/demo_farm.toml'))
print(resolve_place(site, 'the barn').name)
"
```

### Expected

```
Barn
```

## Exercise

Add a temporary alias on Pond, chat with it, then revert and rerun site tests.

## Checkpoint

- `tests/unit/test_site.py::test_normalize_and_resolve`
