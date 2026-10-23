"""Secret redaction for logs, errors, and audit payloads."""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import SecretStr

SENSITIVE_HEADERS = ("authorization", "x-api-key", "x-goog-api-key")

_secrets: list[str] = []


def configure_redaction(api_key: SecretStr | None, extra_keys: list[str] | None = None) -> None:
    global _secrets
    _secrets = []
    if api_key is not None:
        _secrets.append(api_key.get_secret_value())
    if extra_keys:
        _secrets.extend(k for k in extra_keys if k)
    _secrets = [s for s in _secrets if s]


def redact_text(text: str) -> str:
    out = text
    for secret in _secrets:
        if secret:
            out = out.replace(secret, "[REDACTED]")
    for hdr in SENSITIVE_HEADERS:
        pattern = re.compile(
            rf"({re.escape(hdr)}:\s*)([^\r\n]+)",
            re.IGNORECASE,
        )
        out = pattern.sub(r"\1[REDACTED]", out)
    return out


def redact_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    return obj


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.args:
            record.args = tuple(redact_text(a) if isinstance(a, str) else a for a in record.args)
        return True


def install_redact_filter() -> None:
    filt = RedactFilter()
    logging.getLogger().addFilter(filt)
