"""Regenerate docs/tutorial/*.md from AST excerpts and chapter metadata."""

from __future__ import annotations

import json
from pathlib import Path

from tests.repo.tutorial_ast import assert_segment_rules, extract_segment
from tests.repo.tutorial_goal_prose import goal_for_chapter

ROOT = Path(__file__).resolve().parents[2]
TUTORIAL = ROOT / "docs/tutorial"
CACHE = Path(__file__).with_name("tutorial_excerpt_cache.json")
TRY_EXPECTED = Path(__file__).with_name("tutorial_try_expected.json")


def _segment_fence(rel: str, qualname: str, text: str) -> str:
    return f"<!-- segment: {rel} {qualname} -->\n\n```python\n{text.rstrip()}\n```\n"


def _try_section(bash: str, expected: list[str], note: str = "") -> str:
    note_line = f"{note}\n\n" if note else ""
    expected_body = "\n".join(expected)
    return f"""## Try it

{note_line}```bash
{bash.strip()}
```

### Expected

```
{expected_body}
```
"""


CHAPTER_DEFS: list[dict] = []  # filled below after imports


def _chapter(
    fname: str,
    title: str,
    topic: str,
    bullets: list[str],
    files: list[str],
    walkthrough: list[tuple[str, int, str]],
    try_bash: str,
    try_expected: list[str],
    exercise: str,
    checkpoint: list[str],
    try_note: str = "",
) -> dict:
    return {
        "fname": fname,
        "title": title,
        "topic": topic,
        "bullets": bullets,
        "files": files,
        "walkthrough": walkthrough,
        "try_bash": try_bash,
        "try_expected": try_expected,
        "exercise": exercise,
        "checkpoint": checkpoint,
        "try_note": try_note,
    }


CHAPTER_DEFS = [
    _chapter(
        "00-overview.md",
        "00 Project overview and safety model",
        "redaction and the safety envelope",
        [
            "Redaction runs before request guards so provider stack traces never echo API keys copied from dotenv files.",
            "The mock provider is default, yet settings still load optional cloud keys for experiments you run locally.",
            "Validators are pure functions over typed plans; they never call models or mutate SQLite rows directly.",
            "Human confirmation binds to a SHA-256 plan hash so tampered JSON cannot execute after review.",
            "Simulation consumes validated reports only, which prevents guessing physics from draft provider output.",
            "Audit events record confirm, repair, and decline transitions for later forensics in teaching demos.",
            "Static assets ship from FastAPI, while JSON APIs power the browser chat and playback widgets.",
            "Configuration merges TOML defaults with environment overrides through a single settings loader.",
            "Issue codes are stable enums so explanations, repairs, and UI badges stay aligned across releases.",
            "Keep-out polygons and geofences come from site TOML consumed by spatial checks and map rendering.",
            "Energy checks include return-home legs because battery failures often appear only on the way back.",
            "Repair loops cap attempts so runaway provider failures cannot spam tokens during classroom sessions.",
            "Concurrency limits on provider calls protect SQLite from thrashing when many students chat at once.",
            "The health endpoint advertises provider name and site title so operators know which world loaded.",
            "pytest runs with RCC_DOTENV off in docs so tutorials do not depend on your private secrets file.",
            "Docker and CI pins appear later; this chapter only orients you to the safety ordering of components.",
            "When chat returns help text, the UI should clear map overlays so stale paths never mislead operators.",
            "Portfolio reviewers expect you to articulate each gate between natural language and simulated motion.",
        ],
        [
            "src/robot_copilot/redact.py",
            "src/robot_copilot/security.py",
            "config/app.toml",
            "src/robot_copilot/main.py",
        ],
        [
            (
                "Begin with `redact_text`, which scrubs configured secrets and sensitive headers from arbitrary strings.",
                0,
                "Logging hooks call this helper so bearer tokens in misconfigured clients do not reach stderr during failures.",
            ),
        ],
        """RCC_DOTENV=off uv run --no-sync python -c "
from fastapi.testclient import TestClient
from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env
s = load_settings(env=default_settings_env(), dotenv_enabled=False)
r = TestClient(create_app(s), base_url='http://localhost').get('/healthz')
print(r.status_code, r.json()['status'], r.json()['provider'], r.json()['site'])
" """,
        ["200 ok mock Applycoding Demo Farm"],
        "Write three sentences: what validators may change, what confirmation guarantees, and what simulation assumes about hashes.",
        ["tests/api/test_healthz.py::test_healthz"],
    ),
    _chapter(
        "01-skeleton.md",
        "01 Application skeleton and persistence",
        "SQLite store bootstrap",
        [
            "FastAPI `create_app` wires site geometry, vehicles, orchestrator, templates, and guarded routers in a fixed order.",
            "The store encapsulates SQLModel engines, monotonic string ids, and transactional commits for chat outcomes.",
            "bootstrap_id_factory scans existing rows so restarted dev servers continue id sequences without collisions.",
            "Store.from_url creates tables on boot, which keeps docker-less tutorials approachable for new contributors.",
            "Orchestrator methods never open raw SQL; they call store helpers that enforce optimistic concurrency.",
            "Conversation generation counters let new chat supersede stale missions awaiting confirmation.",
            "Mission revisions retain provider metadata per attempt so audits can reconstruct model provenance.",
            "Runs are unique per mission id, preventing double execution if a browser retries confirm.",
            "Clock injection supports deterministic created_at fields inside unit tests for id factories.",
            "Provider registry construction happens once per process, sharing timeouts loaded from app.toml.",
            "Lifespan hooks close provider HTTP clients cleanly when uvicorn shuts down.",
            "OpenAPI endpoints are disabled to reduce attack surface in classroom deployments.",
            "Validation error handler normalizes Pydantic failures into stable JSON the UI can render.",
            "Chat responses include kind plan, help, decline, or error so the front end can branch predictably.",
            "Greeting messages like hello should return kind help with mission None, clearing any prior map overlay.",
            "Static JavaScript modules import map and playback helpers without inline event handlers.",
            "API routes live in a dedicated module included after orchestrator construction.",
            "Next chapters load site TOML; this one focuses on persistence seams around orchestrator.chat.",
        ],
        [
            "src/robot_copilot/main.py",
            "src/robot_copilot/store.py",
            "src/robot_copilot/orchestrator.py",
            "src/robot_copilot/api.py",
        ],
        [
            (
                "Id generation resumes after restarts by scanning every persisted table for the highest `idNNNN` suffix.",
                0,
                "The factory closure increments a counter so new rows stay sortable during demos without UUIDs.",
            ),
            (
                "Store.from_url is the supported entry for tests and production: it builds the engine, creates schema, and injects ids.",
                1,
                "Passing a custom id_factory is rare but useful when you need deterministic sequences in property tests.",
            ),
        ],
        """RCC_DOTENV=off uv run --no-sync python -c "
from fastapi.testclient import TestClient
from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env
s = load_settings(env=default_settings_env(), dotenv_enabled=False)
c = TestClient(create_app(s), base_url='http://localhost')
r = c.post('/api/chat', json={'message':'hello','vehicle':'drone','battery_pct':80}).json()
print(r['kind'], r.get('mission'))
" """,
        ["help None"],
        "Trace POST /api/chat into orchestrator.chat and list persistence rows created on first contact.",
        ["tests/api/test_id_persistence.py::test_id_factory_resumes_after_restart"],
    ),
    _chapter(
        "02-site-config.md",
        "02 Site configuration and place resolution",
        "demo farm topology",
        [
            "Sites load from TOML under config/sites with geofence polygons, keep-outs, and named places.",
            "normalize_name case-folds text, strips punctuation, and removes a leading article before comparisons.",
            "Aliases on places let operators type informal labels while canonical names stay cartographer friendly.",
            "load_site validates polygon orientation, margins, and place kind constraints before returning a Site dataclass.",
            "resolve_place walks aliases after normalization so mock regex captures need not list every spelling.",
            "Path places expose multiple vertices used by perimeter patrol mock plans and spatial energy legs.",
            "Keep-out margins expand polygons slightly so numerical edge cases do not graze forbidden airspace.",
            "Home coordinates anchor return-home energy calculations and simulator final state checks.",
            "SiteGeometry builds spatial indexes consumed by segment_hits_keepout and geofence tests.",
            "Vehicle profiles load separately from vehicles.toml and attach to ValidationContext per request.",
            "Demo farm includes Barn, Pond, substation keep-out, and North Fence path used throughout pytest.",
            "Site summary JSON feeds provider tools so models see counts without dumping full coordinate lists.",
            "Changing demo_farm.toml requires consistency tests so README phrases still match validator outcomes.",
            "Invalid polygons raise SiteLoadError with human-readable problems instead of silent Shapely failures.",
            "Place kinds distinguish point targets from polylines, affecting inspect loops and visit copy.",
            "Tutorial operators should treat site edits as contract changes reviewed by unit and scenario tests.",
            "Map rendering uses the same site payload as validators, avoiding drift between UI and physics.",
            "This chapter pairs normalization with full loader validation to show failures happen early.",
        ],
        [
            "src/robot_copilot/site.py",
            "config/sites/demo_farm.toml",
            "src/robot_copilot/geometry.py",
            "tests/unit/test_site.py",
        ],
        [
            (
                "normalize_name is the shared tokenization step for alias tables, keep-out names, and mock place capture groups.",
                0,
                "Because every matcher uses the same function, a fix here improves chat, validation, and provider tools together.",
            ),
            (
                "load_site parses TOML into typed tuples, then calls _validate_site before any mission references coordinates.",
                1,
                "Early validation prevents orchestrator from accepting chats when the world description is internally inconsistent.",
            ),
        ],
        """RCC_DOTENV=off uv run --no-sync python -c "
from robot_copilot.site import load_site, resolve_place
from pathlib import Path
site = load_site(Path('config/sites/demo_farm.toml'))
print(resolve_place(site, 'the barn').name)
" """,
        ["Barn"],
        "Add a temporary alias on Pond, chat with it, then revert and rerun site tests.",
        ["tests/unit/test_site.py::test_normalize_and_resolve"],
    ),
    _chapter(
        "03-plan-schema.md",
        "03 Plan schema and validation entry",
        "typed actions",
        [
            "MissionPlan bundles vehicle, summary, and an ordered action list validated by Pydantic models.",
            "ChatRequest carries conversation id, user text, vehicle choice, and battery percent into orchestrator.chat.",
            "Goto actions require exactly one of place or xy, preventing ambiguous targets from reaching spatial code.",
            "Takeoff and land actions include altitudes vetted later against vehicle profiles and structure rules.",
            "Hover seconds must be positive floats; photo actions optionally carry human labels for playback markers.",
            "return_home terminates sequences and triggers energy return legs independent of explicit land commands.",
            "Raw JSON schema tests lock provider tool shapes so cloud models cannot invent new action types silently.",
            "validate orchestrates structure, spatial, and energy passes, accumulating Issue objects with stable codes.",
            "ValidationContext threads site, geometry, vehicle profile, and battery percentage through each pass.",
            "Reports include ok flag, issues, resolved plan, stats, and plan_hash used by confirmation and simulation.",
            "Decline tools capture provider refusals before a MissionPlan exists, mapping to kind decline responses.",
            "Repair context reuses the same schema with issue briefs fed back into provider prompts.",
            "Plan hashes cover canonical JSON so single-field edits change confirmation requirements predictably.",
            "Structure rules encode allowed action sequences per vehicle, rejecting rover takeoff early.",
            "Spatial rules consume resolved coordinates after place expansion and path indexing.",
            "Energy rules estimate watt-hours using speeds and hover draws from vehicle.toml parameters.",
            "Explanations read the same issue codes produced here, keeping UI copy aligned with validator truth.",
            "Understanding this entrypoint clarifies why provider output still requires deterministic gatekeeping.",
        ],
        [
            "src/robot_copilot/schemas.py",
            "src/robot_copilot/plan.py",
            "src/robot_copilot/validator/__init__.py",
            "tests/unit/test_plan_schema.py",
        ],
        [
            (
                "ChatRequest is the HTTP-facing contract mirroring POST /api/chat bodies validated before orchestrator work.",
                0,
                "Optional conversation_id lets browsers continue threads while generation counters protect against stale writes.",
            ),
            (
                "validate is the single front door for deterministic checks; orchestrator never reimplements geometry math inline.",
                1,
                "Downstream simulator and explanation modules consume ValidationReport objects emitted here.",
            ),
        ],
        """RCC_DOTENV=off uv run --no-sync python -c "
from pydantic import ValidationError
from robot_copilot.plan import Goto, XY
try:
    Goto(type='goto', place='Barn', xy=XY(x_m=1,y_m=2))
except ValidationError as e:
    print(e.errors()[0]['msg'])
" """,
        ["Value error, exactly one of place or xy required"],
        "Build a rover MissionPlan containing takeoff in a REPL and note the structure issue code.",
        ["tests/unit/test_plan_schema.py::test_raw_json_schema_errors"],
    ),
    _chapter(
        "04-mock-provider.md",
        "04 Mock LLM provider",
        "deterministic proposals",
        [
            "MockProvider implements propose without network IO, enabling offline CI and classroom laptops alike.",
            "_canonical_place maps noisy operator strings onto canonical site names using SiteSummary aliases.",
            "_inspect_place expands path places into repeated goto-hover-photo sequences at optional altitudes.",
            "Regex handlers cover patrol loops, photos, hover timers, keep-out flyovers, and simple goto commands.",
            "Patrol plans wrap perimeter vertices with takeoff and return_home for drones but not rovers.",
            "Decline paths trigger when regex detects unsupported payload verbs like drop or spray.",
            "Repair mode rewrites plans using structured issue briefs rather than echoing full prior JSON.",
            "Normalization pipeline validates tool args sizes and required fields before orchestrator commits missions.",
            "Photo intents normalize to goto place plus hover dwell then photo action for drones.",
            "Keep-out flyovers may synthesize goto xy inside forbidden regions to teach spatial failures.",
            "Site summary tools expose place counts so prompts stay compact for real providers too.",
            "Mock model id flows into audit metadata identical to cloud providers for uniform dashboards.",
            "Provider results distinguish text, plan, and decline kinds consumed by orchestrator._commit_chat.",
            "Tool specs declare JSON schemas shared with Anthropic and OpenAI adapters in later chapters.",
            "Uppercase aliases like BARN should still resolve to Barn thanks to normalize_name in canonicalization.",
            "Tests lock regex behavior so tutorial phrases in README stay synchronized with validator expectations.",
            "Understanding mock routing helps you debug chat flows before spending cloud tokens.",
            "This provider is not a toy; it encodes the same tool contracts production models must honor.",
        ],
        [
            "src/robot_copilot/llm/mock.py",
            "src/robot_copilot/llm/normalize.py",
            "src/robot_copilot/tools.py",
            "tests/unit/test_mock_provider.py",
        ],
        [
            (
                "_canonical_place iterates summary places and aliases, returning the canonical name when normalization matches.",
                0,
                "When lookup fails, raw text flows through so unknown_place issues can still be diagnosed clearly.",
            ),
            (
                "_inspect_place counts path vertices from the summary, emitting per-point gotos and inspection photos.",
                1,
                "Optional altitude_m parameters attach to goto actions for fence inspections at specified heights.",
            ),
        ],
        """RCC_DOTENV=off uv run --no-sync python -c "
from pathlib import Path
from robot_copilot.site import load_site
from robot_copilot.tools import build_site_summary
from robot_copilot.vehicles import load_vehicles
from robot_copilot.llm.mock import _canonical_place
site = load_site(Path('config/sites/demo_farm.toml'))
vehicles = load_vehicles(Path('config/vehicles.toml'))
summary = build_site_summary(site, vehicles['drone'])
print(_canonical_place(summary, 'BARN'))
" """,
        ["Barn"],
        "Send patrol the perimeter twice and count goto actions before return_home.",
        ["tests/api/test_name_resolution.py::test_barn_aliases_resolve_in_mock_plans"],
    ),
]

# Append remaining chapters in second part - use exec from file continuation
# For maintainability the rest is loaded from tutorial_chapter_defs_extra.json if present

EXTRA_DEFS_PATH = Path(__file__).with_name("tutorial_chapter_defs_extra.json")


def _render_chapter(defn: dict, cache: dict) -> str:
    fname = defn["fname"]
    segs = cache[fname]
    goal = goal_for_chapter(defn)
    files_md = "\n".join(f"- `{f}`" for f in defn["files"])
    walk_parts: list[str] = ["## Walkthrough", ""]
    for n, (intro, seg_idx, outro) in enumerate(defn["walkthrough"], start=1):
        seg = segs[seg_idx]
        walk_parts.append(f"{n}. {intro}")
        walk_parts.append("")
        walk_parts.append(_segment_fence(seg["rel"], seg["qualname"], seg["text"]))
        walk_parts.append(outro)
        walk_parts.append("")
    exercise = defn["exercise"]
    checkpoint = "\n".join(f"- `{c}`" for c in defn["checkpoint"])
    return (
        f"# {defn['title']}\n\n"
        f"## Goal\n\n{goal}\n\n"
        f"## Files\n\n{files_md}\n\n"
        f"{chr(10).join(walk_parts)}"
        f"{_try_section(defn['try_bash'], defn['try_expected'], defn.get('try_note', ''))}\n"
        f"## Exercise\n\n{exercise}\n\n"
        f"## Checkpoint\n\n{checkpoint}\n"
    )


def _load_extra_defs() -> list[dict]:
    if not EXTRA_DEFS_PATH.exists():
        return []
    return json.loads(EXTRA_DEFS_PATH.read_text())


def regenerate() -> None:
    cache = json.loads(CACHE.read_text())
    try_expected: dict[str, dict] = {}
    all_defs = CHAPTER_DEFS + _load_extra_defs()
    assert len(all_defs) == 17, f"expected 17 chapters, got {len(all_defs)}"
    used_ranges: set[tuple[str, int, int]] = set()
    for defn in all_defs:
        fname = defn["fname"]
        for seg in cache[fname]:
            seg_obj = extract_segment(ROOT, seg["rel"], seg["qualname"])
            assert_segment_rules(seg_obj)
            key = (seg["rel"], seg_obj.lineno, seg_obj.end_lineno)
            assert key not in used_ranges, f"overlap {key}"
            used_ranges.add(key)
            assert seg_obj.text == seg["text"]
        text = _render_chapter(defn, cache)
        (TUTORIAL / fname).write_text(text)
        try_expected[fname] = {"expected_lines": defn["try_expected"]}
    TRY_EXPECTED.write_text(json.dumps(try_expected, indent=2) + "\n")


if __name__ == "__main__":
    regenerate()
