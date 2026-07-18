"""Dedup gate: embed → pgvector ANN → LLM judge.

Conservative posture: any internal failure (embedder down, judge agent
raises) is logged loudly and the item is treated as ``novel`` — we'd rather
show a likely-dup than swallow a novel item. The push pipeline can mark
freshly-novel-with-failed-embed items separately if it wants.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from paca.agents.loader import build_from_name
from paca.agents.structured import run_structured
from paca.core.models import get_embedder
from paca.workflows.info_radar_analysis import store as analysis_store
from paca.workflows.info_radar_analysis.schemas import DedupVerdict

log = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.40
DEFAULT_K = 5


@dataclass(frozen=True)
class DedupOutcome:
    status: str  # 'novel' | 'duplicate'
    matched_topic_id: int | None
    embedding: list[float] | None  # used by persist to create a new topic when novel


def run(summary: str, *, threshold: float = DEFAULT_THRESHOLD, k: int = DEFAULT_K) -> DedupOutcome:
    """Decide whether ``summary`` is a paraphrase of a previously-pushed topic."""
    try:
        embedder = get_embedder("local")
        embedding = embedder(summary)
    except (RuntimeError, KeyError) as e:
        log.warning("dedup_embedder_failed", extra={"error": str(e)})
        return DedupOutcome(status="novel", matched_topic_id=None, embedding=None)

    try:
        candidates = analysis_store.ann_search_topics(embedding, k=k, threshold=threshold)
    except Exception as e:  # noqa: BLE001
        log.warning("dedup_ann_failed", extra={"error": str(e)})
        return DedupOutcome(status="novel", matched_topic_id=None, embedding=embedding)

    if not candidates:
        return DedupOutcome(status="novel", matched_topic_id=None, embedding=embedding)

    try:
        verdict = _ask_judge(summary, candidates)
    except Exception as e:  # noqa: BLE001
        log.warning("dedup_judge_failed", extra={"error": str(e)})
        return DedupOutcome(status="novel", matched_topic_id=None, embedding=embedding)

    if verdict.is_duplicate and verdict.matched_topic_id is not None:
        # Defensive: verdict id must be in the candidates we sent, otherwise
        # the judge fabricated an id. Treat as novel.
        candidate_ids = {int(c["id"]) for c in candidates}
        if int(verdict.matched_topic_id) in candidate_ids:
            return DedupOutcome(
                status="duplicate",
                matched_topic_id=int(verdict.matched_topic_id),
                embedding=embedding,
            )
        log.warning(
            "dedup_judge_unknown_topic_id",
            extra={"verdict_id": verdict.matched_topic_id, "candidates": list(candidate_ids)},
        )
    return DedupOutcome(status="novel", matched_topic_id=None, embedding=embedding)


def _ask_judge(summary: str, candidates: list[dict]) -> DedupVerdict:
    payload = {
        "new_summary": summary,
        "candidates": [
            {"id": int(c["id"]), "summary": str(c["topic_summary"])} for c in candidates
        ],
    }
    agent = build_from_name("radar_dedup_judge")
    return run_structured(agent, json.dumps(payload, ensure_ascii=False), DedupVerdict)
