"""Capture UI screenshots for the README (requires a server on port 8765)."""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("capture_readme_screenshots.py")), run_name="__main__")
