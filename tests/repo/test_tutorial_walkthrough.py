from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TUTORIAL = ROOT / "docs/tutorial"
SECTIONS = [
    "## Goal",
    "## Files",
    "## Walkthrough",
    "## Try it",
    "## Exercise",
    "## Checkpoint",
]
_PY_FENCE = re.compile(r"```python\n(.*?)```", re.DOTALL)
_BOILERPLATE = "This chapter ties to the integration story"


def _prose_words(text: str) -> int:
    without_code = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return len(re.findall(r"\w+", without_code))


def test_tutorial_files():
    for i in range(17):
        matches = list(TUTORIAL.glob(f"{i:02d}-*.md"))
        assert matches, i
        text = matches[0].read_text()
        assert _BOILERPLATE not in text, matches[0].name
        for sec in SECTIONS:
            assert sec in text, f"{matches[0].name} missing {sec}"
        prose = _prose_words(text)
        assert 350 <= prose <= 750, f"{matches[0].name} prose word count {prose}"


def test_tutorial_excerpt_count():
    for path in sorted(TUTORIAL.glob("*.md")):
        blocks = _PY_FENCE.findall(path.read_text())
        if path.name.startswith("00-"):
            assert len(blocks) >= 1, path.name
        else:
            assert len(blocks) >= 2, f"{path.name} needs >=2 python excerpts, got {len(blocks)}"


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


def test_tutorial_python_excerpts_are_verbatim():
    for path in TUTORIAL.glob("*.md"):
        text = path.read_text()
        files = _files_list(text)
        assert files, f"{path.name}: no files listed"
        blocks = _PY_FENCE.findall(text)
        assert blocks, f"{path.name}: no python excerpt"
        for block in blocks:
            excerpt = block.strip("\n") + "\n"
            matched = False
            for rel in files:
                if not rel.endswith(".py"):
                    continue
                src = (ROOT / rel).read_text()
                if excerpt in src:
                    matched = True
                    break
            assert matched, f"{path.name}: excerpt not found verbatim in listed .py files"


def _files_list(text: str) -> list[str]:
    out: list[str] = []
    in_files = False
    for line in text.splitlines():
        if line.strip() == "## Files":
            in_files = True
            continue
        if in_files and line.startswith("## "):
            break
        if in_files and line.startswith("- `") and "`" in line[3:]:
            out.append(line.split("`", 2)[1])
    return out


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
