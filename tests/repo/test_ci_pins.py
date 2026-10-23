import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ci_pins():
    text = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "permissions:" in text and "contents: read" in text
    assert "ubuntu-24.04" in text
    assert "secrets." not in text
    for line in text.splitlines():
        if "uses:" in line:
            assert re.search(r"@[0-9a-f]{40}\s+# v", line), line
    assert "uv run --no-sync" in text
