from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from tests.repo.tutorial_ast import assert_segment_rules, extract_segment

ROOT = Path(__file__).resolve().parents[2]
TUTORIAL = ROOT / "docs/tutorial"
TRY_EXPECTED = Path(__file__).with_name("tutorial_try_expected.json")
SECTIONS = [
    "## Goal",
    "## Files",
    "## Walkthrough",
    "## Try it",
    "## Exercise",
    "## Checkpoint",
]
_SEGMENT = re.compile(r"<!-- segment: (\S+) ([\w.]+) -->\s*```python\n(.*?)```", re.DOTALL)
_PY_FENCE = re.compile(r"```python\n(.*?)```", re.DOTALL)
_BASH_FENCE = re.compile(r"## Try it\s*(.*?)\s*### Expected", re.DOTALL)
_SENTENCE = re.compile(r"[.!?]\s+")


def _prose_words(text: str) -> int:
    without_code = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return len(re.findall(r"\w+", without_code))


def test_tutorial_files():
    for i in range(17):
        matches = list(TUTORIAL.glob(f"{i:02d}-*.md"))
        assert matches, i
        text = matches[0].read_text()
        for sec in SECTIONS:
            assert sec in text, f"{matches[0].name} missing {sec}"
        prose = _prose_words(text)
        assert 60 <= prose <= 220, f"{matches[0].name} prose word count {prose}"


def _prose_text(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def _sentences_8plus(text: str) -> list[str]:
    raw = _prose_text(text)
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    parts = re.split(r"[.!?]\s+|\n+", raw)
    out: list[str] = []
    for part in parts:
        words = re.findall(r"\w+", part)
        if len(words) >= 8:
            norm = " ".join(w.lower() for w in words)
            out.append(norm)
    return out


def test_tutorial_no_duplicate_sentences_across_chapters():
    seen: dict[str, str] = {}
    for path in sorted(TUTORIAL.glob("*.md")):
        for sentence in _sentences_8plus(path.read_text()):
            if sentence in seen:
                raise AssertionError(
                    f"duplicate sentence in {path.name} and {seen[sentence]}: {sentence[:80]}..."
                )
            seen[sentence] = path.name


def test_tutorial_no_robotic_goal_filler():
    banned = (
        "Learning note",
        "You are reading tutorial chapter",
        "links harness and hygiene to validators, confirmation hashes",
        "Skim imports at the top of the module",
        "Scroll one screen above and below the excerpt",
    )
    for path in sorted(TUTORIAL.glob("*.md")):
        text = path.read_text()
        for phrase in banned:
            assert phrase not in text, f"{path.name} contains banned filler: {phrase}"


def test_tutorial_excerpt_segments():
    used: set[tuple[str, int, int]] = set()
    for path in sorted(TUTORIAL.glob("*.md")):
        text = path.read_text()
        segments = list(_SEGMENT.finditer(text))
        assert segments, f"{path.name}: missing segment markers"
        py_blocks = _PY_FENCE.findall(text)
        assert len(py_blocks) == len(segments)
        for match in segments:
            rel, qualname, excerpt = match.group(1), match.group(2), match.group(3)
            seg = extract_segment(ROOT, rel, qualname)
            assert_segment_rules(seg)
            key = (rel, seg.lineno, seg.end_lineno)
            assert key not in used, f"overlap {key} in {path.name}"
            used.add(key)
            assert excerpt == seg.text, f"{path.name}: stale excerpt for {qualname}"


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


def test_tutorial_try_it_commands():
    expected_all = json.loads(TRY_EXPECTED.read_text())
    env = {**dict(__import__("os").environ), "RCC_DOTENV": "off"}
    for path in sorted(TUTORIAL.glob("*.md")):
        text = path.read_text()
        bash_match = _BASH_FENCE.search(text)
        assert bash_match, f"{path.name}: missing try-it bash block"
        cmd = bash_match.group(1).strip()
        assert cmd.startswith("```bash"), path.name
        bash = re.search(r"```bash\n(.*?)```", cmd, re.DOTALL)
        assert bash, path.name
        script = bash.group(1).strip()
        proc = subprocess.run(
            script,
            shell=True,
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
        )
        assert proc.returncode == 0, f"{path.name} try-it failed: {proc.stderr}\n{proc.stdout}"
        out = proc.stdout
        for line in expected_all[path.name]["expected_lines"]:
            assert line in out, f"{path.name}: expected line missing: {line}\n{out}"


def test_checkpoint_collects():
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
