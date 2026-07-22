"""Ebbinghaus spaced-repetition scheduling over the wiki.

A doc is resurfaced along a fixed curve anchored to its ``captured_at``:

    STAGES = [1, 3, 7, 15, 30, 60, 120]   # days after capture
    next_due_at = captured_at + STAGES[stage]

The curve is *fixed* — no recall rating, no ease factor. Seeding and advancing
both fast-forward past stages whose offset has already elapsed, so enrolling an
old corpus (or reviewing late) never dumps a backlog of already-overdue cards.
Advancing past the final stage retires the doc (``next_due_at = NULL``).

Review state lives entirely in ``knowledge_reviews`` (see store.py); the wiki
markdown is never written. The review card reuses the doc's frontmatter
``summary`` (already produced at ingest), so this layer makes no LLM call — it
only reconciles the wiki against the table. ``run()`` is the manual entrypoint
invoked by ``paca knowledge review``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from paca.core import paths
from paca.workflows.knowledge_review import store

# `_markdown_files` is the wiki walk that gives a doc its manifest identity;
# reuse it so `doc_path` means exactly what the ingest manifest means.
from paca.workflows.knowledge_ingest import _markdown_files

# Fixed forgetting-curve offsets, in days after `captured_at`.
STAGES = [1, 3, 7, 15, 30, 60, 120]

__all__ = ["run", "sync", "factory", "STAGES", "schedule_seed", "schedule_advance"]


# --- the curve ------------------------------------------------------------


def _fast_forward_stage(captured_at: date, today: date) -> int:
    """Index of the first stage not yet elapsed = count of offsets already past.

    A doc captured 100 days ago returns 6 (offsets 1..60 elapsed, 120 pending),
    seeding it near the end of the curve rather than at stage 0 with six overdue
    reviews behind it.
    """
    elapsed = (today - captured_at).days
    return sum(1 for offset in STAGES if offset <= elapsed)


def _due_checked(captured_at: date, stage: int, today: date) -> date | None:
    """``captured_at + STAGES[stage]``, or ``None`` once retired past the curve.

    Because ``stage`` is always at least the fast-forward index, ``STAGES[stage]``
    is the first offset greater than the elapsed days, so the result is strictly
    in the future — asserted here to catch any regression that would schedule a
    card in the past.
    """
    if stage >= len(STAGES):
        return None
    due = captured_at + timedelta(days=STAGES[stage])
    assert due > today, f"next_due_at {due} not in the future (captured {captured_at}, stage {stage})"
    return due


def schedule_seed(captured_at: date, today: date) -> tuple[int, date | None]:
    """Stage + due date for a freshly enrolled doc."""
    stage = _fast_forward_stage(captured_at, today)
    return stage, _due_checked(captured_at, stage, today)


def schedule_advance(
    current_stage: int, captured_at: date, today: date
) -> tuple[int, date | None]:
    """Stage + due date after a doc is marked seen.

    ``max(current + 1, fast-forward)`` so a late review skips every stage that
    already elapsed instead of cascading the backlog one overdue card at a time.
    """
    stage = max(current_stage + 1, _fast_forward_stage(captured_at, today))
    return stage, _due_checked(captured_at, stage, today)


# --- reading the wiki -----------------------------------------------------


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return ``(frontmatter, body)``; empty dict when there is no valid block."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            data = yaml.safe_load(parts[1]) or {}
            if isinstance(data, dict):
                return data, parts[2]
    return {}, text


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _resolve_captured_at(path: Path) -> date:
    """Effective capture date, precedence matching dashboard/lib/wiki.ts."""
    front, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
    for key in ("captured_at", "updated_at", "created_at"):
        parsed = _coerce_date(front.get(key))
        if parsed is not None:
            return parsed
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date()


# --- reconciliation -------------------------------------------------------


def sync() -> tuple[int, int]:
    """Reconcile the wiki against the table. Returns ``(enrolled, unenrolled)``."""
    return _reconcile()


def _reconcile() -> tuple[int, int]:
    """Enroll unknown docs, unenroll gone ones.

    Refuses to act on a missing or empty wiki: an empty tree is a
    misconfiguration, not evidence that every doc was deleted (design, task 3.2).
    """
    wiki_dir = paths.WIKI_DIR
    files = _markdown_files(wiki_dir)  # raises RuntimeError if the root is missing
    if not files:
        raise RuntimeError(f"wiki has no markdown docs: {wiki_dir}; refusing to reconcile")

    present = {p.relative_to(wiki_dir).as_posix() for p in files}
    existing = store.existing_doc_paths()
    today = store.today_local()

    seeded: list[dict[str, Any]] = []
    for path in files:
        rel = path.relative_to(wiki_dir).as_posix()
        if rel in existing:
            continue
        captured_at = _resolve_captured_at(path)
        stage, next_due = schedule_seed(captured_at, today)
        seeded.append(
            {"doc_path": rel, "captured_at": captured_at, "stage": stage, "next_due_at": next_due}
        )

    enrolled = store.insert_seeded(seeded)
    unenrolled = store.delete_paths(sorted(existing - present))
    return enrolled, unenrolled


def run() -> dict[str, Any]:
    """Reconcile the wiki against ``knowledge_reviews``.

    Returns ``{enrolled, unenrolled, due}``. Invoked by ``paca knowledge review``
    and ``paca run-workflow knowledge_review``.
    """
    enrolled, unenrolled = _reconcile()
    return {"enrolled": enrolled, "unenrolled": unenrolled, "due": store.count_due()}


def factory():
    """Placeholder so WorkflowConfig.factory parses; never called.

    The YAML sets ``expose.agent_os: false`` so AgentOS never binds this. A
    misconfiguration that flips it on must fail loudly rather than silently
    producing a broken handle.
    """
    raise NotImplementedError(
        "knowledge_review is not an AgentOS workflow; it is invoked via "
        "extra.run_now (`paca knowledge review` or `paca run-workflow`)."
    )
