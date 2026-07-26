"""Secret redaction for logs and error messages."""

from __future__ import annotations

import re
from typing import Iterable

_SENSITIVE_KEYS = re.compile(
    r"(token|api[_-]?key|authorization|password|secret|cookie|session|bearer)",
    re.IGNORECASE,
)

_PATTERNS = [
    re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b"),  # Telegram bot tokens
    re.compile(r"(?i)(authorization:\s*bearer\s+)(\S+)"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*([^\s&,;]+)"),
    re.compile(r"(?i)(cookie:\s*)([^\n]+)"),
    re.compile(r"([?&](?:access_token|api_key|token|key|secret)=)([^&\s]+)", re.I),
]


def redact_text(text: str | None, extra: Iterable[str] | None = None) -> str:
    if not text:
        return ""
    out = text
    for pat in _PATTERNS:
        if pat.groups >= 2:
            out = pat.sub(lambda m: f"{m.group(1)}[REDACTED]", out)
        else:
            out = pat.sub("[REDACTED_TOKEN]", out)
    if extra:
        for secret in extra:
            if secret and len(secret) >= 8:
                out = out.replace(secret, "[REDACTED]")
    return out


def redact_mapping(data: dict) -> dict:
    cleaned: dict = {}
    for k, v in data.items():
        if _SENSITIVE_KEYS.search(str(k)):
            cleaned[k] = "[REDACTED]"
        elif isinstance(v, dict):
            cleaned[k] = redact_mapping(v)
        elif isinstance(v, str):
            cleaned[k] = redact_text(v)
        else:
            cleaned[k] = v
    return cleaned
