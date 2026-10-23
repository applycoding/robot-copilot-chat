import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TUTORIAL = ROOT / "docs/tutorial"
SECTIONS = ["## Goal", "## Concepts", "## Files", "## Run it", "## Checkpoint", "## Exercises"]


def test_tutorial_files():
    for i in range(17):
        matches = list(TUTORIAL.glob(f"{i:02d}-*.md"))
        assert matches, i
        text = matches[0].read_text()
        for sec in SECTIONS:
            assert sec in text


def test_checkpoint_collects():
    import subprocess

    proc = subprocess.run(
        ["uv", "run", "--no-sync", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "RCC_DOTENV": "off"},
    )
    assert proc.returncode == 0
    out = proc.stdout
    for path in TUTORIAL.glob("*.md"):
        for m in re.findall(r"`(tests/[^`]+)`", path.read_text()):
            node = m.split("::")[-1]
            assert node in out or m.split("::")[0].replace("tests/", "tests/") in out
