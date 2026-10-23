"""Unique Goal-section prose for tutorial chapters (no shared template sentences)."""

from __future__ import annotations

GOAL_INTROS: dict[str, str] = {
    "00-overview.md": (
        "Robot copilot chat turns natural language into simulated farm missions only after a fixed "
        "chain of deterministic gates. This overview chapter names each gate in order so you can "
        "explain the safety model to reviewers without opening every module. Redaction runs before "
        "guards, validation runs before confirmation, and simulation runs only on hashed plans "
        "the operator already accepted."
    ),
    "01-skeleton.md": (
        "FastAPI boots a single SQLite-backed application where chat, confirmation, and repair share "
        "one orchestrator and one store. This chapter follows persistence seams: how monotonic string "
        "ids survive restarts, how missions and runs relate, and why the mock provider is wired before "
        "routes go live. You will see where chat responses pick up kind plan versus kind help."
    ),
    "02-site-config.md": (
        "Every validator and map overlay reads the same demo farm loaded from TOML. Here you learn how "
        "place names normalize, how aliases resolve informal operator text, and why polygon validation "
        "fails fast when a site file is inconsistent. Path places such as North Fence matter later "
        "for inspect loops, patrol geometry, and simulator frame counts."
    ),
    "03-plan-schema.md": (
        "Mission plans are typed Pydantic models, not loose JSON blobs. This chapter connects HTTP "
        "ChatRequest bodies to validate, the single entry for structure, spatial, and energy passes. "
        "You will see why mutually exclusive fields like place versus xy are rejected at parse time "
        "and how issue codes stay stable for explanations and repair briefs."
    ),
    "04-mock-provider.md": (
        "The mock LLM provider proposes tool calls with zero network traffic, which keeps CI and "
        "classroom laptops reliable. You will trace regex routing from operator phrases to MissionPlan "
        "actions, including patrol, photo, and keep-out flyover demos. Canonical place lookup shares "
        "normalization with the site loader so BARN and the barn mean the same Barn target."
    ),
    "05-validator-structure.md": (
        "Structure validation is the first deterministic pass after a plan parses. It enforces "
        "vehicle-specific action sequences before any coordinates are computed. Rover takeoff is the "
        "classic teaching failure: ground vehicles cannot enter the flight state table used for "
        "drones. Issues carry action_index so the UI and explain templates cite the same step numbers."
    ),
    "06-validator-spatial.md": (
        "Spatial checks expand named places into segments, then test geofence margins and keep-out "
        "volumes along each leg and along return-home shortcuts. The substation flyover chat phrase "
        "exists to produce enters_keep_out together with rth_path_blocked in one invalid mission. "
        "Understanding segment helpers clarifies why map previews can look fine while validation still fails."
    ),
    "07-validator-energy.md": (
        "Energy validation estimates watt-hours for mission legs plus conservative return-home legs "
        "using speeds and hover draws from vehicle profiles. Patrol loops multiply perimeter distance, "
        "so four laps at forty percent battery should fail with battery_insufficient before an operator "
        "confirms. Reserve watt-hours stay unavailable for outbound travel, mirroring real pack margins."
    ),
    "08-explanations.md": (
        "Validators emit IssueCode values and param dicts; explanations turn those into operator "
        "sentences and short remediation hints. Templates use Python format placeholders filled per "
        "issue instance, and step prefixes derive from action_index for multi-step plans. "
        "describe_plan composes visit summaries used in confirmation copy and playback titles."
    ),
    "09-simulator.md": (
        "Simulation consumes only ok validation reports, then emits frames for map playback and run "
        "JSON stored after confirm. Frame counts depend on ceil(duration/dt) semantics, so North "
        "Fence inspect plans produce hundreds of frames rather than a toy forty-two step guess. "
        "Final state aggregates landed flags and battery for summaries shown beside the timeline."
    ),
    "10-confirmation.md": (
        "Confirmation is compare-and-swap on plan_hash: clients must POST the hash shown with a valid "
        "mission or the API returns 409 plan_hash_mismatch without creating a run row. Orchestrator "
        "_confirm checks mission status, generation counters, and TTL before simulate runs. This "
        "chapter ties store commits to audit events so double confirms do not duplicate execution."
    ),
    "11-repair-loop.md": (
        "Invalid missions can enter a bounded repair loop where the provider sees structured issue "
        "briefs instead of raw validator dumps. Orchestrator.repair reserves attempts with optimistic "
        "concurrency, and provider failures still consume budget via commit_repair_failure. Provider "
        "calls share the asyncio semaphore sized from settings.provider_concurrency, which "
        "tests/unit/test_settings.py asserts defaults to four alongside the mock provider."
    ),
    "12-web-ui-and-hardening.md": (
        "The browser client is plain modules served from FastAPI, while RequestGuardMiddleware rejects "
        "bad hosts, bad origins, oversize bodies, and unexpected content types before route code runs. "
        "Chunked uploads return 413 without draining the socket, which matters for slowloris-style "
        "abuse in classroom deployments. Chat JavaScript clears map overlays when responses are help "
        "text or lack a mission so stale paths never linger."
    ),
    "13-anthropic-openai.md": (
        "Cloud providers wrap vendor SDKs but return the same ProviderResult shapes as the mock. "
        "Anthropic and OpenAI adapters map tool calls into propose and decline flows validated by "
        "orchestrator commits. Unit tests inject fake HTTP transports so CI never opens outbound "
        "sockets while still asserting tool-use plans parse correctly."
    ),
    "14-gemini-xai.md": (
        "build_provider selects Gemini or xAI implementations from settings while reusing shared tool "
        "specs and normalize helpers. Gemini contract tests validate client configuration fields "
        "without calling live Google APIs. xAI reuses OpenAI client patterns with a different base URL "
        "and model identifiers, keeping registry growth explicit and testable."
    ),
    "15-testing-docker-ci.md": (
        "pytest layout separates unit, API, provider, scenario, and Playwright smoke tiers. scrub_env "
        "fixtures strip API keys so tests fail closed when environment leaks occur. Farm day scenario "
        "tests replay JSON transcripts against a real app instance, while hygiene tests grep static "
        "assets for inline handlers and docker pins document immutable base images."
    ),
    "16-extending.md": (
        "Extending the stack means updating schemas, validators, simulator motion, mock regex routes, "
        "and tool_specs together so providers cannot invent silent new action types. build_site_summary "
        "compresses places for prompts without dumping full coordinate lists. Demo farm consistency "
        "tests lock patrol calibration so README phrases and tutorial Try it commands stay truthful."
    ),
}


def goal_for_chapter(defn: dict) -> str:
    return GOAL_INTROS[defn["fname"]]
