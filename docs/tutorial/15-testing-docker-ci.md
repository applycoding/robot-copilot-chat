# 15 Testing, Docker, and CI

Tests are layered: pure validator units, API integration with `TestClient`, property fuzzing against `oracle.py`, provider contract tests with mock transports, the farm-day golden scenario, and Playwright e2e against a real browser. `conftest.py` installs an autouse socket guard that blocks outbound TCP except loopback, preventing accidental network during pytest.

Environment scrubbing removes API keys and stray `RCC_*` variables before subprocess tutorial checks run.

Farm-day golden compares quantized DB snapshots including audit kind order and frame sha256. Playwright e2e runs in CI with a live uvicorn fixture. Docker smoke builds the image and curls `/healthz` to ensure packaging includes site config and static assets.

## Files

- `tests/conftest.py`
- `tests/scenario/test_farm_day.py`
- `tests/repo/test_ci_pins.py`
- `Dockerfile`

```python
@pytest.fixture(autouse=True)
def _socket_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def guarded_connect(self, address):  # type: ignore[no-untyped-def]
        host = address[0] if isinstance(address, tuple) else address
        if (
            isinstance(host, str)
            and host not in ("127.0.0.1", "localhost", "::1")
            and not str(host).startswith("/")
        ):
            raise AssertionError(f"Outbound network blocked: {host}")
        return real_connect(self, address)
```

CI runs ruff, mypy on `src`, pytest (e2e excluded by default marker), Playwright, Docker smoke, and gitleaks with SHA-pinned GitHub Actions.



This chapter ties to the integration story in `tests/scenario/farm_day.json`: replay those steps after reading so you see how testing-docker-ci behaves inside a long conversation with repairs, declines, and confirmations. Cross-check any prose claims against `PLAN.md` criterion numbers when you are preparing a portfolio review.
## Exercise

Run `uv run --no-sync pytest tests/scenario/test_farm_day.py -q` and note how many executed runs the scenario expects.

## Checkpoint

- `tests/scenario/test_farm_day.py::test_farm_day_scenario`
