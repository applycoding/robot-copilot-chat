# robot-copilot-chat

[![CI](https://github.com/applycoding/robot-copilot-chat/actions/workflows/ci.yml/badge.svg)](https://github.com/applycoding/robot-copilot-chat/actions/workflows/ci.yml)
![MIT](https://img.shields.io/badge/license-MIT-blue)
![Python 3.13](https://img.shields.io/badge/python-3.13-blue)

Plain English → validated, human-confirmed mission plans for a simulated drone or rover.

**Portfolio demo and tutorial project** — simulation only, loopback-only, **not flight-tested** and not intended for real aircraft or robots.

## Screenshot

![Plan](docs/screenshots/01-plan.png)

![Repair](docs/screenshots/02-repair.png)

![Executing](docs/screenshots/03-executing.png)

## Safety model

- The LLM only proposes structured plans via tools.
- The deterministic validator is the only safety gate.
- A human confirms before any simulated execution.
- Simulation replays validated legs locally; it never commands real hardware.
- The return-home path check is a **demo heuristic**, not a safety guarantee.

## Quickstart (60 seconds)

```bash
git clone https://github.com/applycoding/robot-copilot-chat && cd robot-copilot-chat
uv sync --locked
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --reload
```

Open http://localhost:8000. No API keys required. Loopback only.

## Try these phrases

| Phrase | Outcome |
|---|---|
| inspect the north fence | valid plan |
| survey the pond at 150 m | invalid → repair to 120 m |
| fly to the neighbor's house | unknown place |
| fly over the substation | keep-out |
| patrol the perimeter four times (40% battery) | battery repair |
| fly to the pond at 30 m (rover) | vehicle mismatch → repair |
| drop the payload on the barn | decline |

## Docker

```bash
docker build -t robot-copilot-chat .
docker run -p 127.0.0.1:8000:8000 -v rcc-data:/app/data robot-copilot-chat
```

Publish on loopback only.

## Use a real LLM

Copy `.env.example` to `.env`. Set `RCC_PROVIDER` and the matching key. Models live in `config/app.toml`.

## Architecture

See [docs/architecture.md](docs/architecture.md).

## Safety rules

| Rule | Config | Default |
|---|---|---|
| Geofence inset | site TOML | 5 m |
| Keep-out buffers | site TOML | per zone |
| Max altitude | vehicles TOML | 120 m |
| Host allowlist | app.toml | localhost |
| JSON-only POST | middleware | enforced |

## Configure your own site

See annotated TOML under `config/sites/demo_farm.toml`.

## Project layout

See `PLAN.md` §4.

## Testing

```bash
uv sync --locked
uv run --no-sync pytest
UPDATE_GOLDEN=1 uv run --no-sync pytest tests/scenario/test_farm_day.py::test_farm_day_golden
```

## CI

Lint, typecheck, unit/property/scenario tests, Playwright e2e, Docker smoke. SHA-pinned actions, no API keys in CI.

## Tutorial

Chapters [00–16](docs/tutorial/00-overview.md).

## Out of scope / disclaimer

This repository is a **portfolio and teaching demo**: it shows how to gate LLM proposals with a deterministic validator and human confirmation before replaying a plan in software. It has **not** been validated for real flight or field robotics. Do not use it to command hardware, and do not expose it beyond localhost.

## License and author

MIT © 2026 [Arpan Bom](https://applycoding.com) — [@applycoding](https://github.com/applycoding)
