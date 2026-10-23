# 02 Site configuration and geometry

Sites live in TOML under `config/sites/`. Each file defines `home`, a closed geofence polygon, buffered keep-outs, and named places (point or path). Aliases feed both the mock provider and fuzzy suggestions when validation reports `UNKNOWN_PLACE`.

Name normalization strips punctuation and a leading "the" so `BARN.` and `the barn` match configured names:

`resolve_place` and `suggest_places` power both validation errors and mock routing. Path places such as North Fence expand to multiple vertices during resolution, which is why inspect missions generate several gotos and photos. Keep-out margins are larger than geofence inset defaults, reflecting the spec's stricter buffer around hazards like the Substation.

## Files

- `config/sites/demo_farm.toml`
- `src/robot_copilot/site.py`
- `src/robot_copilot/geometry.py`

```python
def normalize_name(text: str) -> str:
    t = text.casefold()
    t = _PUNCT_RE.sub(" ", t)
    t = " ".join(t.split())
    if t.startswith("the "):
        t = t[4:]
    return t.strip()
```

`SiteGeometry.build` applies geofence inset and keep-out expansion before any segment tests. Invalid polygons fail at import time with `SiteConfigError`, not at runtime.



This chapter ties to the integration story in `tests/scenario/farm_day.json`: replay those steps after reading so you see how site-config behaves inside a long conversation with repairs, declines, and confirmations. Cross-check any prose claims against `PLAN.md` criterion numbers when you are preparing a portfolio review.
## Exercise

Add a temporary alias on `Pond` in `demo_farm.toml`, restart the app, and chat `hover over the alias for 5 s` (use your alias text). Remove the alias afterward.

## Checkpoint

- `tests/unit/test_site.py`
