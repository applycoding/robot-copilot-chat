# 00 Project overview and safety model

## Goal

You will learn the end-to-end safety story for robot-copilot-chat: who may propose a mission, who must validate it, and who must confirm before simulation runs. The repository is a teaching stack, not a flight-tested autopilot. Your outcome is a clear mental model you can defend in a portfolio review: typed plans, deterministic validation, human confirmation bound to a hash, and local simulation only after those gates pass.

## Files

- `src/robot_copilot/redact.py`
- `src/robot_copilot/security.py`
- `config/app.toml`
- `src/robot_copilot/main.py`

## Walkthrough

1. Start with secrets handling. Even mock mode may load an API key from the environment when you experiment with cloud providers, so the app configures redaction before serving traffic.

```python
def configure_redaction(api_key: SecretStr | None, extra_keys: list[str] | None = None) -> None:
    global _secrets
    _secrets = []
    if api_key is not None:
        _secrets.append(api_key.get_secret_value())
    if extra_keys:
        _secrets.extend(k for k in extra_keys if k)
    _secrets = [s for s in _secrets if s]
```

The list is rebuilt on startup rather than appended forever, which keeps tests that rotate keys predictable. Log filters and audit serialization call `redact_text` so provider failures never echo bearer tokens.

2. Open `security.py` and read `RequestGuardMiddleware`. It enforces allowed hosts, JSON-only POST bodies, origin checks, and a maximum body size before FastAPI parses JSON. Oversized chunked uploads return HTTP 413 without draining the rest of the stream, which closes the connection quickly under abuse.

3. Read `config/app.toml` next to the README rules table. Note `allowed_hosts`, `max_body_bytes`, and `confirm_ttl_s`. These defaults are what pytest guards in `tests/api/test_request_guard.py` and confirmation tests. Changing a limit without updating tests is a common review failure.

4. Skim `create_app` in `main.py` only far enough to see the order: load site and vehicles, open SQLite, build the orchestrator, mount static files, register routes, attach validation error handling, then wrap the app with the request guard. That ordering guarantees malformed JSON never reaches business logic and that static assets still serve for the browser UI.

5. Finally, open the browser UI once and read the mock banner copy. It reminds operators that the default provider does not call external APIs. The banner is not a substitute for validation, but it sets expectations during demos.

## Try it

From the repository root:

```bash
RCC_DOTENV=off uv run --no-sync python -c "
from fastapi.testclient import TestClient
from robot_copilot.main import create_app
from robot_copilot.settings import load_settings
from tests.helpers import default_settings_env
s = load_settings(env=default_settings_env(), dotenv_enabled=False)
r = TestClient(create_app(s), base_url='http://localhost').get('/healthz')
print(r.status_code, r.json()['status'], r.json()['provider'], r.json()['site'])
"
```

Expected (provider and site come from your settings):

```
200 ok mock Applycoding Demo Farm
```

## Exercise

Write three sentences in your own words: what the validator is allowed to do, what the human confirm step guarantees, and what the simulator is allowed to assume about the plan hash.

## Checkpoint

- `tests/api/test_healthz.py::test_healthz`
