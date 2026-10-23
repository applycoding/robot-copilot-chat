from __future__ import annotations

import logging

from robot_copilot.redact import RedactFilter, configure_redaction, redact_obj, redact_text
from tests.fakes.sentinel import SENTINEL_ANTHROPIC


def test_redact_sentinel_in_text():
    configure_redaction(None, extra_keys=[SENTINEL_ANTHROPIC])
    out = redact_text(f"bearer {SENTINEL_ANTHROPIC}")
    assert SENTINEL_ANTHROPIC not in out
    assert "[REDACTED]" in out


def test_redact_headers():
    configure_redaction(None)
    msg = "Authorization: Bearer secret123\nx-api-key: abc\nx-goog-api-key: g"
    out = redact_text(msg)
    assert "secret123" not in out
    assert "abc" not in out


def test_redact_log_filter():
    configure_redaction(None, extra_keys=[SENTINEL_ANTHROPIC])
    rec = logging.LogRecord("n", logging.INFO, "", 0, SENTINEL_ANTHROPIC, (), None)
    assert RedactFilter().filter(rec)
    assert SENTINEL_ANTHROPIC not in rec.msg


def test_redact_audit_detail():
    configure_redaction(None, extra_keys=[SENTINEL_ANTHROPIC])
    detail = redact_obj({"key": SENTINEL_ANTHROPIC})
    assert SENTINEL_ANTHROPIC not in str(detail)
