# Site configuration and geometry

## Goal

Work through **site configuration and geometry** with the real robot-copilot-chat sources open beside this page.

## Concepts

- Typed plans, validator authority, and human confirmation before simulation.
- Chapter focus: site configuration.

## Files

- `src/robot_copilot/main.py`
- `PLAN.md` (normative behavior)

## Run it

```bash
uv sync --locked
uv run --no-sync uvicorn --factory robot_copilot.main:create_app --host 127.0.0.1 --port 8000
```


Sites are declarative TOML. `demo_farm.toml` defines home, a rectangular geofence, buffered keep-outs, and named places that may be points or paths. Aliases feed the mock provider and the validator's fuzzy name suggestions.

```
[site]
id = "demo-farm"
name = "Applycoding Demo Farm"
home = [0.0, 0.0]
geofence = [[-200,-150],[250,-150],[250,300],[-200,300]]
geofence_margin_m = 5.0

[[keep_out]]
name = "Substation"
polygon = [[-160,100],[-120,100],[-120,140],[-160,140]]
margin_m = 10.0

[[keep_out]]
name = "Beehives"
polygon = [[135,75],[165,75],[165,105],[135,105]]
margin_m = 10.0

[[places]]
name = "North Fence"
aliases = ["northern fence"]
kind = "path"
points = [[-180,280],[20,285],[230,280]]

[[places]]
name = "Perimeter"
aliases = ["fence line", "boundary"]
kind = "path"
points = [[-180,-130],[230,-130],[230,280],[-180,280],[-180,-130]]

[[places]]
name = "Barn"
kind = "point"
points = [[-90,60]]

[[places]]
name = "Pond"
kind = "point"
points = [[110,-50]]
```

`load_site` validates polygons, normalizes names, and computes a fingerprint used in plan hashing. `SiteGeometry` inflates keep-outs and shrinks the geofence so validation operates on safety margins, not raw fence lines.

## Exercise

Add a new point place with two aliases and write a one-line chat phrase the mock provider should understand. Run chat locally and confirm the place resolves.

## Checkpoint

```bash
uv run --no-sync pytest tests/unit/test_site.py -q
```
## Exercises

Apply the checkpoint below, then read on.

## What to notice in the codebase

Keep a scratch log while you work: file paths, function names, and the pytest node ids you ran. When something surprises you (for example a 409 conflict or a clipped map polyline), capture the HTTP status, mission status, and audit kinds from SQLite. The tutorial checkpoints are intentionally narrow so you can run them quickly, but the real learning comes from comparing your local traces with the farm-day golden audit sequence and the validator issue templates in `explain.py`. If you change behavior, update both tests and the matching tutorial chapter so the next reader inherits an accurate story.

Re-run `scripts/build_tutorials.py` after editing cited excerpts so line numbers stay honest, or update the script literals when you move code. Pair each chapter with one manual UI action (send a chat, repair once, confirm) so you see the same statuses the API tests assert.
