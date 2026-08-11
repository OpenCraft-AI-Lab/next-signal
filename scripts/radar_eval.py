"""Offline evaluation harness for the info-radar tier-1 / tier-2 prompts.

Replays the real analysis stages over a curated, hand-labelled subset of
``radar_items`` and records every verdict / score into dedicated ``radar_eval_*``
tables, so prompt edits can be measured instead of argued about.

Why a separate harness rather than ``next-signal info-radar analyze``:

  * ``radar_analyses`` is ``UNIQUE(radar_item_id)`` with ``ON CONFLICT DO
    NOTHING`` and the runner calls ``mark_seen`` before fetch — production rows
    are write-once, so the same item can never be re-scored in place.
  * We need N repeats of the same item to see through sampling noise
    (``local_structured`` runs at temperature 0.2, so scores are not stable).

What is identical to production: the same ``tier1.run_batch`` (same chunk size),
the same ``fetch.run``, the same ``tier2.run`` (ceilings included), the same
agents, prompts and ``goals.yaml``.

What is deliberately skipped: the dedup gate. It writes to
``radar_pushed_topics`` — shared production state — and does not influence
verdict or score, which is what we are measuring.

Article content is snapshotted at ``load`` time and replayed on every ``run``,
so a variant comparison comes out of the prompt alone and not out of whether
folocli happened to answer that day.

Usage::

    uv run python scripts/radar_eval.py init
    uv run python scripts/radar_eval.py load  --cases configs/info_radar/eval_cases.yaml
    uv run python scripts/radar_eval.py run   --variant baseline --repeats 3
    uv run python scripts/radar_eval.py report --variant baseline
    uv run python scripts/radar_eval.py report --variant tuned --against baseline
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import statistics
import sys
from typing import Any

import psycopg
import yaml

from next_signal.agents.stage import stage_job, stage_job_provenance
from next_signal.core.db import database_url
from next_signal.core.paths import CONFIGS_DIR, PROMPTS_DIR
from next_signal.workflows.info_radar_analysis.goals import goals_path, load_goals
from next_signal.workflows.info_radar_analysis.runner import _BATCH_SIZE
from next_signal.workflows.info_radar_analysis.stages import fetch, tier1, tier2

log = logging.getLogger("radar_eval")

# Qualified with the `i` alias — every query below joins radar_items AS i
# alongside radar_eval_cases AS c, which also has an `id`.
_ITEM_COLS = (
    "i.id, i.source, i.source_id, i.url, i.title, i.excerpt, "
    "i.published_at, i.fetched_at, i.payload"
)

DDL = """
CREATE TABLE IF NOT EXISTS radar_eval_cases (
    id              BIGSERIAL PRIMARY KEY,
    label_set       TEXT NOT NULL,
    radar_item_id   BIGINT NOT NULL REFERENCES radar_items(id) ON DELETE CASCADE,
    bucket          TEXT NOT NULL,
    expect_verdict  TEXT NOT NULL,
    expect_min      INTEGER,
    expect_max      INTEGER,
    rationale       TEXT NOT NULL,
    content         TEXT,
    content_status  TEXT,
    UNIQUE (label_set, radar_item_id)
);

CREATE TABLE IF NOT EXISTS radar_eval_runs (
    id              BIGSERIAL PRIMARY KEY,
    label_set       TEXT NOT NULL,
    variant         TEXT NOT NULL,
    prompt_digest   TEXT NOT NULL,
    repeats         INTEGER NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS radar_eval_results (
    id              BIGSERIAL PRIMARY KEY,
    run_id          BIGINT NOT NULL REFERENCES radar_eval_runs(id) ON DELETE CASCADE,
    case_id         BIGINT NOT NULL REFERENCES radar_eval_cases(id) ON DELETE CASCADE,
    repeat_idx      INTEGER NOT NULL,
    verdict         TEXT,
    tier1_reason    TEXT,
    score           INTEGER,
    tags            JSONB NOT NULL DEFAULT '[]',
    summary         TEXT,
    impact_md       TEXT,
    error           TEXT,
    UNIQUE (run_id, case_id, repeat_idx)
);
"""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _connect() -> psycopg.Connection:
    return psycopg.connect(database_url())


def prompt_digest(engine: dict[str, object] | None = None) -> str:
    """Fingerprint of prompts, goals, and the frozen engine configuration."""
    h = hashlib.sha256()
    for p in (
        PROMPTS_DIR / "agents" / "radar_tier1_filter.md",
        PROMPTS_DIR / "agents" / "radar_tier2_impact.md",
        goals_path(),
    ):
        h.update(p.read_bytes())
    if engine is not None:
        h.update(json.dumps(engine, sort_keys=True, separators=(",", ":")).encode())
    return h.hexdigest()[:12]


def _notes_with_engine(notes: str | None, engine: dict[str, object]) -> str:
    provenance = "engine=" + json.dumps(engine, sort_keys=True, separators=(",", ":"))
    return f"{notes}\n{provenance}" if notes else provenance


def _rows(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------


def cmd_init(_args) -> int:
    with _connect() as conn:
        conn.execute(DDL)
    print("radar_eval_cases / radar_eval_runs / radar_eval_results ready")
    return 0


def cmd_load(args) -> int:
    """Upsert the case set, then snapshot article content for every case."""
    spec = yaml.safe_load((CONFIGS_DIR / "info_radar" / args.cases).read_text("utf-8"))
    # --label-set loads the same gold labels under a second name, so a change
    # to fetch.py can be A/B'd on content while the labels stay fixed.
    label_set = args.label_set or spec["label_set"]
    cases = spec["cases"]

    with _connect() as conn:
        for c in cases:
            conn.execute(
                """
                INSERT INTO radar_eval_cases
                    (label_set, radar_item_id, bucket, expect_verdict,
                     expect_min, expect_max, rationale)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (label_set, radar_item_id) DO UPDATE SET
                    bucket = EXCLUDED.bucket,
                    expect_verdict = EXCLUDED.expect_verdict,
                    expect_min = EXCLUDED.expect_min,
                    expect_max = EXCLUDED.expect_max,
                    rationale = EXCLUDED.rationale
                """,
                (
                    label_set,
                    c["item"],
                    c["bucket"],
                    c["expect"],
                    c.get("min"),
                    c.get("max"),
                    c["why"],
                ),
            )
        conn.commit()

        # Snapshot content for every case (not just tier-1 keeps) so a variant
        # that flips drop -> keep still has a body to score.
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT c.id AS case_id, {_ITEM_COLS}
                      FROM radar_eval_cases c
                      JOIN radar_items i ON i.id = c.radar_item_id
                     WHERE c.label_set = %s AND c.content IS NULL""",
                (label_set,),
            )
            pending = _rows(cur)

        for n, row in enumerate(pending, 1):
            case_id = row.pop("case_id")
            content, status = fetch.run(row)
            conn.execute(
                "UPDATE radar_eval_cases SET content=%s, content_status=%s WHERE id=%s",
                (content, status, case_id),
            )
            conn.commit()
            print(f"  [{n}/{len(pending)}] item {row['id']} {status} ({len(content)} chars)")

    print(f"label_set={label_set}: {len(cases)} cases, {len(pending)} newly fetched")
    return 0


def _load_cases(conn, label_set: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT c.id AS case_id, c.bucket, c.expect_verdict, c.expect_min,
                       c.expect_max, c.content, c.content_status, {_ITEM_COLS}
                  FROM radar_eval_cases c
                  JOIN radar_items i ON i.id = c.radar_item_id
                 WHERE c.label_set = %s
                 ORDER BY c.radar_item_id""",
            (label_set,),
        )
        return _rows(cur)


def cmd_run(args) -> int:
    goals = load_goals()

    with stage_job() as engine_state, _connect() as conn:
        initial_engine = stage_job_provenance(engine_state)
        digest = prompt_digest(initial_engine)
        cases = _load_cases(conn, args.label_set)
        if not cases:
            raise RuntimeError(f"no cases for label_set={args.label_set}; run `load` first")

        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO radar_eval_runs
                       (label_set, variant, prompt_digest, repeats, notes)
                   VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                (
                    args.label_set,
                    args.variant,
                    digest,
                    args.repeats,
                    _notes_with_engine(args.notes, initial_engine),
                ),
            )
            run_id = cur.fetchone()[0]
        conn.commit()

        print(f"run {run_id}: variant={args.variant} digest={digest} "
              f"cases={len(cases)} repeats={args.repeats}")

        batch_size = args.batch_size or _BATCH_SIZE
        for rep in range(args.repeats):
            # Tier 1, batched exactly as production does it (--batch-size 1
            # isolates each item from its batch neighbours).
            verdicts: list[Any] = []
            for start in range(0, len(cases), batch_size):
                chunk = cases[start : start + batch_size]
                try:
                    verdicts.extend(tier1.run_batch(chunk, goals))
                except Exception as e:  # noqa: BLE001 — mirror runner's fallback
                    log.warning("batch failed, falling back: %s", e)
                    for item in chunk:
                        try:
                            verdicts.append(tier1.run(item, goals))
                        except Exception as e2:  # noqa: BLE001
                            log.warning("item %s tier1 failed: %s", item["id"], e2)
                            verdicts.append(None)

            for case, verdict in zip(cases, verdicts):
                score = tags = summary = impact = reason = err = None
                vstr = None
                if verdict is None:
                    err = "tier1_error"
                else:
                    vstr, reason = verdict.verdict, verdict.reason
                    if vstr == "keep":
                        try:
                            a = tier2.run(
                                case,
                                case["content"] or "",
                                case["content_status"] or "fallback",
                                goals,
                            )
                            score, tags = a.score, list(a.tags)
                            summary, impact = a.summary, a.impact
                        except Exception as e:  # noqa: BLE001
                            err = f"tier2_error: {e}"

                conn.execute(
                    """INSERT INTO radar_eval_results
                           (run_id, case_id, repeat_idx, verdict, tier1_reason,
                            score, tags, summary, impact_md, error)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (run_id, case["case_id"], rep, vstr, reason, score,
                     json.dumps(tags or []), summary, impact, err),
                )
                conn.commit()
                print(f"  rep{rep} item {case['id']:>4} {vstr or 'ERR':<5} "
                      f"{score if score is not None else '':>4}  {case['title'][:48]}")

        final_engine = stage_job_provenance(engine_state)
        digest = prompt_digest(final_engine)
        conn.execute(
            """UPDATE radar_eval_runs
                  SET prompt_digest=%s, notes=%s, finished_at=now()
                WHERE id=%s""",
            (digest, _notes_with_engine(args.notes, final_engine), run_id),
        )
        conn.commit()

    print(f"\nrun {run_id} complete — report with: "
          f"uv run python scripts/radar_eval.py report --run-id {run_id}")
    return 0


def _report_inversions(by_item: dict[int, list[dict]]) -> None:
    """Pairwise industry-vs-paper ranking check.

    The user's actual complaint is an ordering one — "a narrow OCR paper
    outranks a frontier model launch" — so measure it directly. Immune to
    absolute-scale drift, which band pass/fail is not.
    """
    def means(bucket: str) -> list[tuple[int, float]]:
        out = []
        for item_id, reps in by_item.items():
            if reps[0]["bucket"] != bucket:
                continue
            scores = [r["score"] for r in reps if r["score"] is not None]
            if scores:
                out.append((item_id, statistics.mean(scores)))
        return sorted(out)

    ind, pap = means("IND-surface"), means("PAP-low")
    if not ind or not pap:
        return

    bad = [(i, si, p, sp) for i, si in ind for p, sp in pap if si < sp]
    n = len(ind) * len(pap)
    print(f"\n--- industry-vs-paper ordering ({len(ind)}x{len(pap)} = {n} pairs) ---")
    print(f"  inversions: {len(bad)}/{n}  ({100*len(bad)/n:.0f}% of pairs have a paper above an industry item)")
    print(f"  mean score: industry {statistics.mean(s for _, s in ind):.1f} "
          f"vs paper {statistics.mean(s for _, s in pap):.1f} "
          f"(gap {statistics.mean(s for _, s in ind) - statistics.mean(s for _, s in pap):+.1f})")
    for i, si, p, sp in sorted(bad, key=lambda x: x[3] - x[1], reverse=True)[:6]:
        print(f"    item {p} ({sp:.0f}) over item {i} ({si:.0f})   -{sp-si:.0f}")


def _fetch_results(conn, run_id: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT r.*, c.bucket, c.expect_verdict, c.expect_min, c.expect_max,
                      c.radar_item_id, i.title
                 FROM radar_eval_results r
                 JOIN radar_eval_cases c ON c.id = r.case_id
                 JOIN radar_items i ON i.id = c.radar_item_id
                WHERE r.run_id = %s
                ORDER BY c.radar_item_id, r.repeat_idx""",
            (run_id,),
        )
        return _rows(cur)


def _resolve_run(conn, args) -> int:
    if args.run_id:
        return args.run_id
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id FROM radar_eval_runs WHERE variant=%s
               ORDER BY started_at DESC LIMIT 1""",
            (args.variant,),
        )
        row = cur.fetchone()
    if not row:
        raise RuntimeError(f"no run found for variant={args.variant}")
    return row[0]


def cmd_report(args) -> int:
    with _connect() as conn:
        run_id = _resolve_run(conn, args)
        rows = _fetch_results(conn, run_id)
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM radar_eval_runs WHERE id=%s", (run_id,))
            meta = _rows(cur)[0]
        # production scores for the same items, for drift comparison
        with conn.cursor() as cur:
            cur.execute(
                """SELECT c.radar_item_id, a.verdict, a.score
                     FROM radar_eval_cases c
                     JOIN radar_analyses a ON a.radar_item_id = c.radar_item_id
                    WHERE c.label_set = %s""",
                (meta["label_set"],),
            )
            prod = {r["radar_item_id"]: r for r in _rows(cur)}

    by_item: dict[int, list[dict]] = {}
    for r in rows:
        by_item.setdefault(r["radar_item_id"], []).append(r)

    print(f"\n=== run {run_id} | variant={meta['variant']} | digest={meta['prompt_digest']} "
          f"| repeats={meta['repeats']} ===\n")

    buckets: dict[str, list[bool]] = {}
    flips = 0
    spreads: list[int] = []
    print(f"{'item':>5} {'bucket':<18} {'want':<16} {'got':<22} {'prod':>5}  title")
    for item_id, reps in sorted(by_item.items()):
        exp_v = reps[0]["expect_verdict"]
        lo, hi = reps[0]["expect_min"], reps[0]["expect_max"]
        bucket = reps[0]["bucket"]
        got_v = {r["verdict"] for r in reps}
        scores = [r["score"] for r in reps if r["score"] is not None]
        if len(got_v) > 1:
            flips += 1
        if len(scores) > 1:
            spreads.append(max(scores) - min(scores))

        ok = exp_v in got_v and len(got_v) == 1
        if ok and exp_v == "keep" and scores:
            m = statistics.mean(scores)
            ok = (lo is None or m >= lo) and (hi is None or m <= hi)
        buckets.setdefault(bucket, []).append(bool(ok))

        want = exp_v + (f" {lo or 0}-{hi or 100}" if exp_v == "keep" else "")
        got = "/".join(sorted(x or "ERR" for x in got_v))
        if scores:
            got += f" {min(scores)}-{max(scores)}" if len(set(scores)) > 1 else f" {scores[0]}"
        p = prod.get(item_id) or {}
        pstr = str(p.get("score") or ("drop" if p.get("verdict") == "drop" else "-"))
        mark = "✔" if ok else "✘"
        print(f"{mark}{item_id:>4} {bucket:<18} {want:<16} {got:<22} {pstr:>5}  {reps[0]['title'][:40]}")

    print("\n--- per-bucket pass rate ---")
    for b, oks in sorted(buckets.items()):
        print(f"  {b:<20} {sum(oks):>2}/{len(oks):<3} {100*sum(oks)/len(oks):5.0f}%")
    total = [o for oks in buckets.values() for o in oks]
    print(f"  {'OVERALL':<20} {sum(total):>2}/{len(total):<3} {100*sum(total)/len(total):5.0f}%")

    _report_inversions(by_item)

    if meta["repeats"] > 1:
        print(f"\n--- stability across {meta['repeats']} repeats ---")
        print(f"  verdict flips: {flips}/{len(by_item)} items")
        if spreads:
            print(f"  score spread: mean {statistics.mean(spreads):.1f}, max {max(spreads)}")
            print(f"  items with spread >= 10: {sum(1 for s in spreads if s >= 10)}/{len(spreads)}")
    return 0


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(fn=cmd_init)

    p = sub.add_parser("load")
    p.add_argument("--cases", default="eval_cases.yaml")
    p.add_argument("--label-set", default=None,
                   help="override the YAML's label_set (re-snapshots content)")
    p.set_defaults(fn=cmd_load)

    p = sub.add_parser("run")
    p.add_argument("--variant", required=True)
    p.add_argument("--label-set", default="v1")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--batch-size", type=int, default=None,
                   help="tier-1 chunk size; defaults to the production value")
    p.add_argument("--notes", default=None)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("report")
    p.add_argument("--run-id", type=int)
    p.add_argument("--variant")
    p.add_argument("--against")
    p.set_defaults(fn=cmd_report)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
