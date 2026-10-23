# 00 Project overview and safety model

## Goal

Robot copilot chat turns natural language into simulated farm missions only after a fixed chain of deterministic gates. This overview chapter names each gate in order so you can explain the safety model to reviewers without opening every module. Redaction runs before guards, validation runs before confirmation, and simulation runs only on hashed plans the operator already accepted.

Redaction runs before request guards so provider stack traces never echo API keys copied from dotenv files. The mock provider is default, yet settings still load optional cloud keys for experiments you run locally. Validators are pure functions over typed plans; they never call models or mutate SQLite rows directly.

Human confirmation binds to a SHA-256 plan hash so tampered JSON cannot execute after review. Simulation consumes validated reports only, which prevents guessing physics from draft provider output. Audit events record confirm, repair, and decline transitions for later forensics in teaching demos.

Static assets ship from FastAPI, while JSON APIs power the browser chat and playback widgets. Configuration merges TOML defaults with environment overrides through a single settings loader. Issue codes are stable enums so explanations, repairs, and UI badges stay aligned across releases.

Keep-out polygons and geofences come from site TOML consumed by spatial checks and map rendering. Energy checks include return-home legs because battery failures often appear only on the way back. Repair loops cap attempts so runaway provider failures cannot spam tokens during classroom sessions.

Concurrency limits on provider calls protect SQLite from thrashing when many students chat at once. The health endpoint advertises provider name and site title so operators know which world loaded. pytest runs with RCC_DOTENV off in docs so tutorials do not depend on your private secrets file.

Docker and CI pins appear later; this chapter only orients you to the safety ordering of components. When chat returns help text, the UI should clear map overlays so stale paths never mislead operators. Portfolio reviewers expect you to articulate each gate between natural language and simulated motion.

## Files

- `src/robot_copilot/redact.py`
- `src/robot_copilot/security.py`
- `config/app.toml`
- `src/robot_copilot/main.py`

## Walkthrough

1. Begin with `redact_text`, which scrubs configured secrets and sensitive headers from arbitrary strings.

<!-- segment: src/robot_copilot/redact.py redact_text -->

```python
def redact_text(text: str) -> str:
    out = text
    for secret in _secrets:
        if secret:
            out = out.replace(secret, "[REDACTED]")
    for hdr in SENSITIVE_HEADERS:
        pattern = re.compile(
            rf"({re.escape(hdr)}:\s*)([^\r\n]+)",
            re.IGNORECASE,
        )
        out = pattern.sub(r"\1[REDACTED]", out)
    return out
```

Logging hooks call this helper so bearer tokens in misconfigured clients do not reach stderr during failures.
## Try it

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

### Expected

```
200 ok mock Applycoding Demo Farm
```

## Exercise

Write three sentences: what validators may change, what confirmation guarantees, and what simulation assumes about hashes.

## Checkpoint

- `tests/api/test_healthz.py::test_healthz`
