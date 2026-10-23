# 04 Mock LLM provider

`MockProvider` pattern-matches normalized user phrases and returns tool calls for `propose_plan` or `decline`. It powers local development, Playwright e2e, and the farm-day scenario without network access. Repairs reuse the same matcher with validator issues embedded in the prompt.

Place tokens from user text are mapped to display-case site names before plan JSON is built:

Repair mode reuses `_chat` logic after reading structured issues from the request. Speed and altitude suffix parsers strip trailing clauses before canonicalizing place names, which is why `fly to the barn at 25 m/s` becomes a speed violation while place names stay stable. Help text is returned as plain assistant content with `kind=help` and no mission row.

## Files

- `src/robot_copilot/llm/mock.py`
- `src/robot_copilot/llm/normalize.py`
- `src/robot_copilot/tools.py`

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

Declines fire for payload verbs, unknown places on repair, keep-out flights, and similar hard failures. Patrol phrases expand into repeated perimeter loops with deterministic geometry.



This chapter ties to the integration story in `tests/scenario/farm_day.json`: replay those steps after reading so you see how mock-provider behaves inside a long conversation with repairs, declines, and confirmations. Cross-check any prose claims against `PLAN.md` criterion numbers when you are preparing a portfolio review.
## Exercise

Send `take a photo of BARN` and inspect the plan JSON: every `goto.place` should read `Barn`, not `BARN`.

## Checkpoint

- `tests/api/test_name_resolution.py`
