"""Canonical JSON helpers shared by validator, store, and hashing."""

from __future__ import annotations

import json
from typing import Any


def canonical_json(obj: Any) -> str:
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=_default,
    )


def _default(o: Any) -> Any:
    if hasattr(o, "model_dump"):
        return o.model_dump(mode="json")
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def quantize_obj(obj: Any, places: int = 6) -> Any:
    if isinstance(obj, float):
        return round(obj, places)
    if isinstance(obj, dict):
        return {k: quantize_obj(v, places) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [quantize_obj(v, places) for v in obj]
    if isinstance(obj, tuple):
        return [quantize_obj(v, places) for v in obj]
    return obj
