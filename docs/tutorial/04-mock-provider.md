# Mock LLM provider

## Goal

Work through **mock llm provider** with the real robot-copilot-chat sources open beside this page.

## Concepts

- Typed plans, validator authority, and human confirmation before simulation.
- Chapter focus: mock llm provider.

## Files

- `src/robot_copilot/main.py`
- `PLAN.md` (normative behavior)

## Run it

```bash
uv sync --locked
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --host 127.0.0.1 --port 8000
```


`MockProvider` pattern-matches normalized user text and returns tool calls for `propose_plan` or `decline`. It is deterministic, which makes CI and the farm-day scenario reproducible. Place names are canonicalized to display case from site metadata:

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
```

Repairs re-run generation with validator issues embedded in the prompt via `render_repair_message`. Declines are returned for unknown places, keep-out flights, and unsupported payload verbs. Patrol phrases expand into repeated perimeter loops; speed and altitude are parsed from trailing `at … m` or `at … m/s` clauses on goto intents. Because matching runs on normalized text, the tests in `tests/api/test_name_resolution.py` cover uppercase place tokens and trailing punctuation.

## Exercise

Trace how `"inspect the north fence"` becomes a multi-point path plan. Count photos and gotos in the resulting actions list.

## Checkpoint

```bash
uv run --no-sync pytest tests/unit/test_mock_provider.py tests/api/test_name_resolution.py -q
```
## Exercises

Apply the checkpoint below, then read on.

## What to notice in the codebase

Keep a scratch log while you work: file paths, function names, and the pytest node ids you ran. When something surprises you (for example a 409 conflict or a clipped map polyline), capture the HTTP status, mission status, and audit kinds from SQLite. The tutorial checkpoints are intentionally narrow so you can run them quickly, but the real learning comes from comparing your local traces with the farm-day golden audit sequence and the validator issue templates in `explain.py`. If you change behavior, update both tests and the matching tutorial chapter so the next reader inherits an accurate story.

Re-run `scripts/build_tutorials.py` after editing cited excerpts so line numbers stay honest, or update the script literals when you move code. Pair each chapter with one manual UI action (send a chat, repair once, confirm) so you see the same statuses the API tests assert.
