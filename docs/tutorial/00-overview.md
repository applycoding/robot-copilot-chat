# 00 Project overview and safety model

## Goal

You are reading tutorial chapter 00 about redaction and the safety envelope in robot-copilot-chat. Chapter 00 links redaction and the safety envelope to validators, confirmation hashes, and local simulation gates. Learning note 00-1: Redaction runs before request guards so provider stack traces never echo API keys copied from dotenv files. Learning note 00-2: The mock provider is default, yet settings still load optional cloud keys for experiments you run locally. Learning note 00-3: Validators are pure functions over typed plans; they never call models or mutate SQLite rows directly. Learning note 00-4: Human confirmation binds to a SHA-256 plan hash so tampered JSON cannot execute after review. Learning note 00-5: Simulation consumes validated reports only, which prevents guessing physics from draft provider output. Learning note 00-6: Audit events record confirm, repair, and decline transitions for later forensics in teaching demos. Learning note 00-7: Static assets ship from FastAPI, while JSON APIs power the browser chat and playback widgets. Learning note 00-8: Configuration merges TOML defaults with environment overrides through a single settings loader. Learning note 00-9: Issue codes are stable enums so explanations, repairs, and UI badges stay aligned across releases. Learning note 00-10: Keep-out polygons and geofences come from site TOML consumed by spatial checks and map rendering. Learning note 00-11: Energy checks include return-home legs because battery failures often appear only on the way back. Learning note 00-12: Repair loops cap attempts so runaway provider failures cannot spam tokens during classroom sessions. Learning note 00-13: Concurrency limits on provider calls protect SQLite from thrashing when many students chat at once. Learning note 00-14: The health endpoint advertises provider name and site title so operators know which world loaded. Learning note 00-15: pytest runs with RCC_DOTENV off in docs so tutorials do not depend on your private secrets file. Learning note 00-16: Docker and CI pins appear later; this chapter only orients you to the safety ordering of components. Learning note 00-17: When chat returns help text, the UI should clear map overlays so stale paths never mislead operators. Learning note 00-18: Portfolio reviewers expect you to articulate each gate between natural language and simulated motion.

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
