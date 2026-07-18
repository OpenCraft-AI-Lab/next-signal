"""Folo CLI bridge helpers.

``folocli`` is invoked via subprocess from ``paca.collectors.info_radar.runner``;
the actual argv comes from each source's YAML entry. This module exists for
two things only:

1. ``default_argv()`` — the default argv prefix when a source descriptor
   doesn't override; pinned to ``folocli@0.0.5`` per Appendix B.
2. ``whoami()`` — used by ``paca doctor`` to verify auth.

Auth: ``folocli`` reads ``FOLO_TOKEN`` env var if set, otherwise falls back to
the session at ``~/.folo/config.json``. We pass the parent environment through
unchanged so both paths keep working.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

# Pinned per Appendix B: `npx folocli` (no @<version>) resolves to a stale
# cached build that returns "operation aborted" on timeline. Override with
# FOLO_CLI_ARGV if a newer release ships.
_DEFAULT_ARGV = ["npx", "--yes", "folocli@0.0.5"]


def default_argv() -> list[str]:
    """argv prefix for invoking ``folocli``. Honors ``FOLO_CLI_ARGV`` env override."""
    override = os.environ.get("FOLO_CLI_ARGV", "").strip()
    if override:
        # Split on whitespace; operator is responsible for quoting if needed.
        return override.split()
    return list(_DEFAULT_ARGV)


def whoami(timeout: float = 60.0) -> tuple[bool, str]:
    """Run ``folocli whoami`` and return (ok, message). Used by ``paca doctor``.

    Returns ``ok=True`` when the JSON envelope has ``ok: true``; ``ok=False``
    otherwise with a one-line message. Never raises. Default timeout is 60s
    because a cold ``npx --yes folocli@<v>`` install can run 20-40s on first
    invocation; subsequent calls hit the npm cache and return in <1s.
    """
    try:
        result = subprocess.run(
            [*default_argv(), "whoami"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        return (False, f"folocli launcher missing: {e}")
    except subprocess.TimeoutExpired:
        return (False, f"folocli whoami timed out after {timeout}s")

    try:
        envelope: dict[str, Any] = json.loads(result.stdout)
    except json.JSONDecodeError:
        excerpt = (result.stderr or result.stdout)[:200].strip()
        return (False, f"folocli whoami non-JSON output: {excerpt!r}")

    if envelope.get("ok"):
        user = (envelope.get("data") or {}).get("user") or {}
        name = user.get("name") or user.get("email") or user.get("id") or "unknown"
        return (True, f"logged in as {name}")

    err = envelope.get("error") or {}
    return (False, f"{err.get('code', 'UNKNOWN')}: {err.get('message', 'auth check failed')}")


def entry_get(source_id: str, *, timeout: float = 60.0) -> dict[str, Any]:
    """Fetch one entry's full content via ``folocli entry get <id>``.

    Returns the article dict from ``data.entries`` of the envelope (so callers
    can read ``["content"]``, ``["title"]``, etc.). Raises ``RuntimeError`` on
    any error path — caller (typically the fetch stage) catches and falls back
    to description-only. We never silently return an empty dict because the
    fallback decision must be observable.
    """
    if not source_id:
        raise RuntimeError("entry_get requires a non-empty source_id")
    try:
        result = subprocess.run(
            [*default_argv(), "entry", "get", source_id],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        raise RuntimeError(f"folocli launcher missing: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"folocli entry get {source_id} timed out after {timeout}s") from e

    if result.returncode != 0 and not result.stdout.strip():
        excerpt = (result.stderr or "").strip()[:200]
        raise RuntimeError(f"folocli entry get exit {result.returncode}: {excerpt!r}")

    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        excerpt = (result.stderr or result.stdout)[:200].strip()
        raise RuntimeError(f"folocli entry get non-JSON output: {excerpt!r}") from e

    if not isinstance(envelope, dict) or "ok" not in envelope:
        raise RuntimeError(f"folocli entry get: missing 'ok' in envelope: {envelope!r}")

    if not envelope.get("ok"):
        err = envelope.get("error") or {}
        raise RuntimeError(
            f"folocli entry get ok=false: {err.get('code', 'UNKNOWN')}: "
            f"{err.get('message', 'no message')}"
        )

    data = envelope.get("data") or {}
    entries = data.get("entries")
    if not isinstance(entries, dict):
        raise RuntimeError(
            f"folocli entry get: data.entries missing or not a dict, got {type(entries).__name__}"
        )
    return entries


def subscription_list(*, timeout: float = 60.0) -> list[dict[str, Any]]:
    """Return normalized rows from ``folocli subscription list``.

    The CLI output shape has drifted across folocli versions, so this parser
    accepts the common list locations and field aliases, then emits a small
    dashboard-stable row shape. It raises ``RuntimeError`` on auth/shape errors
    instead of returning an empty list, because an empty subscription inventory
    is materially different from a failed CLI call.
    """
    try:
        result = subprocess.run(
            [*default_argv(), "subscription", "list"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        raise RuntimeError(f"folocli launcher missing: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"folocli subscription list timed out after {timeout}s") from e

    if result.returncode != 0 and not result.stdout.strip():
        excerpt = (result.stderr or "").strip()[:200]
        raise RuntimeError(f"folocli subscription list exit {result.returncode}: {excerpt!r}")

    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        excerpt = (result.stderr or result.stdout)[:200].strip()
        raise RuntimeError(f"folocli subscription list non-JSON output: {excerpt!r}") from e

    if not isinstance(envelope, dict) or "ok" not in envelope:
        raise RuntimeError(f"folocli subscription list: missing 'ok' in envelope: {envelope!r}")

    if not envelope.get("ok"):
        err = envelope.get("error") or {}
        raise RuntimeError(
            f"folocli subscription list ok=false: {err.get('code', 'UNKNOWN')}: "
            f"{err.get('message', 'no message')}"
        )

    raw_rows = _subscription_rows(envelope.get("data"))
    return [_normalize_subscription(row) for row in raw_rows]


def _subscription_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = []
        for key in ("subscriptions", "feeds", "list", "items"):
            if key in data:
                rows = data[key]
                break
    else:
        raise RuntimeError(
            f"folocli subscription list: data must be a list or mapping, got {type(data).__name__}"
        )
    if not isinstance(rows, list):
        raise RuntimeError(
            f"folocli subscription list: subscriptions missing or not a list, got {type(rows).__name__}"
        )
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            out.append(row)
    return out


def _first_str(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_int(row: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _category(row: dict[str, Any]) -> str | None:
    raw = row.get("category") or row.get("view") or row.get("folder")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, dict):
        return _first_str(raw, "title", "name", "label", "id")
    return None


def _normalize_subscription(row: dict[str, Any]) -> dict[str, Any]:
    feed = row.get("feeds") if isinstance(row.get("feeds"), dict) else {}
    title = _first_str(row, "title", "name", "feedTitle") or _first_str(feed, "title", "name") or "(untitled)"
    feed_url = (
        _first_str(row, "feedUrl", "feed_url", "url", "xmlUrl", "xml_url")
        or _first_str(feed, "feedUrl", "feed_url", "url", "xmlUrl", "xml_url")
        or _first_str(row, "siteUrl", "site_url", "homepage")
        or _first_str(feed, "siteUrl", "site_url", "homepage")
        or ""
    )
    return {
        "id": _first_str(row, "id", "sourceId", "source_id", "feedId")
        or _first_str(feed, "id", "sourceId", "source_id")
        or feed_url
        or title,
        "title": title,
        "feedUrl": feed_url,
        "siteUrl": _first_str(row, "siteUrl", "site_url", "homepage")
        or _first_str(feed, "siteUrl", "site_url", "homepage"),
        "category": _category(row) or "Uncategorized",
        "unread": _first_int(row, "unread", "unreadCount", "unread_count"),
        "updatedAt": _first_str(
            row, "updatedAt", "updated_at", "lastUpdated", "last_updated", "createdAt", "created_at"
        ),
    }
