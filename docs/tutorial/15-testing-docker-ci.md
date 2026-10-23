# 15 Testing, Docker, and CI

## Goal

pytest layout separates unit, API, provider, scenario, and Playwright smoke tiers. scrub_env fixtures strip API keys so tests fail closed when environment leaks occur. Farm day scenario tests replay JSON transcripts against a real app instance, while hygiene tests grep static assets for inline handlers and docker pins document immutable base images.

scrub_env fixture removes provider API keys so tests fail closed when env leaks occur. Orchestrator.__init__ builds asyncio semaphores from settings.provider_concurrency defaults. Farm day scenario tests replay JSON transcripts against live FastAPI apps without manual clicking.

Property tests mutate valid plans to match analytic oracle expectations across validator modules. Socket guards detect accidental outbound connections during provider unit tests. Playwright smoke tests use free ports and per-run SQLite paths to avoid shard collisions.

CI pins Dockerfile base images with immutable hashes commented for reproducibility. Hygiene tests grep static JavaScript for innerHTML assignments and inline script patterns. Tutorial walkthrough tests validate prose length, excerpt overlap, and try-it commands automatically.

RCC_DOTENV off is standard for pytest and documentation commands to ignore developer secrets. conftest load_ctx fixtures build ValidationContext objects shared by unit and integration suites. Docker builds package uv environments matching lockfiles committed beside pyproject.toml.

Scenario tests assert HTTP 409 patterns for stale confirms and repair limits using real clients. Regression guards encode product decisions like battery messaging parameters expected in UI. Repo tests ensure tutorial python excerpts map to whole AST nodes between ten and sixty lines.

Parallel CI assumes provider concurrency four unless settings tests prove otherwise. Testing chapters should be read before attempting to modify GitHub workflow pins. Students ought to run tutorial checkpoint nodes after each chapter to confirm understanding.

## Files

- `tests/conftest.py`
- `src/robot_copilot/orchestrator.py`
- `tests/scenario/test_farm_day.py`
- `tests/repo/test_hygiene.py`

## Walkthrough

1. scrub_env deletes known API key environment variables before each test function runs.

<!-- segment: tests/conftest.py scrub_env -->

```python
def scrub_env(env: dict[str, str]) -> dict[str, str]:
    out = dict(env)
    for key in list(out):
        if key.endswith("_API_KEY"):
            out.pop(key, None)
        if key.startswith("RCC_") and key not in _KEEP_RCC:
            out.pop(key, None)
        if re.match(r"^(ANTHROPIC|OPENAI|GEMINI|GOOGLE|XAI)_", key):
            out.pop(key, None)
        if key.lower() in ("http_proxy", "https_proxy", "all_proxy", "no_proxy"):
            out.pop(key, None)
    out["RCC_DOTENV"] = "off"
    return out
```

This complements default_settings_env by ensuring no hidden dotenv restores cloud credentials mid-suite.

2. Orchestrator.__init__ stores provider semaphore sized by provider_concurrency from loaded settings.

<!-- segment: src/robot_copilot/orchestrator.py Orchestrator.__init__ -->

```python
    def __init__(
        self,
        provider: LLMProvider,
        store: Store,
        site: Site,
        geometry: SiteGeometry,
        vehicles: Mapping[VehicleKind, DroneProfile | RoverProfile],
        settings: AppSettings,
        clock: Callable[[], datetime],
    ) -> None:
        self._provider = provider
        self._store = store
        self._site = site
        self._geometry = geometry
        self._vehicles = vehicles
        self._settings = settings
        self._clock = clock
        self._locks: dict[str, asyncio.Lock] = {}
        self._sem = asyncio.Semaphore(settings.provider_concurrency)
```

tests/unit/test_settings.py asserts the default value four so tutorials and CI share the same expectation.
## Try it

```bash
RCC_DOTENV=off uv run --no-sync pytest tests/scenario/test_farm_day.py::test_farm_day_scenario -q --no-header
```

### Expected

```
1 passed
```

## Exercise

Run tests/repo/test_hygiene.py and note which pattern forbids inline scripts in static assets.

## Checkpoint

- `tests/scenario/test_farm_day.py::test_farm_day_scenario`
