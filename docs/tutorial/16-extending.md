# 16 Extending the stack

To add a vehicle profile, extend `config/vehicles.toml` and teach structure and energy modules about any new limits. To add a provider, implement `LLMProvider`, register it in `llm/registry.py`, and add contract tests that mirror existing vendors. UI changes should keep map fitting and playback reset logic aligned so operators still see faithful geography after edits.

Prefer new `Store` methods over reaching into private SQLAlchemy engines from orchestrator code.

New audit kinds should be documented in PLAN.md and reflected in scenario golden files when behavior changes. Feature flags belong in settings, not ad hoc environment reads scattered through handlers. Keep orchestrator methods small enough to test with `TestClient` and fake providers without booting a browser.

## Files

- `src/robot_copilot/llm/registry.py`
- `src/robot_copilot/llm/base.py`
- `src/robot_copilot/store.py`
- `PLAN.md`

```python
def build_provider(settings: AppSettings) -> LLMProvider:
    if settings.provider == ProviderName.MOCK:
        return MockProvider(settings.model)
    if settings.provider == ProviderName.ANTHROPIC:
        from robot_copilot.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            settings.model,
            settings.api_key,  # type: ignore[arg-type]
            timeout_s=settings.request_timeout_s,
            max_retries=settings.sdk_max_retries,
            max_output_tokens=settings.max_output_tokens,
        )
```

When you change persistence or audit semantics, update farm-day golden expectations and the matching tutorial chapter checkpoints.



This chapter ties to the integration story in `tests/scenario/farm_day.json`: replay those steps after reading so you see how extending behaves inside a long conversation with repairs, declines, and confirmations. Cross-check any prose claims against `PLAN.md` criterion numbers when you are preparing a portfolio review.
## Exercise

Sketch a decline category for a new unsupported verb and add a mock matcher plus a unit test expecting `kind=decline`.

## Checkpoint

- `tests/unit/test_mock_provider.py`
