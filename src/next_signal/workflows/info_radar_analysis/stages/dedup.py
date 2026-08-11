"""Dedup gate: embed → provider-scoped pgvector search → LLM judge.

Conservative posture: any internal failure (embedder down, judge agent
raises) is logged loudly and the item is treated as ``novel`` — we'd rather
show a likely-dup than swallow a novel item. The push pipeline can mark
freshly-novel-with-failed-embed items separately if it wants.

One embedder snapshot is resolved per item and used for both the search and
the identity handed back for persistence. Live settings are never re-read
afterwards, so a settings write landing mid-item cannot label this vector with
the space it did not come from.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from next_signal.agents.stage import run_stage
from next_signal.core.models import get_embedder
from next_signal.workflows.info_radar_analysis import store as analysis_store
from next_signal.workflows.info_radar_analysis.schemas import DedupVerdict

log = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.40
DEFAULT_K = 5


@dataclass(frozen=True)
class DedupOutcome:
    status: str  # 'novel' | 'duplicate'
    matched_topic_id: int | None
    embedding: list[float] | None  # used by persist to create a new topic when novel
    # Vector-space identity that produced ``embedding``; the two are set and
    # cleared together, so a vector is never stored without its provenance.
    embedder: str | None


def run(summary: str, *, threshold: float = DEFAULT_THRESHOLD, k: int = DEFAULT_K) -> DedupOutcome:
    """Decide whether ``summary`` is a paraphrase of a previously-pushed topic."""
    try:
        embedder = get_embedder()
        embedding = embedder.embed(summary)
    except RuntimeError as e:
        log.warning("dedup_embedder_failed", extra={"error": str(e)})
        return DedupOutcome(
            status="novel", matched_topic_id=None, embedding=None, embedder=None
        )

    identity = embedder.identity
    novel = DedupOutcome(
        status="novel", matched_topic_id=None, embedding=embedding, embedder=identity
    )

    try:
        candidates = analysis_store.search_topics(
            embedding, embedder=identity, k=k, threshold=threshold
        )
    except Exception as e:  # noqa: BLE001
        log.warning("dedup_search_failed", extra={"error": str(e)})
        return novel

    if not candidates:
        return novel

    try:
        verdict = _ask_judge(summary, candidates)
    except Exception as e:  # noqa: BLE001
        log.warning("dedup_judge_failed", extra={"error": str(e)})
        return novel

    if verdict.is_duplicate and verdict.matched_topic_id is not None:
        # Defensive: verdict id must be in the candidates we sent, otherwise
        # the judge fabricated an id. Treat as novel.
        candidate_ids = {int(c["id"]) for c in candidates}
        if int(verdict.matched_topic_id) in candidate_ids:
            return DedupOutcome(
                status="duplicate",
                matched_topic_id=int(verdict.matched_topic_id),
                embedding=embedding,
                embedder=identity,
            )
        log.warning(
            "dedup_judge_unknown_topic_id",
            extra={"verdict_id": verdict.matched_topic_id, "candidates": list(candidate_ids)},
        )
    return novel


def _ask_judge(summary: str, candidates: list[dict]) -> DedupVerdict:
    payload = {
        "new_summary": summary,
        "candidates": [
            {"id": int(c["id"]), "summary": str(c["topic_summary"])} for c in candidates
        ],
    }
    return run_stage(
        "radar_dedup_judge",
        json.dumps(payload, ensure_ascii=False),
        DedupVerdict,
    )
