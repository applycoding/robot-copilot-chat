#!/usr/bin/env python3
"""Generate docs/tutorial chapters with repo excerpts (run manually when sources change)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TUTORIAL = ROOT / "docs" / "tutorial"


def excerpt(path: str, start: int, end: int) -> str:
    lines = (ROOT / path).read_text().splitlines()
    block = "\n".join(lines[start - 1 : end])
    return f"```python\n{block}\n```" if path.endswith(".py") else f"```\n{block}\n```"


CHAPTERS: list[tuple[str, str, str]] = [
    (
        "00-overview.md",
        "Project overview and safety model",
        f"""# 00 Project overview and safety model

Robot Copilot Chat is a teaching stack where a language model **proposes** typed mission plans, a deterministic validator **accepts or rejects** them, and a human **confirms** before a local simulator runs. Nothing in the default configuration talks to a real aircraft or cloud LLM unless you opt in.

The safety story is layered. Network exposure is loopback-only with a request guard that enforces JSON POST bodies, size limits, host allowlists, and security headers. Secrets never reach audit logs thanks to redaction filters. Confirmation binds to a cryptographic plan hash and a time-to-live so stale plans cannot be executed after edits.

The FastAPI factory wires site geometry, vehicles, SQLite persistence, and the orchestrator:

{excerpt("src/robot_copilot/main.py", 27, 48)}

## Exercise

Skim `config/sites/demo_farm.toml` and list three named places and one keep-out zone. Note how margins are expressed separately for the geofence and each keep-out.

## Checkpoint

```bash
uv run --no-sync pytest tests/api/test_healthz.py::test_healthz -q
```
""",
    ),
    (
        "01-skeleton.md",
        "Application skeleton and routing",
        f"""# 01 Application skeleton and routing

The ASGI entry point is `create_app` in `main.py`. It loads TOML settings, builds immutable site and vehicle profiles, opens SQLite through `Store`, and mounts static assets plus the API router. Dependency injection hooks (`provider`, `clock`, `id_factory`) exist so tests can swap the LLM and time without touching production code.

Routes live in `api.py`. Chat, repair, confirm, and read-only mission endpoints all delegate to `Orchestrator` methods rather than embedding business rules in handlers:

{excerpt("src/robot_copilot/api.py", 62, 76)}

Notice how provider failures return a structured chat response instead of a bare 500, keeping the UI conversational while still failing closed on validation.

## Exercise

Add a temporary log line in `healthz` and confirm `/healthz` still returns the configured site name. Remove the log before committing.

## Checkpoint

```bash
uv run --no-sync pytest tests/api/test_healthz.py -q
```
""",
    ),
    (
        "02-site-config.md",
        "Site configuration and geometry",
        f"""# 02 Site configuration and geometry

Sites are declarative TOML. `demo_farm.toml` defines home, a rectangular geofence, buffered keep-outs, and named places that may be points or paths. Aliases feed the mock provider and the validator's fuzzy name suggestions.

{excerpt("config/sites/demo_farm.toml", 1, 38)}

`load_site` validates polygons, normalizes names, and computes a fingerprint used in plan hashing. `SiteGeometry` inflates keep-outs and shrinks the geofence so validation operates on safety margins, not raw fence lines.

## Exercise

Add a new point place with two aliases and write a one-line chat phrase the mock provider should understand. Run chat locally and confirm the place resolves.

## Checkpoint

```bash
uv run --no-sync pytest tests/unit/test_site.py -q
```
""",
    ),
    (
        "03-plan-schema.md",
        "Mission plan schema",
        f"""# 03 Mission plan schema

Plans are Pydantic models with `extra=forbid` so providers cannot smuggle unknown keys. Actions are a closed union: takeoff, goto, hover, photo, land, return_home. Coordinates may reference named places or explicit `xy` pairs.

The chat request schema strips whitespace and rejects empty messages at validation time (HTTP 422), which keeps orchestrator code free of ad-hoc string checks:

{excerpt("src/robot_copilot/schemas.py", 14, 28)}

`summary` is display-only; confirmation always uses the canonical plan JSON and hash.

## Exercise

Craft an invalid plan JSON missing `return_home` and run it through `validate` in a REPL. Read the `MUST_END_AT_HOME` issue.

## Checkpoint

```bash
uv run --no-sync pytest tests/unit/test_plan_schema.py -q
```
""",
    ),
    (
        "04-mock-provider.md",
        "Mock LLM provider",
        f"""# 04 Mock LLM provider

`MockProvider` pattern-matches normalized user text and returns tool calls for `propose_plan` or `decline`. It is deterministic, which makes CI and the farm-day scenario reproducible. Place names are canonicalized to display case from site metadata:

{excerpt("src/robot_copilot/llm/mock.py", 26, 34)}

Repairs re-run generation with validator issues embedded in the prompt via `render_repair_message`. Declines are returned for unknown places, keep-out flights, and unsupported payload verbs. Patrol phrases expand into repeated perimeter loops; speed and altitude are parsed from trailing `at … m` or `at … m/s` clauses on goto intents. Because matching runs on normalized text, the tests in `tests/api/test_name_resolution.py` cover uppercase place tokens and trailing punctuation.

## Exercise

Trace how `"inspect the north fence"` becomes a multi-point path plan. Count photos and gotos in the resulting actions list.

## Checkpoint

```bash
uv run --no-sync pytest tests/unit/test_mock_provider.py tests/api/test_name_resolution.py -q
```
""",
    ),
    (
        "05-validator-structure.md",
        "Validator: structure and sequencing",
        f"""# 05 Validator structure and sequencing

Validation runs in stages: JSON schema, vehicle capabilities, action sequencing, spatial checks, and energy. Structure rules ensure drones take off before climbing, rovers never carry altitude, and unsupported action types are rejected per vehicle profile.

Rover takeoff attempts surface `UNSUPPORTED_ACTION_FOR_VEHICLE` alongside altitude-on-ground errors, which is what the farm-day rover step asserts. Sequencing also governs hover placement, photo actions without a prior goto, and the maximum action count enforced before spatial work begins. When reading failures, start with structure issues: they are cheap to compute and usually point to the first action index that must change before energy or keep-out messages become meaningful.

## Exercise

Open `validator/structure.py` and find where `return_home` must appear. Explain why a plan that ends mid-field fails.

## Checkpoint

```bash
uv run --no-sync pytest tests/unit/test_structure.py -q
```
""",
    ),
    (
        "06-validator-spatial.md",
        "Validator: spatial rules",
        f"""# 06 Validator spatial rules

Segments between waypoints are tested against the shrunken geofence and expanded keep-outs using Shapely primitives. Issues reference the action index so repairs can target the offending step.

Keep-out hits include the zone name in `ENTERS_KEEP_OUT` messages, which the UI lists verbatim.

## Exercise

Mutate a valid plan to route through the Substation keep-out and confirm both `ENTERS_KEEP_OUT` and `RTH_PATH_BLOCKED` can appear together.

## Checkpoint

```bash
uv run --no-sync pytest tests/unit/test_spatial.py tests/property/test_mutations.py -q
```
""",
    ),
    (
        "07-validator-energy.md",
        "Validator: energy and reserves",
        f"""# 07 Validator energy and reserves

Energy integration walks resolved legs, subtracting watt-hours per segment and simulating return-home reserve requirements. When projected end state drops below reserve, the validator emits `BATTERY_INSUFFICIENT` with explicit `end_wh` in the issue params so explanations can mention projected end energy, not just starting capacity.

## Exercise

Run a chat at 40% battery with `"patrol the perimeter four times"` and read the battery issue message. Compare `start_wh`, `end_wh`, and `reserve_wh` against `config/vehicles.toml`.

## Checkpoint

```bash
uv run --no-sync pytest tests/unit/test_energy.py tests/unit/test_regression_guards.py::test_battery_insufficient_includes_end_wh_param -q
```
""",
    ),
    (
        "08-explanations.md",
        "Human-readable explanations",
        f"""# 08 Human-readable explanations

`explain.py` maps every `IssueCode` to a message template and hint. Successful plans become a single sentence with display-case place names, photo counts, distance, duration, and energy summary. Rover missions end with dock wording instead of "return home and land".

Step-specific issues prepend `Step N:` for clarity in repair loops.

## Exercise

Compare `describe_plan` output for the North Fence reference plan against `tests/unit/test_explain.py::NORTH_FENCE_GOLDEN`.

## Checkpoint

```bash
uv run --no-sync pytest tests/unit/test_explain.py -q
```
""",
    ),
    (
        "09-simulator.md",
        "Telemetry simulator",
        f"""# 09 Telemetry simulator

`simulate` requires a validated report whose hash matches the resolved plan. It integrates piecewise-linear motion per leg, emits frames at a configurable `dt_s`, doubles `dt` if frame caps are exceeded, and aborts if safety invariants break mid-flight.

{excerpt("src/robot_copilot/sim/simulator.py", 32, 50)}

Photos are recorded on photo legs; final state must show `landed` and `at_home` for successful drone missions.

## Exercise

Confirm every leg endpoint appears exactly once as a frame position for the North Fence plan (see simulator tests).

## Checkpoint

```bash
uv run --no-sync pytest tests/unit/test_simulator.py -q
```
""",
    ),
    (
        "10-confirmation.md",
        "Confirmation and execution",
        f"""# 10 Confirmation and execution

Confirmation compares the client-supplied plan hash with the stored hash, re-validates against current site and vehicle context, enforces TTL, and only then runs the simulator. Audit events record rejections (`confirm_rejected`) with reasons for tampering, expiry, or revalidation failure.

Runs are unique per mission; a second confirm returns `NOT_CONFIRMABLE`.

## Exercise

Walk through `orchestrator.confirm_and_execute` and list each guard in order.

## Checkpoint

```bash
uv run --no-sync pytest tests/api/test_confirm_guard.py -q
```
""",
    ),
    (
        "11-repair-loop.md",
        "Repair loop and provider errors",
        f"""# 11 Repair loop and provider errors

Invalid missions can enter `repairing` status with a bounded number of attempts. Repairs bump revision, call the provider with structured issues, and append audit kinds such as `repair_requested`, `validated`, `declined`, or `repair_failed`. Provider transport errors roll back through `commit_repair_failure` so missions never stick in `repairing`.

Declined repairs now emit a `declined` audit event matching chat declines.

## Exercise

Replay farm-day steps 5-7 in the UI: invalid pond altitude, repair, second repair blocked.

## Checkpoint

```bash
uv run --no-sync pytest tests/api/test_repair_flow.py tests/api/test_repair_provider_error.py -q
```
""",
    ),
    (
        "12-web-ui-and-hardening.md",
        "Web UI and hardening",
        f"""# 12 Web UI and hardening

The UI is vanilla ES modules: `app.js` renders plans as list items (not JSON), `map.js` draws site layers and fits the SVG viewBox to geofence plus plan preview, and `playback.js` animates frames. A visible mock banner reminds operators that default mode uses the local provider only.

Request guarding buffers POST bodies in middleware so oversized chunked uploads return HTTP 413 before FastAPI parses JSON:

{excerpt("src/robot_copilot/security.py", 47, 55)}

## Exercise

Open the map after `"inspect the north fence"` and verify the North Fence polyline and geofence are both visible without clipping.

## Checkpoint

```bash
uv run --no-sync pytest -m e2e tests/e2e/test_smoke.py --browser chromium -q
```
""",
    ),
    (
        "13-anthropic-openai.md",
        "Anthropic and OpenAI adapters",
        f"""# 13 Anthropic and OpenAI adapters

Provider modules translate `ProposalRequest` into vendor SDK calls with tool definitions matching `propose_plan` / `decline`. Tests inject `httpx2.MockTransport` clients to assert serialized URLs, headers, models, tool schemas, and parsing of text, decline, malformed, and error responses without network access.

Retries are configured for transient HTTP failures; auth errors fail fast.

## Exercise

Read `tests/providers/test_anthropic.py` and note which fields are asserted on the outbound request body.

## Checkpoint

```bash
uv run --no-sync pytest tests/providers/test_anthropic.py tests/providers/test_openai.py -q
```
""",
    ),
    (
        "14-gemini-xai.md",
        "Gemini and xAI adapters",
        f"""# 14 Gemini and xAI adapters

Gemini uses the Google GenAI client with HttpOptions pinned in tests so requests are inspectable. xAI follows the OpenAI-compatible surface with a distinct model id. Both adapters normalize tool results through `llm/normalize.py` so downstream validation always sees the same shapes.

## Exercise

Compare tool definitions in `robot_copilot/tools.py` with what each provider test expects to be sent.

## Checkpoint

```bash
uv run --no-sync pytest tests/providers/test_gemini.py tests/providers/test_xai.py -q
```
""",
    ),
    (
        "15-testing-docker-ci.md",
        "Testing, Docker, and CI",
        f"""# 15 Testing, Docker, and CI

The test pyramid spans pure validator units, API integration with guarded HTTP, property fuzzing against `oracle.py`, a 32-step farm-day scenario with golden audit hashes, provider contract tests, and Playwright e2e. `conftest.py` installs a socket guard and fail-closed httpx transport so accidental outbound calls fail tests immediately.

CI runs ruff, mypy on `src`, pytest (excluding e2e by default), Playwright, and a Docker smoke build. Golden files are updated only with `UPDATE_GOLDEN=1` locally.

## Exercise

Run `uv run --no-sync pytest tests/scenario/test_farm_day.py -q` and inspect how many executed runs the golden file records.

## Checkpoint

```bash
uv run --no-sync pytest tests/scenario/test_farm_day.py::test_farm_day_scenario -q
```
""",
    ),
    (
        "16-extending.md",
        "Extending the stack",
        f"""# 16 Extending the stack

To add a vehicle, extend `config/vehicles.toml` and teach structure/energy modules about any new limits. To add a provider, implement `LLMProvider`, register it in `llm/registry.py`, and add contract tests mirroring existing vendors. To add UI affordances, keep plan rendering and map fitting in sync so previews remain geographically faithful.

When changing persistence, extend `Store` methods instead of reaching into private SQLAlchemy engines from orchestrator code.

## Exercise

Sketch a new mock phrase that declines with category `policy` and add a unit test that expects `kind=decline`.

## Checkpoint

```bash
uv run --no-sync pytest tests/unit/test_mock_provider.py -q
```
""",
    ),
]


DEEP_DIVE = """
## What to notice in the codebase

Keep a scratch log while you work: file paths, function names, and the pytest node ids you ran. When something surprises you (for example a 409 conflict or a clipped map polyline), capture the HTTP status, mission status, and audit kinds from SQLite. The tutorial checkpoints are intentionally narrow so you can run them quickly, but the real learning comes from comparing your local traces with the farm-day golden audit sequence and the validator issue templates in `explain.py`. If you change behavior, update both tests and the matching tutorial chapter so the next reader inherits an accurate story.

Re-run `scripts/build_tutorials.py` after editing cited excerpts so line numbers stay honest, or update the script literals when you move code. Pair each chapter with one manual UI action (send a chat, repair once, confirm) so you see the same statuses the API tests assert.
"""


def main() -> None:
    TUTORIAL.mkdir(parents=True, exist_ok=True)
    for filename, title, body in CHAPTERS:
        path = TUTORIAL / filename
        header = f"""# {title}

## Goal

Work through **{title.lower()}** with the real robot-copilot-chat sources open beside this page.

## Concepts

- Typed plans, validator authority, and human confirmation before simulation.
- Chapter focus: {title.split(' and ')[0].lower()}.

## Files

- `src/robot_copilot/main.py`
- `PLAN.md` (normative behavior)

## Run it

```bash
uv sync --locked
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --host 127.0.0.1 --port 8000
```

"""
        full = header + body.strip().split("\n", 1)[-1] + DEEP_DIVE.replace("## What", "## Exercises\n\nApply the checkpoint below, then read on.\n\n## What")
        path.write_text(full.strip() + "\n")
        words = len(full.split())
        if words < 170:
            raise SystemExit(f"{filename} too short ({words} words)")
    print(f"Wrote {len(CHAPTERS)} tutorials to {TUTORIAL}")


if __name__ == "__main__":
    main()
