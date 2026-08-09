"""Common helpers for cloud-API integrations.

Pattern shared across all integrations:
  * Env vars hold credentials (TAVILY_API_KEY, NOTION_API_KEY, ...).
  * Tools fail loud with a clear "set X" message at *call* time, not import
    time — so a missing key for one integration doesn't break the whole
    AgentOS startup.
  * httpx.Client is the default HTTP transport (sync; agno's tool runner is
    sync). Set a per-integration timeout: assistant tools should never hang.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

import httpx

DEFAULT_TIMEOUT = 30.0
_RATE_LIMIT_LOCK = threading.Lock()
_LAST_CALL_BY_BUCKET: dict[str, float] = {}


def env(name: str, *, hint: str | None = None) -> str:
    """Read a required env var, or raise with a clear remediation message."""
    val = os.environ.get(name, "").strip()
    if not val:
        msg = f"environment variable {name} is not set"
        if hint:
            msg += f" — {hint}"
        raise RuntimeError(msg)
    return val


def http_client(
    *,
    base_url: str | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> httpx.Client:
    """Build an httpx.Client with sane defaults. Caller owns the lifetime."""
    return httpx.Client(
        base_url=base_url or "",
        headers=headers or {},
        timeout=timeout,
        follow_redirects=True,
    )


def rate_limit(bucket: str, *, min_interval: float = 1.0) -> None:
    """Sleep until this rate-limit bucket is allowed to make its next call."""
    with _RATE_LIMIT_LOCK:
        now = time.monotonic()
        next_allowed = _LAST_CALL_BY_BUCKET.get(bucket, 0.0) + min_interval
        wait = max(0.0, next_allowed - now)
        _LAST_CALL_BY_BUCKET[bucket] = now + wait
    if wait > 0:
        time.sleep(wait)


def truncate(text: str, max_chars: int) -> str:
    """Hard-cap returned text so a chatty API doesn't blow the LLM context."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20] + f"\n\n[…truncated {len(text) - max_chars} chars]"


def to_jsonable(obj: Any) -> Any:
    """Best-effort coercion of API responses into JSON-safe primitives."""
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)
