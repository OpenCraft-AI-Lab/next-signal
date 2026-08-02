"""Measure output-language conformance for the radar and knowledge agents.

Replays the real stages over already-pulled `radar_items` and reports what
language each LLM-written field actually came back in. Writes nothing to any
production table — results land as JSON under `PACA_AGENT_TMP_DIR/lang-probe/`.

Why this exists separately from `radar_eval.py`: that harness measures *scores*
against hand-labelled expectations. This one measures language, which is a
different failure mode with a different noise profile — `knowledge_frontmatter`
returns the same article in different languages on different runs, so repeats
are mandatory even though the metric is binary.

What is identical to production: the same `tier1.run_batch` at the same chunk
size, the same `fetch.run` (snapshotted once, then replayed so a variant
comparison isolates the prompt), the same `tier2.run` including the opinion
ceiling, the same `write_frontmatter` input shape, and the real agent loader —
so the language rule is composed exactly as it is in a real run, whichever way
it is delivered (in-place `{{OUTPUT_LANGUAGE}}` substitution, or the appended
block for prompts that carry no token).

Usage::

    python scripts/lang_probe.py snapshot --items en --limit 10
    SIGNAL_OUTPUT_LANG=zh python scripts/lang_probe.py run \\
        --agent radar --items en --limit 10 --repeats 3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
import time
from collections import defaultdict
from typing import Any

import psycopg
from psycopg.rows import dict_row

from paca.agents.loader import build_from_name
from paca.agents.structured import run_structured
from paca.core.context import LANGUAGE_TOKEN, OUTPUT_LANG_ENV, output_language
from paca.core.db import database_url
from paca.core.paths import AGENT_TMP_DIR
from paca.workflows.info_radar_analysis.goals import load_goals
from paca.workflows.info_radar_analysis.runner import _BATCH_SIZE
from paca.workflows.info_radar_analysis.stages import fetch, tier1, tier2
from paca.workflows.stages.knowledge_ingest.schemas import FrontmatterDraft

OUT_DIR = AGENT_TMP_DIR / "lang-probe"
CACHE_PATH = OUT_DIR / "content_cache.json"

_ITEM_COLS = "id, source, source_id, url, title, excerpt, published_at, fetched_at, payload"
_MAX_MARKDOWN_CHARS = 16000

_CJK = re.compile(r"[一-鿿㐀-䶿]")
_LATIN = re.compile(r"[A-Za-z]")

# Goal names are English identifiers the prompts REQUIRE the model to cite. In a
# one-sentence tier-1 reason they outweigh the Chinese prose around them
# ("ai_robotics_space_investment" is 28 Latin characters), which drags a fully
# Chinese reason under any sane threshold. Strip them before measuring.
_GOAL_NAMES = (
    "ai_capability_frontier",
    "ai_robotics_space_investment",
    "startup_opportunity_scouting",
)


def lang_stats(text: str | None) -> dict[str, Any]:
    """CJK-vs-Latin mix of a string, plus a coarse label.

    The ratio is over letters only, so punctuation and digits cannot move it.
    Chinese technical prose keeps many English proper nouns and measures
    0.35-0.80 here; English prose measures 0.00-0.02. `cjk_ratio == 0` is the
    unambiguous "wrong language" signal for a Chinese target — a Chinese title
    carrying English product names is correct output, not a defect.
    """
    text = text or ""
    for g in _GOAL_NAMES:
        text = text.replace(g, "")
    cjk, latin = len(_CJK.findall(text)), len(_LATIN.findall(text))
    total = cjk + latin
    ratio = (cjk / total) if total else 0.0
    if total < 10:
        label = "empty"
    elif ratio >= 0.30:
        label = "zh"
    elif ratio <= 0.05:
        label = "en"
    else:
        label = "mixed"
    return {"cjk": cjk, "latin": latin, "cjk_ratio": round(ratio, 4), "lang": label}


def _connect() -> psycopg.Connection:
    return psycopg.connect(database_url(), row_factory=dict_row)


def select_items(kind: str, limit: int) -> list[dict[str, Any]]:
    """Production-kept items whose source language is `kind`.

    Judged on the title: the corpus has no usable `entries.language`. `en` is a
    small set so it is taken in id order; `zh` is sampled deterministically
    across the whole corpus rather than taking the oldest N, which would all
    come from one week of feeds.
    """
    cjk_op = "!~" if kind == "en" else "~"
    order = "i.id" if kind == "en" else "md5(i.id::text)"
    cols = ", ".join(f"i.{c}" for c in _ITEM_COLS.split(", "))
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""SELECT {cols} FROM radar_items i
                JOIN radar_analyses a ON a.radar_item_id = i.id
                WHERE i.title {cjk_op} '[一-鿿]' AND a.verdict = 'keep'
                ORDER BY {order} LIMIT %s""",
            (limit,),
        )
        return list(cur.fetchall())


def cmd_snapshot(args: argparse.Namespace) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    items = select_items(args.items, args.limit)
    print(f"snapshotting {len(items)} {args.items} items", flush=True)
    for item in items:
        key = str(item["id"])
        if key in cache and not args.force:
            continue
        try:
            content, status = fetch.run(item)
        except Exception as e:  # noqa: BLE001 — one dead fetch must not kill the batch
            print(f"  {key} FETCH FAILED {e}", flush=True)
            continue
        cache[key] = {
            "title": item["title"],
            "content": content,
            "content_status": status,
            "content_lang": lang_stats(content),
        }
        print(f"  {key} {status} {len(content)}ch {cache[key]['content_lang']['lang']}", flush=True)
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
    print(f"cache holds {len(cache)} items -> {CACHE_PATH}", flush=True)


def _instruction_digest(agent_name: str) -> str:
    return hashlib.sha256(
        str(build_from_name(agent_name).instructions).encode()
    ).hexdigest()[:12]


def _assert_language_applied(agent_name: str, target: str) -> str:
    """Fail loud unless the built agent really names the target language.

    Checks the composed instructions rather than a prompt file, so it covers
    both delivery paths (in-place ``{{OUTPUT_LANGUAGE}}`` substitution and the
    appended block). A probe that silently measures the wrong prompt reports
    "the fix changed nothing" and is worse than no probe at all — that happened
    once during this change's investigation via a bind mount that quietly did
    not apply.

    Returns the instruction digest so the caller can detect the prompts being
    edited mid-run — ``prompts/`` is bind-mounted live, so a run started before
    an edit silently measures a mix of two prompt versions.
    """
    instructions = str(build_from_name(agent_name).instructions)
    if LANGUAGE_TOKEN in instructions:
        sys.exit(f"ABORT: {agent_name} shipped an unsubstituted {LANGUAGE_TOKEN}")
    expected = {"zh": "Simplified Chinese", "en": "English"}[target]
    if expected not in instructions:
        sys.exit(
            f"ABORT: {agent_name}'s instructions never name {expected!r}. "
            f"Is {OUTPUT_LANG_ENV} set, and does the agent set output_language: false?"
        )
    digest = _instruction_digest(agent_name)
    print(f"  {agent_name}: names {expected} (instructions {digest})", flush=True)
    return digest


def _run_radar(items, cache, goals, repeats, target, result) -> None:
    for rep in range(repeats):
        for start in range(0, len(items), _BATCH_SIZE):
            chunk = items[start : start + _BATCH_SIZE]
            try:
                verdicts = tier1.run_batch(chunk, goals)
            except Exception as e:  # noqa: BLE001
                print(f"  t1 rep{rep} FAILED {e}", flush=True)
                continue
            for item, v in zip(chunk, verdicts):
                result["tier1"].append(
                    {"item_id": item["id"], "repeat": rep, "verdict": v.verdict,
                     "reason": v.reason, "reason_lang": lang_stats(v.reason)}
                )
    for rep in range(repeats):
        for item in items:
            snap = cache[str(item["id"])]
            t0 = time.monotonic()
            try:
                a = tier2.run(item, snap["content"], snap["content_status"], goals)
            except Exception as e:  # noqa: BLE001 — mirrors the runner's isolation
                result["tier2"].append({"item_id": item["id"], "repeat": rep, "error": str(e)})
                print(f"  t2 rep{rep} item{item['id']} FAILED {e}", flush=True)
                continue
            row = {
                "item_id": item["id"], "repeat": rep, "score": a.score, "tags": list(a.tags),
                "summary": a.summary, "impact": a.impact,
                "summary_lang": lang_stats(a.summary), "impact_lang": lang_stats(a.impact),
                "elapsed_s": round(time.monotonic() - t0, 1),
            }
            result["tier2"].append(row)
            print(
                f"  t2 rep{rep} item{item['id']} score={a.score} "
                f"sum={row['summary_lang']['lang']} imp={row['impact_lang']['lang']}",
                flush=True,
            )


def _run_frontmatter(items, cache, repeats, result) -> None:
    for rep in range(repeats):
        for item in items:
            snap = cache[str(item["id"])]
            agent = build_from_name("knowledge_frontmatter")
            payload = json.dumps(
                {"source_type": "markitdown", "category": "ai-engineering",
                 "title": snap["title"], "metadata": {},
                 "markdown": snap["content"].strip()[:_MAX_MARKDOWN_CHARS]},
                ensure_ascii=False,
            )
            try:
                d = run_structured(agent, payload, FrontmatterDraft)
            except Exception as e:  # noqa: BLE001
                result["frontmatter"].append({"item_id": item["id"], "repeat": rep, "error": str(e)})
                print(f"  fm rep{rep} item{item['id']} FAILED {e}", flush=True)
                continue
            row = {
                "item_id": item["id"], "repeat": rep, "title": d.title,
                "summary": d.summary, "tags": list(d.tags),
                "title_lang": lang_stats(d.title), "summary_lang": lang_stats(d.summary),
            }
            result["frontmatter"].append(row)
            print(
                f"  fm rep{rep} item{item['id']} title={row['title_lang']['lang']} "
                f"summary={row['summary_lang']['lang']} tags={d.tags[:3]}",
                flush=True,
            )


def cmd_run(args: argparse.Namespace) -> None:
    target = output_language()
    if target is None:
        sys.exit(f"ABORT: set {OUTPUT_LANG_ENV}=zh|en — this probe measures the injected rule")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    items = [i for i in select_items(args.items, args.limit) if str(i["id"]) in cache]
    if not items:
        sys.exit("no snapshotted items — run `snapshot` first")

    agents = ["radar_tier1_filter", "radar_tier2_impact"] if args.agent == "radar" else ["knowledge_frontmatter"]
    digests = {name: _assert_language_applied(name, target) for name in agents}

    result: dict[str, Any] = {
        "agent": args.agent, "items_kind": args.items, "target_lang": target,
        "repeats": args.repeats, "tier1": [], "tier2": [], "frontmatter": [],
    }
    print(f"{args.agent}: {len(items)} {args.items} items x {args.repeats} repeats -> {target}", flush=True)

    if args.agent == "radar":
        _run_radar(items, cache, load_goals(), args.repeats, target, result)
    else:
        _run_frontmatter(items, cache, args.repeats, result)

    # prompts/ is bind-mounted live: an edit mid-run silently mixes two prompt
    # versions into one result set. Refuse to write a contaminated file.
    for name, before in digests.items():
        after = _instruction_digest(name)
        if after != before:
            sys.exit(
                f"ABORT: {name}'s instructions changed mid-run ({before} -> {after}). "
                "The prompts were edited while this was running; results discarded."
            )
    result["digests"] = digests

    out = OUT_DIR / f"{args.agent}_{args.items}2{target}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    _report(result, target)
    print(f"wrote {out}", flush=True)


def _report(result: dict[str, Any], target: str) -> None:
    fields = (
        [("summary", "tier2"), ("impact", "tier2"), ("reason", "tier1")]
        if result["agent"] == "radar"
        else [("title", "frontmatter"), ("summary", "frontmatter")]
    )
    print(f"\n=== {result['agent']} {result['items_kind']} -> {target} ===")
    for field, bucket in fields:
        rows = [r for r in result[bucket] if "error" not in r and f"{field}_lang" in r]
        if not rows:
            continue
        # The unambiguous defect: prose entirely in the wrong language. A
        # Chinese summary carrying English product names is correct output, so
        # for a zh target only a zero-CJK field counts as wrong.
        def _wrong(row: dict[str, Any]) -> bool:
            ratio = row[f"{field}_lang"]["cjk_ratio"]
            return ratio == 0.0 if target == "zh" else ratio >= 0.30

        bad = [r for r in rows if _wrong(r)]
        by = defaultdict(list)
        for r in rows:
            by[r["item_id"]].append(_wrong(r))
        flip = sorted(k for k, v in by.items() if any(v) and not all(v))
        ratios = [r[f"{field}_lang"]["cjk_ratio"] for r in rows]
        print(
            f"  {field:<8} defect {len(bad):>2}/{len(rows):<3} "
            f"({100 * len(bad) / len(rows):>5.1f}%)  "
            f"cjk_ratio {statistics.mean(ratios):.3f} "
            f"[{min(ratios):.3f}..{max(ratios):.3f}]"
        )
        # Flipping is the failure a single pass cannot see — always name it.
        print(f"  {'':<8} items flipping between runs: {flip or 'none'}")
    errs = [r for b in ("tier2", "frontmatter") for r in result[b] if "error" in r]
    if errs:
        print(f"  errors: {len(errs)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("snapshot")
    s.add_argument("--items", choices=["en", "zh"], required=True)
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_snapshot)

    r = sub.add_parser("run")
    r.add_argument("--agent", choices=["radar", "frontmatter"], required=True)
    r.add_argument("--items", choices=["en", "zh"], required=True)
    r.add_argument("--limit", type=int, default=10)
    r.add_argument("--repeats", type=int, default=3)
    r.set_defaults(func=cmd_run)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
