# Application skeleton and routing

## Goal

Work through **application skeleton and routing** with the real robot-copilot-chat sources open beside this page.

## Concepts

- Typed plans, validator authority, and human confirmation before simulation.
- Chapter focus: application skeleton.

## Files

- `src/robot_copilot/main.py`
- `PLAN.md` (normative behavior)

## Run it

```bash
uv sync --locked
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --host 127.0.0.1 --port 8000
```


The ASGI entry point is `create_app` in `main.py`. It loads TOML settings, builds immutable site and vehicle profiles, opens SQLite through `Store`, and mounts static assets plus the API router. Dependency injection hooks (`provider`, `clock`, `id_factory`) exist so tests can swap the LLM and time without touching production code.

Routes live in `api.py`. Chat, repair, confirm, and read-only mission endpoints all delegate to `Orchestrator` methods rather than embedding business rules in handlers:

```python
    @router.post("/api/chat", response_model=ChatResponse)
    async def chat(body: ChatRequest) -> ChatResponse:
        from robot_copilot.llm.base import ProviderError

        try:
            return await orchestrator.chat(body)
        except ConflictError as exc:
            raise _conflict(exc) from exc
        except ProviderError:
            return ChatResponse(
                conversation_id=body.conversation_id or "",
                kind="error",
                assistant_message="The AI provider is unavailable; no plan was created.",
                mission=None,
            )
```

Notice how provider failures return a structured chat response instead of a bare 500, keeping the UI conversational while still failing closed on validation.

## Exercise

Add a temporary log line in `healthz` and confirm `/healthz` still returns the configured site name. Remove the log before committing.

## Checkpoint

```bash
uv run --no-sync pytest tests/api/test_healthz.py -q
```
## Exercises

Apply the checkpoint below, then read on.

## What to notice in the codebase

Keep a scratch log while you work: file paths, function names, and the pytest node ids you ran. When something surprises you (for example a 409 conflict or a clipped map polyline), capture the HTTP status, mission status, and audit kinds from SQLite. The tutorial checkpoints are intentionally narrow so you can run them quickly, but the real learning comes from comparing your local traces with the farm-day golden audit sequence and the validator issue templates in `explain.py`. If you change behavior, update both tests and the matching tutorial chapter so the next reader inherits an accurate story.

Re-run `scripts/build_tutorials.py` after editing cited excerpts so line numbers stay honest, or update the script literals when you move code. Pair each chapter with one manual UI action (send a chat, repair once, confirm) so you see the same statuses the API tests assert.
