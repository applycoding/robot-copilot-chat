from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_gitignore_env():
    gi = (ROOT / ".gitignore").read_text()
    assert ".env" in gi and "!.env.example" in gi


def test_env_example_keys():
    text = (ROOT / ".env.example").read_text()
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY"):
        assert f"{key}=" in text


def test_no_model_ids_in_src():
    src = (ROOT / "src").read_text(encoding="utf-8", errors="ignore") if False else ""
    for p in (ROOT / "src").rglob("*.py"):
        src += p.read_text(encoding="utf-8")
    assert "mock-1" not in src
    assert "claude-sonnet" not in src


def test_static_js_safe():
    for p in (ROOT / "src/robot_copilot/static").glob("*.js"):
        text = p.read_text()
        for bad in ("innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "new Function"):
            assert bad not in text


def test_readme_sections():
    readme = (ROOT / "README.md").read_text()
    for heading in (
        "## Safety model",
        "## Quickstart (60 seconds)",
        "## Try these phrases",
        "## Docker",
        "## Use a real LLM",
        "## Architecture",
        "## Safety rules",
        "## Configure your own site",
        "## Project layout",
        "## Testing",
        "## CI",
        "## Tutorial",
        "## Out of scope / disclaimer",
        "## License and author",
    ):
        assert heading in readme
    assert "mermaid" in readme
    assert "\u2014" not in readme and "\u2013" not in readme
    for i in range(17):
        assert f"{i:02d}-" in readme or f"docs/tutorial/{i:02d}-" in readme


def test_screenshots_exist():
    for name in ("01-plan.png", "02-repair.png", "03-executing.png"):
        assert (ROOT / "docs/screenshots" / name).is_file()
