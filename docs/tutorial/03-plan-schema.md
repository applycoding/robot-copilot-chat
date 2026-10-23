# Mission plan schema

## Goal

Work through **mission plan schema** with the real robot-copilot-chat sources open beside this page.

## Concepts

- Typed plans, validator authority, and human confirmation before simulation.
- Chapter focus: mission plan schema.

## Files

- `src/robot_copilot/main.py`
- `PLAN.md` (normative behavior)

## Run it

```bash
uv sync --locked
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --host 127.0.0.1 --port 8000
```


Plans are Pydantic models with `extra=forbid` so providers cannot smuggle unknown keys. Actions are a closed union: takeoff, goto, hover, photo, land, return_home. Coordinates may reference named places or explicit `xy` pairs.

The chat request schema strips whitespace and rejects empty messages at validation time (HTTP 422), which keeps orchestrator code free of ad-hoc string checks:

```python
class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=2000)
    vehicle: VehicleKind = "drone"
    battery_pct: int = Field(default=100, ge=1, le=100)

    @field_validator("message")
    @classmethod
    def _strip_message(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("message must not be empty or whitespace only")
        return s
```

`summary` is display-only; confirmation always uses the canonical plan JSON and hash.

## Exercise

Craft an invalid plan JSON missing `return_home` and run it through `validate` in a REPL. Read the `MUST_END_AT_HOME` issue.

## Checkpoint

```bash
uv run --no-sync pytest tests/unit/test_plan_schema.py -q
```
## Exercises

Apply the checkpoint below, then read on.

## What to notice in the codebase

Keep a scratch log while you work: file paths, function names, and the pytest node ids you ran. When something surprises you (for example a 409 conflict or a clipped map polyline), capture the HTTP status, mission status, and audit kinds from SQLite. The tutorial checkpoints are intentionally narrow so you can run them quickly, but the real learning comes from comparing your local traces with the farm-day golden audit sequence and the validator issue templates in `explain.py`. If you change behavior, update both tests and the matching tutorial chapter so the next reader inherits an accurate story.

Re-run `scripts/build_tutorials.py` after editing cited excerpts so line numbers stay honest, or update the script literals when you move code. Pair each chapter with one manual UI action (send a chat, repair once, confirm) so you see the same statuses the API tests assert.
