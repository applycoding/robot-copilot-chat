# 00 Project overview and safety model

Robot Copilot Chat is a teaching application: a language model proposes structured missions, a deterministic validator accepts or rejects them, and a human operator confirms before a local simulator runs. The default stack uses a mock provider so laptops and CI never need API keys. The product goal is not autonomy; it is an auditable loop you can reason about.

Safety is enforced in layers. Network exposure is loopback-only. `RequestGuardMiddleware` rejects wrong hosts, origins, media types, and oversized bodies before route handlers run. Secrets are stripped from logs and audit payloads. Confirmation binds execution to a SHA-256 plan hash and a TTL so edited or stale plans cannot run silently.

Redaction is configured at startup from the optional API key:

Operators should treat the UI mock banner as a first-class safety signal: when `RCC_PROVIDER=mock`, no outbound model traffic occurs. Conversation history is bounded (`history_turns` in settings) so prompts stay small. Mission status values (`valid`, `invalid`, `repairing`, `declined`, `executed`) are enumerated in `schemas.py` and mirrored in the mission card. Understanding those states makes the farm-day scenario readable as an integration test rather than a mysterious script.

## Files

- `src/robot_copilot/redact.py`
- `src/robot_copilot/security.py`
- `config/app.toml`

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

Read `config/app.toml` for `allowed_hosts`, `max_body_bytes`, and `confirm_ttl_s`. These defaults are what the README rules table documents.

## Exercise

Start the app locally, open `/`, and confirm the mock banner is visible. Send `hello` and verify you get help text without creating a mission row in SQLite.

## Checkpoint

- `tests/api/test_healthz.py::test_healthz`
