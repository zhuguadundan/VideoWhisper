"""Helpers for safe logging of request payloads and third-party output."""

from __future__ import annotations

from typing import Any

SENSITIVE_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "authorization",
    "token",
    "secret",
    "cookie",
    "password",
    "passwd",
    "session",
    "credential",
)


def is_sensitive_key(key: str) -> bool:
    lowered = (key or "").lower()
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def mask_sensitive_data(value: Any, key: str | None = None) -> Any:
    """Recursively mask secrets before they are written to logs."""

    if key and is_sensitive_key(key):
        return "***"
    if isinstance(value, dict):
        return {k: mask_sensitive_data(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_sensitive_data(item, key) for item in value]
    if isinstance(value, tuple):
        return tuple(mask_sensitive_data(item, key) for item in value)
    return value
