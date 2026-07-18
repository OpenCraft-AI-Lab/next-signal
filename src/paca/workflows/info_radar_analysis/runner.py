"""Batch orchestrator: load goals, iterate unseen items, persist analyses.

Pipelined two-phase shape:
  1. **Batched tier-1** runs in a background producer thread. Items are
     chunked (default size ``_BATCH_SIZE``) and sent to the tier-1 agent in
     a single prompt per chunk. On any batch-level failure (length /
     index / schema) the chunk falls back to one-item-at-a-time calls so a
     single bad item can't poison its neighbors. Each ``(item, verdict)``
     pair is pushed onto a bounded queue as soon as it's ready.
  2. **Per-item rest** drains the queue on the main thread: fetch → tier2
     → dedup → persist, still sequential per item. Tier-2 content is large
     so batching that stage is not viable; see design.md §D12.

Because OMLX's concurrency cap is 2, the tier-1 batch call for chunk N+1
naturally overlaps with phase-2 work on items from chunk N — phase 1's
wall-clock cost is mostly hidden behind phase 2. Phase 2 itself stays
single-threaded so dedup ordering and counter mutation remain race-free.

Per-item failure isolation invariant (design.md §D9) is preserved: a
failure during any single item's tier1 / fetch / tier2 / dedup never
aborts the batch.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any

from paca.workflows.info_radar_analysis import store as analysis_store
from paca.workflows.info_radar_analysis.goals import Goal, load_goals
from paca.workflows.info_radar_analysis.schemas import Tier1Verdict
from paca.workflows.info_radar_analysis.stages import dedup, fetch, tier1, tier2

log = logging.getLogger(__name__)

# Tier-1 batch chunk size. Conservative so xgrammar's structured-output
# constraint stays reliable on long array outputs; can be tuned upward once
# we have throughput data. See design.md §D12.
_BATCH_SIZE = 10


# Sentinel signalling the producer has drained all chunks.
_DONE = object()


def run(*, limit: int | None = None, source: str | None = None) -> dict[str, Any]:
    """Process unseen radar_items through the two-tier analysis pipeline.

    Returns a counters dict suitable for ``job_runs.output``. Always returns
    — never raises — except for the one fatal precondition (no goals.yaml).
    """
    goals = load_goals()  # fail-fast intentional: empty/missing → RuntimeError

    items = analysis_store.fetch_unseen_items(limit=limit, source=source)
    counters = _empty_counters()
    counters["items_total"] = len(items)

    if not items:
        return counters

    # Bounded queue keeps memory predictable when phase 2 falls behind phase 1.
    # Two chunks' worth of headroom is enough overlap to keep OMLX's second
    # slot busy without buffering the whole batch.
    work_queue: queue.Queue = queue.Queue(maxsize=_BATCH_SIZE * 2)

    def _producer() -> None:
        try:
            for start in range(0, len(items), _BATCH_SIZE):
                chunk = items[start : start + _BATCH_SIZE]
                verdicts = _run_chunk(chunk, goals)
                for item, verdict in zip(chunk, verdicts):
                    work_queue.put((item, verdict))
        except Exception:  # noqa: BLE001 — stderr-only thread tracebacks vanish under launchd
            log.exception("tier1_producer_crashed")
        finally:
            # Always signal completion — even on unexpected raise — so the
            # consumer never blocks forever. Unprocessed items stay unseen
            # and retry next run.
            work_queue.put(_DONE)

    producer = threading.Thread(
        target=_producer, name="info-radar-tier1", daemon=True
    )
    producer.start()

    # Consumer: phase 2 stays single-threaded so dedup ordering and counter
    # mutation remain race-free. An outermost try/except guards against
    # unexpected raises (e.g. transient DB errors during insert_analysis
    # or mark_seen) so one item never aborts the batch — strict superset of
    # the spec's tier1/fetch/tier2/dedup isolation requirement.
    while True:
        msg = work_queue.get()
        if msg is _DONE:
            break
        item, verdict = msg
        try:
            _process_item(item, verdict, goals, counters)
        except Exception as e:  # noqa: BLE001
            log.warning(
                "item_unexpected_raise",
                extra={"item_id": item.get("id"), "error": str(e)},
            )
            counters["item_error"] += 1

    producer.join()
    return counters


# ---------------------------------------------------------------------------
# Phase 1: batched tier-1 with per-chunk fallback (runs in producer thread)
# ---------------------------------------------------------------------------


def _run_chunk(
    chunk: list[dict[str, Any]], goals: list[Goal]
) -> list[Tier1Verdict | None]:
    """Try the batched call; on any failure, fall back to per-item calls."""
    try:
        return list(tier1.run_batch(chunk, goals))
    except Exception as batch_err:  # noqa: BLE001
        log.warning(
            "tier1_batch_failed_falling_back_to_single",
            extra={"chunk_size": len(chunk), "error": str(batch_err)},
        )

    out: list[Tier1Verdict | None] = []
    for item in chunk:
        try:
            out.append(tier1.run(item, goals))
        except Exception as e:  # noqa: BLE001
            log.warning(
                "tier1_single_failed",
                extra={"item_id": item.get("id"), "error": str(e)},
            )
            out.append(None)
    return out


# ---------------------------------------------------------------------------
# Phase 2: per-item driver — fetch → tier2 → dedup → persist
# ---------------------------------------------------------------------------


def _process_item(
    item: dict[str, Any],
    verdict: Tier1Verdict | None,
    goals: list[Goal],
    counters: dict[str, int],
) -> None:
    item_id = int(item["id"])

    if verdict is None:
        # Tier-1 unrecoverable: do NOT mark seen — retry next batch.
        counters["tier1_error"] += 1
        return

    if verdict.verdict == "drop":
        analysis_store.insert_analysis(
            radar_item_id=item_id, verdict="drop", tier1_reason=verdict.reason
        )
        analysis_store.mark_seen(item_id)
        counters["tier1_dropped"] += 1
        return
    counters["tier1_kept"] += 1

    # --- Fetch -------------------------------------------------------------
    try:
        content, content_status = fetch.run(item)
    except Exception as e:  # noqa: BLE001
        log.warning("fetch_unexpected_raise", extra={"item_id": item_id, "error": str(e)})
        content, content_status = "", "fallback"

    # --- Tier 2 ------------------------------------------------------------
    try:
        analysis = tier2.run(item, content, content_status, goals)
    except Exception as e:  # noqa: BLE001
        # Symmetric with tier-1: do NOT persist or mark seen, so a transient
        # LLM failure retries next batch instead of freezing an empty analysis
        # forever (radar_analyses is UNIQUE per item, with no reanalyze path).
        log.warning("tier2_failed", extra={"item_id": item_id, "error": str(e)})
        counters["tier2_error"] += 1
        return

    if content_status == "fallback":
        counters["tier2_fallback"] += 1
    else:
        counters["tier2_ok"] += 1

    # --- Dedup gate --------------------------------------------------------
    outcome = dedup.run(analysis.summary)
    if outcome.status == "duplicate":
        counters["dedup_duplicate"] += 1
        analysis_store.insert_analysis(
            radar_item_id=item_id,
            verdict="keep",
            tier1_reason=verdict.reason,
            summary=analysis.summary,
            impact_md=analysis.impact,
            score=analysis.score,
            tags=list(analysis.tags),
            content_status=content_status,
            dedup_status="duplicate",
            dedup_match_id=outcome.matched_topic_id,
        )
        if outcome.matched_topic_id is not None:
            try:
                analysis_store.append_item_to_topic(
                    topic_id=outcome.matched_topic_id, item_id=item_id
                )
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "dedup_append_failed",
                    extra={
                        "item_id": item_id,
                        "topic_id": outcome.matched_topic_id,
                        "error": str(e),
                    },
                )
    else:
        counters["dedup_novel"] += 1
        new_topic_id: int | None = None
        if outcome.embedding is not None:
            try:
                new_topic_id = analysis_store.insert_topic(
                    summary=analysis.summary, embedding=outcome.embedding, item_id=item_id
                )
            except Exception as e:  # noqa: BLE001
                log.warning("topic_insert_failed", extra={"item_id": item_id, "error": str(e)})
        analysis_store.insert_analysis(
            radar_item_id=item_id,
            verdict="keep",
            tier1_reason=verdict.reason,
            summary=analysis.summary,
            impact_md=analysis.impact,
            score=analysis.score,
            tags=list(analysis.tags),
            content_status=content_status,
            dedup_status="novel",
            dedup_match_id=new_topic_id,
        )

    analysis_store.mark_seen(item_id)


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------


def _empty_counters() -> dict[str, int]:
    return {
        "items_total": 0,
        "tier1_kept": 0,
        "tier1_dropped": 0,
        "tier1_error": 0,
        "tier2_ok": 0,
        "tier2_fallback": 0,
        "tier2_error": 0,
        "dedup_novel": 0,
        "dedup_duplicate": 0,
        "item_error": 0,
    }


__all__ = ["run"]
