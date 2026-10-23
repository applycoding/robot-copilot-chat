# 15 Testing, Docker, and CI

## Goal

You are reading tutorial chapter 15 about harness and hygiene in robot-copilot-chat. Chapter 15 links harness and hygiene to validators, confirmation hashes, and local simulation gates. Learning note 15-1: scrub_env fixture removes provider API keys so tests fail closed when env leaks occur. Learning note 15-2: Orchestrator.__init__ builds asyncio semaphores from settings.provider_concurrency defaults. Learning note 15-3: Farm day scenario tests replay JSON transcripts against live FastAPI apps without manual clicking. Learning note 15-4: Property tests mutate valid plans to match analytic oracle expectations across validator modules. Learning note 15-5: Socket guards detect accidental outbound connections during provider unit tests. Learning note 15-6: Playwright smoke tests use free ports and per-run SQLite paths to avoid shard collisions. Learning note 15-7: CI pins Dockerfile base images with immutable hashes commented for reproducibility. Learning note 15-8: Hygiene tests grep static JavaScript for innerHTML assignments and inline script patterns. Learning note 15-9: Tutorial walkthrough tests validate prose length, excerpt overlap, and try-it commands automatically. Learning note 15-10: RCC_DOTENV off is standard for pytest and documentation commands to ignore developer secrets. Learning note 15-11: conftest load_ctx fixtures build ValidationContext objects shared by unit and integration suites. Learning note 15-12: Docker builds package uv environments matching lockfiles committed beside pyproject.toml. Learning note 15-13: Scenario tests assert HTTP 409 patterns for stale confirms and repair limits using real clients. Learning note 15-14: Regression guards encode product decisions like battery messaging parameters expected in UI. Learning note 15-15: Repo tests ensure tutorial python excerpts map to whole AST nodes between ten and sixty lines. Learning note 15-16: Parallel CI assumes provider concurrency four unless settings tests prove otherwise. Learning note 15-17: Testing chapters should be read before attempting to modify GitHub workflow pins. Learning note 15-18: Students ought to run tutorial checkpoint nodes after each chapter to confirm understanding.

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
