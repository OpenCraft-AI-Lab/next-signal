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
    python scripts/lang_probe.py run \\
        --agent radar --items en --limit 10 --repeats 3 --target zh

`--target` is required on `run`, and means different things per agent:

- `radar` / `frontmatter` resolve the `global` policy, so `--target` is the
  language to aim at. This points `paca.core.language.global_language` at it for
  this process only, never writing the real preference file (the dashboard's
  settings panel owns it).
- `cleaner` resolves `same_as_source`, where the expected output is each item's
  own detected language and no single target exists. There `--target` is the
  **adversary**: the `global` setting is pointed at it so that a body drifting
  toward the operator's preference — the exact failure `same_as_source` exists
  to prevent — registers as a defect instead of passing silently. Point it at
  the opposite of the corpus language.
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
from paca.core import language as language_module
from paca.core.db import database_url
from paca.core.language import LANGUAGE_TOKEN
from paca.core.language_detect import detect_language
from paca.core.paths import AGENT_TMP_DIR
from paca.workflows.info_radar_analysis.goals import load_goals
from paca.workflows.info_radar_analysis.runner import _BATCH_SIZE
from paca.workflows.info_radar_analysis.stages import fetch, tier1, tier2
from paca.workflows.stages.knowledge_ingest.artifact_editor import (
    _MAX_MARKDOWN_CHARS as _PROD_MAX_MARKDOWN_CHARS,
)
from paca.workflows.stages.knowledge_ingest.artifact_editor import (
    _content_length,
    _strip_code_fence,
)
from paca.workflows.stages.knowledge_ingest.schemas import FrontmatterDraft

OUT_DIR = AGENT_TMP_DIR / "lang-probe"
CACHE_PATH = OUT_DIR / "content_cache.json"

_ITEM_COLS = "id, source, source_id, url, title, excerpt, published_at, fetched_at, payload"

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
    return hashlib.sha256(str(build_from_name(agent_name).instructions).encode()).hexdigest()[:12]


def _assert_language_applied(agent_name: str, target: str) -> str:
    """Fail loud unless the built agent really names the target language.

    Checks the composed instructions rather than a prompt file, so it covers
    both delivery paths (in-place ``{{OUTPUT_LANGUAGE}}`` substitution and the
    appended block). A probe that silently measures the wrong prompt reports
    "the fix changed nothing" and is worse than no probe at all — that happened
    once during this change's investigation via a bind mount that quietly did
    not apply.

    Every agent reached here resolves `global`, so the target arrives through
    the patched `global_language` and no per-call override is passed.

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
            "Check the agent's `extra.output_language` policy — `off` would "
            "explain this."
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


def _run_frontmatter(items, cache, repeats, target, result) -> None:
    for rep in range(repeats):
        for item in items:
            snap = cache[str(item["id"])]
            # `knowledge_frontmatter` resolves `global`: no per-call override,
            # exactly as a real ingestion run builds it. The target reaches it
            # through the patched `global_language` in `cmd_run`.
            agent = build_from_name("knowledge_frontmatter")
            payload = json.dumps(
                {"source_type": "markitdown", "category": "ai-engineering",
                 "title": snap["title"], "metadata": {},
                 "markdown": snap["content"].strip()[:_PROD_MAX_MARKDOWN_CHARS]},
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


def _run_cleaner(items, cache, repeats, target, result) -> None:
    """Measure that the cleaned body keeps the article's own language.

    `knowledge_artifact_editor` resolves `same_as_source`, so the override is
    the language `fetch()` detects for this item and the expected output is that
    same language — recorded per row, because there is no single target here.
    `global_language` is meanwhile pointed at `target`, the opposite language,
    so a body that drifts to the operator's preference registers as a defect.

    Retention is recorded alongside: an over-summarized body would move the
    language ratio for reasons that have nothing to do with the language rule.
    It uses production's own `_content_length` (whitespace-stripped UTF-8
    bytes) against the text actually sent, so the number is directly comparable
    to `_MIN_LONG_TEXT_RETENTION` — a raw `len()` ratio is not, because the
    cleaner reformats markdown and shifts whitespace density.
    """
    for rep in range(repeats):
        for item in items:
            snap = cache[str(item["id"])]
            body = snap["content"].strip()[:_PROD_MAX_MARKDOWN_CHARS]
            detected = detect_language(snap["title"] or body)
            agent = build_from_name("knowledge_artifact_editor", language=detected)
            # Every repeat, not just the first: this doubles as the mid-run
            # prompt-drift guard that `cmd_run`'s digest check gives the other
            # agents. `prompts/` is bind-mounted live, so an edit partway
            # through would otherwise mix two prompt versions into one result
            # file silently. The agent is rebuilt per call anyway, so it's free.
            _assert_names_only(agent, detected, target, item["id"])
            payload = json.dumps(
                {"source_type": "markitdown", "title": snap["title"], "markdown": body},
                ensure_ascii=False,
            )
            try:
                response = agent.run(payload)
                cleaned = _strip_code_fence(
                    str(getattr(response, "content", response))
                ).strip()
                if not cleaned:
                    raise RuntimeError("cleaner returned an empty body")
            except Exception as e:  # noqa: BLE001 — mirrors the stage's isolation
                result["cleaner"].append(
                    {"item_id": item["id"], "repeat": rep, "error": str(e)}
                )
                print(f"  cl rep{rep} item{item['id']} FAILED {e}", flush=True)
                continue
            row = {
                "item_id": item["id"], "repeat": rep, "expected": detected,
                "source_lang": snap["content_lang"]["lang"],
                "retention": round(_content_length(cleaned) / max(_content_length(body), 1), 3),
                "body": cleaned[:400],
                "body_lang": lang_stats(cleaned),
            }
            result["cleaner"].append(row)
            print(
                f"  cl rep{rep} item{item['id']} detected={detected} "
                f"body={row['body_lang']['lang']} "
                f"cjk={row['body_lang']['cjk_ratio']:.3f} ret={row['retention']}",
                flush=True,
            )


def _assert_names_only(agent, expected: str, adversary: str, item_id: int) -> None:
    """Fail loud unless this agent's rule targets the detected language, not the setting.

    The negative half is the point: it proves the `global` preference never
    reached a `same_as_source` agent, which a positive-only check cannot show.

    Matches the rule's own directive clause rather than a bare language name —
    `language_rule()` always ends with "tags, slugs, category paths stay
    lowercase English", so a substring check for "English" reports a leak on
    every Chinese-targeted prompt. That false positive is why this is phrased
    against `... your output in <name>`.
    """
    names = {"zh": "Simplified Chinese", "en": "English"}
    directive = "your output in {}".format
    instructions = str(agent.instructions)
    if directive(names[expected]) not in instructions:
        sys.exit(
            f"ABORT: item {item_id}: cleaner rule does not target "
            f"{names[expected]!r} (detected {expected})."
        )
    if expected != adversary and directive(names[adversary]) in instructions:
        sys.exit(
            f"ABORT: item {item_id}: cleaner rule targets the global setting "
            f"{names[adversary]!r} — `same_as_source` leaked `global`."
        )


def cmd_run(args: argparse.Namespace) -> None:
    target = args.target

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    items = [i for i in select_items(args.items, args.limit) if str(i["id"]) in cache]
    if not items:
        sys.exit("no snapshotted items — run `snapshot` first")

    # Patch `global_language` for this process only rather than persisting to
    # the real preference file (which the dashboard's settings panel owns). For
    # `global`-policy agents this is the target; for the cleaner it is the
    # adversary the output must ignore.
    language_module.global_language = lambda: target
    agents = {
        "radar": ["radar_tier1_filter", "radar_tier2_impact"],
        "frontmatter": ["knowledge_frontmatter"],
        "cleaner": [],  # asserted per item against its own detected language
    }[args.agent]
    digests = {name: _assert_language_applied(name, target) for name in agents}

    result: dict[str, Any] = {
        "agent": args.agent, "items_kind": args.items, "target_lang": target,
        "repeats": args.repeats, "tier1": [], "tier2": [], "frontmatter": [],
        "cleaner": [],
    }
    arrow = "vs global" if args.agent == "cleaner" else "->"
    print(
        f"{args.agent}: {len(items)} {args.items} items x {args.repeats} repeats {arrow} {target}",
        flush=True,
    )

    if args.agent == "radar":
        _run_radar(items, cache, load_goals(), args.repeats, target, result)
    elif args.agent == "cleaner":
        _run_cleaner(items, cache, args.repeats, target, result)
    else:
        _run_frontmatter(items, cache, args.repeats, target, result)

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

    # `<items>2<target>` reads as a direction, which is only true for the
    # `global`-policy agents. For the cleaner, `target` is the adversary and the
    # expected output is the corpus's own language, so name it that way.
    stem = (
        f"{args.items}_vs_{target}" if args.agent == "cleaner" else f"{args.items}2{target}"
    )
    out = OUT_DIR / f"{args.agent}_{stem}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    _report(result, target)
    print(f"wrote {out}", flush=True)


def _report(result: dict[str, Any], target: str) -> None:
    fields = {
        "radar": [("summary", "tier2"), ("impact", "tier2"), ("reason", "tier1")],
        "frontmatter": [("title", "frontmatter"), ("summary", "frontmatter")],
        "cleaner": [("body", "cleaner")],
    }[result["agent"]]
    arrow = "vs global" if result["agent"] == "cleaner" else "->"
    print(f"\n=== {result['agent']} {result['items_kind']} {arrow} {target} ===")
    for field, bucket in fields:
        rows = [r for r in result[bucket] if "error" not in r and f"{field}_lang" in r]
        if not rows:
            continue
        # The unambiguous defect: prose entirely in the wrong language. A
        # Chinese summary carrying English product names is correct output, so
        # for a zh expectation only a zero-CJK field counts as wrong. `expected`
        # is per row for `same_as_source`, where each item has its own target.
        def _wrong(row: dict[str, Any]) -> bool:
            expected = row.get("expected", target)
            ratio = row[f"{field}_lang"]["cjk_ratio"]
            return ratio == 0.0 if expected == "zh" else ratio >= 0.30

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
    if result["agent"] == "cleaner":
        rets = [r["retention"] for r in result["cleaner"] if "error" not in r]
        if rets:
            print(
                f"  {'':<8} retention {statistics.mean(rets):.2f} "
                f"[{min(rets):.2f}..{max(rets):.2f}] (a collapsed body moves the ratio too)"
            )
    errs = [r for b in ("tier2", "frontmatter", "cleaner") for r in result[b] if "error" in r]
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
    r.add_argument("--agent", choices=["radar", "frontmatter", "cleaner"], required=True)
    r.add_argument("--items", choices=["en", "zh"], required=True)
    r.add_argument("--limit", type=int, default=10)
    r.add_argument("--repeats", type=int, default=3)
    r.add_argument("--target", choices=["zh", "en"], required=True)
    r.set_defaults(func=cmd_run)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
