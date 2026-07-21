"""Range-scoped synthesis of kept radar signals into themed narratives.

Flow (single LLM call, no per-item pipeline):

    validate range
      → select candidates (gate + top-N by score)
      → empty? return without touching the DB or the model
      → claim the key ('running')
      → radar_recap agent
      → validate citations against the ids actually sent
      → persist 'done', or 'error' leaving prior content readable

A recap is identified by ``(since, until, min_score, novel_only)``, so a repeat
request is a cache hit and a regenerate is an in-place upsert.

This module is not an AgentOS workflow — it's invoked by the CLI via
``extra.run_now`` (see configs/workflows/info_radar_recap.yaml).
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel, Field

from paca.workflows.info_radar_recap import store

log = logging.getLogger(__name__)

# Selection cap. A month-range recap can match 200+ items; the prompt stays
# bounded and `considered_count` keeps the truncation visible to the reader.
_MAX_ITEMS = 60

__all__ = ["run", "factory", "RecapOutput", "Theme"]


class Theme(BaseModel):
    """One synthesized through-line, grounded in specific items."""

    title: str = Field(..., description="Short theme name.")
    narrative: str = Field(..., description="One paragraph developing the theme.")
    item_ids: list[int] = Field(
        default_factory=list,
        description="Ids of the input items this theme rests on.",
    )


class RecapOutput(BaseModel):
    """Agent output schema for a range recap."""

    headline: str = Field(..., description="One line characterizing the period.")
    themes: list[Theme] = Field(default_factory=list)


def _coerce_day(value: date | str, label: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as e:
        raise RuntimeError(f"{label} is not a YYYY-MM-DD date: {value!r}") from e


def _validate_themes(
    themes: list[Theme], valid_ids: set[int]
) -> list[dict[str, Any]]:
    """Drop unknown citations, then drop themes left with none.

    A hallucinated id costs that citation, not the whole recap. A theme with no
    surviving citation is unverifiable, so it goes too.
    """
    out: list[dict[str, Any]] = []
    for theme in themes:
        kept = [i for i in theme.item_ids if i in valid_ids]
        unknown = [i for i in theme.item_ids if i not in valid_ids]
        if unknown:
            log.warning(
                "recap_citation_unknown",
                extra={"theme": theme.title, "unknown_ids": unknown},
            )
        if not kept:
            log.warning("recap_theme_uncited", extra={"theme": theme.title})
            continue
        out.append({"title": theme.title, "narrative": theme.narrative, "item_ids": kept})
    return out


def run(
    *,
    since: date | str | None = None,
    until: date | str | None = None,
    min_score: int = 0,
    novel_only: bool = False,
    regenerate: bool = False,
) -> dict[str, Any]:
    """Generate (or serve from cache) the recap for one range and quality gate.

    Both bounds default to the trailing 7 days ending today, so the bare
    ``paca run-workflow info_radar_recap`` entrypoint does something useful.
    The CLI requires them explicitly.

    Returns a dict whose ``status`` is one of ``cached`` / ``empty`` /
    ``running`` / ``done`` / ``error``.
    """
    until_day = _coerce_day(until, "until") if until is not None else store.today_local()
    since_day = (
        _coerce_day(since, "since") if since is not None else until_day - timedelta(days=6)
    )
    if until_day < since_day:
        raise RuntimeError(
            f"invalid recap range: until ({until_day}) precedes since ({since_day})"
        )

    key = {
        "since": since_day,
        "until": until_day,
        "min_score": min_score,
        "novel_only": novel_only,
    }

    if not regenerate:
        cached = store.read_recap(**key)
        if cached is not None and cached["status"] == "done":
            return {"status": "cached", **_public(cached)}

    items, considered, watermark = store.select_candidates(**key, cap=_MAX_ITEMS)
    if not items:
        # No row, no agent: narrating the absence of input would cost a minute
        # of inference to say nothing.
        return {"status": "empty", "considered_count": 0, **_key_public(key)}

    if not store.begin_recap(**key):
        return {"status": "running", **_key_public(key)}

    try:
        recap = _generate(since_day, until_day, items)
        themes = _validate_themes(recap.themes, {i["id"] for i in items})
        if not themes:
            raise RuntimeError("no theme survived citation validation")
    except Exception as e:  # noqa: BLE001 — recorded on the row, surfaced to the caller
        log.warning("recap_failed", extra={**_key_public(key), "error": str(e)})
        store.fail_recap(**key, error=str(e))
        return {"status": "error", "error": str(e), **_key_public(key)}

    store.finish_recap(
        **key,
        headline=recap.headline,
        themes=themes,
        item_count=len(items),
        considered_count=considered,
        max_analyzed_at=watermark,
    )
    return {
        "status": "done",
        "headline": recap.headline,
        "themes": themes,
        "item_count": len(items),
        "considered_count": considered,
        **_key_public(key),
    }


def _generate(since_day: date, until_day: date, items: list[dict[str, Any]]) -> RecapOutput:
    """Ask radar_recap to cluster the selected items into themes."""
    from paca.agents.loader import build_from_name
    from paca.agents.structured import run_structured

    payload = {
        "since": since_day.isoformat(),
        "until": until_day.isoformat(),
        "items": items,
    }
    agent = build_from_name("radar_recap")
    return run_structured(
        agent, json.dumps(payload, ensure_ascii=False), RecapOutput
    )


def _key_public(key: dict[str, Any]) -> dict[str, Any]:
    return {
        "since": key["since"].isoformat(),
        "until": key["until"].isoformat(),
        "min_score": key["min_score"],
        "novel_only": key["novel_only"],
    }


def _public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "since": row["since"].isoformat(),
        "until": row["until"].isoformat(),
        "min_score": row["min_score"],
        "novel_only": row["novel_only"],
        "headline": row["headline"],
        "themes": row["themes"] or [],
        "item_count": row["item_count"],
        "considered_count": row["considered_count"],
    }


def factory():
    """Placeholder so WorkflowConfig.factory parses; never called.

    The YAML sets ``expose.agent_os: false`` so AgentOS never tries to bind
    this. A misconfiguration that flips it on must fail loudly here rather
    than silently producing a broken handle.
    """
    raise NotImplementedError(
        "info_radar_recap is not an AgentOS workflow; it is invoked via "
        "extra.run_now (`paca info-radar recap` or `paca run-workflow`)."
    )
