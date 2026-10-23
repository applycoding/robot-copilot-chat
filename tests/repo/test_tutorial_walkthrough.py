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


def test_tutorial_referenced_paths_exist():
    for path in TUTORIAL.glob("*.md"):
        text = path.read_text()
        in_files = False
        for line in text.splitlines():
            if line.strip() == "## Files":
                in_files = True
                continue
            if in_files and line.startswith("## ") and line.strip() != "## Files":
                in_files = False
            if not in_files:
                continue
            if line.startswith("- `") and "`" in line[3:]:
                rel = line.split("`", 2)[1]
                if rel.startswith(("src/", "config/", "tests/", "docs/", ".github/")):
                    assert (ROOT / rel).exists(), f"{path.name}: missing {rel}"


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
        text = path.read_text()
        in_checkpoint = False
        for line in text.splitlines():
            if line.strip() == "## Checkpoint":
                in_checkpoint = True
                continue
            if in_checkpoint and line.startswith("## "):
                break
            if not in_checkpoint or not line.startswith("- `"):
                continue
            m = line.split("`", 2)[1]
            if not m.startswith("tests/"):
                continue
            node = m.split("::")[-1]
            assert node in out or m.split("::")[0] in out
