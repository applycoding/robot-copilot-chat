"""Constructive and fuzz plan generators for property tests."""

from __future__ import annotations

import random
from typing import Any


def fuzz_plan(rng: random.Random) -> dict[str, Any]:
    vehicle = rng.choice(["drone", "rover"])
    n = rng.randint(1, 45)
    actions: list[dict[str, Any]] = []
    if vehicle == "drone":
        actions.append({"type": "takeoff", "altitude_m": rng.uniform(-10, 200)})
    for _ in range(n):
        t = rng.choice(["goto", "hover", "photo", "land", "return_home"])
        if t == "goto":
            if rng.random() < 0.7:
                actions.append(
                    {
                        "type": "goto",
                        "place": rng.choice(
                            ["Barn", "Pond", "North Fence", "Perimeter", "Nowhere"]
                        ),
                        "point_index": rng.randint(0, 4),
                        "speed_mps": rng.uniform(0, 30),
                    }
                )
            else:
                actions.append(
                    {
                        "type": "goto",
                        "x_m": rng.uniform(-300, 400),
                        "y_m": rng.uniform(-300, 400),
                        "altitude_m": rng.uniform(-10, 200),
                    }
                )
        elif t == "hover":
            actions.append({"type": "hover", "seconds": rng.uniform(0, 300)})
        elif t == "photo":
            actions.append({"type": "photo"})
        elif t == "land":
            actions.append({"type": "land"})
        else:
            actions.append({"type": "return_home"})
    if not actions or actions[-1]["type"] != "return_home":
        actions.append({"type": "return_home"})
    return {"vehicle": vehicle, "summary": "fuzz", "actions": actions}


def constructive_valid_mission(rng: random.Random) -> dict[str, Any]:
    place = rng.choice(["Barn", "Pond", "South Gate"])
    alt = rng.uniform(10, 120)
    speed = rng.uniform(1, 15)
    return {
        "vehicle": "drone",
        "summary": "constructive",
        "actions": [
            {"type": "takeoff", "altitude_m": alt},
            {"type": "goto", "place": place, "speed_mps": speed},
            {"type": "return_home"},
        ],
    }
