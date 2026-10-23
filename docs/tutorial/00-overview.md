# 00 Project overview and safety model

## Goal

Robot copilot chat turns natural language into simulated farm missions only after a fixed chain of deterministic gates. This overview chapter names each gate in order so you can explain the safety model to reviewers without opening every module. Redaction runs before guards, validation runs before confirmation, and simulation runs only on hashed plans the operator already accepted.

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
