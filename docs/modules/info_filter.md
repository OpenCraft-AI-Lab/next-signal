# Module: info_filter (information collection and filtering)

> **English** · [中文](../zh/modules/info_filter.md)

## What it solves

Collect external information streams and filter them down to signal. The current
instance is **info-radar**: periodically pull the Folo / source CLIs and write
`radar_items`; then a two-tier local-LLM analysis scores relevance and impact and
deduplicates according to `configs/info_radar/goals.yaml`, writing
`radar_analyses` / `radar_pushed_topics`. The dashboard `/radar` page handles
reading and manual triggering.

## Where the code lives

`src/paca/collectors/info_radar/` — the LLM-free collector, source CLI →
`radar_items`.
`src/paca/integrations/info_radar/` — provider adapters (Folo, YouTube subtitles).
`src/paca/workflows/info_radar_pull.py` — the collector's manual-run thin shell.
`src/paca/workflows/info_radar_analysis/` — the two-tier LLM analysis pipeline.

## Agents

| Agent | Model profile | Used for |
|---|---|---|
| `radar_tier1_filter` | local_structured | Batched tier-1 relevance filter; keep/drop against the goals |
| `radar_tier2_impact` | local_structured | Per-item full-content impact summary / score / tags |
| `radar_dedup_judge` | local_structured | LLM duplicate/novel verdict after pgvector candidate retrieval |

## Tools

- info-radar collector: `uv run paca info-radar pull [--source NAME]`.
- info-radar analysis: `uv run paca info-radar analyze [--limit N] [--source NAME]`.
- Folo subscriptions inventory: `uv run paca info-radar subscriptions --json`.

## External systems

- **Folo CLI** (`paca.integrations.info_radar.folo`) — info-radar source, full
  content, and subscriptions. Defaults to `npx --yes folocli@0.0.5`, overridable
  with `FOLO_CLI_ARGV`. The dashboard's `/radar` Ingest first pulls the full text
  with `folocli entry get <source_id>` and stages it as HTML under
  `PACA_AGENT_TMP_DIR` before handing off to the knowledge pipeline; non-Folo
  sources still go through `radar_items.url`.
- **YouTube native subtitles** (`paca.integrations.info_radar.youtube_subs`) —
  audio-free subtitle enrichment for YouTube items.

## Where data lives

- info-radar raw items: Postgres `radar_items`
- info-radar analyses: Postgres `radar_analyses`
- info-radar dedup memory: Postgres `radar_pushed_topics` (pgvector, 1024-dim)
- info-radar goals: `configs/info_radar/goals.yaml` (editable from the dashboard
  `/goals` page)
- info-radar sources: `configs/info_radar/sources.yaml`

## Invariants

- `radar_items.seen_at` is written **only** by the analysis layer; the collector
  writes raw items only.
- `radar_analyses.radar_item_id` is a unique key. Analysis only processes rows
  where `seen_at IS NULL`, and writes `seen_at` only after the analysis row is
  committed — which is what keeps reruns idempotent at any cadence.
- When `configs/info_radar/goals.yaml` is missing or invalid, analysis fails loud.
- If a tier-1 batch response does not match the expected structure, fall back to
  single-item processing; one failing item must never block the batch.
- Items that fail tier-1 or tier-2 get no analysis row and no `seen_at`, leaving
  them for the next run. (Given the unique key on `radar_analyses` and the
  absence of a reanalyze command, writing an empty row would freeze a transient
  failure permanently.)
- Tier-2 scoring is a two-step rubric defined in the prompt: anchor a base score,
  then adjust within ±3 bands across three dimensions. The ≤65 ceiling for the
  `opinion` tag is backstopped in code
  (`stages/tier2.py::_apply_ceilings`), and high-signal individuals named in the
  goals are exempted via a prompt-driven `frontier-voice` tag.
- When dedup embedding fails, treat the item conservatively as novel — never
  silently drop it.
- Never dump a whole provider dict into the logger.

## Specs and status

Specs: [`openspec/specs/info-radar/`](../../openspec/specs/info-radar/),
[`openspec/specs/info-radar-analysis/`](../../openspec/specs/info-radar-analysis/),
[`openspec/specs/dashboard-radar-reader/`](../../openspec/specs/dashboard-radar-reader/).

Current status: info-radar pull, analysis, the dashboard reader, the goals
editor, and the Folo subscriptions table are all in place. There is no background
scheduler — both pull and analysis are **manually triggered**, via
`paca info-radar pull|analyze`, `paca run-workflow <name>`, or the dashboard
`/radar` page's Pull + Analyze.

The dashboard's `Pull + Analyze` shows **live analyze progress**: after pulling,
the action writes the unanalyzed-item count (the denominator) plus an
`analyzeRunning` flag into `~/.next-signal/radar-state.json`, then spawns
`info-radar analyze` as a **tracked** (not detached) child, flipping
`analyzeRunning` back to false when it exits. The page drives a `done/total`
progress bar from `GET /api/radar/run` (~1.5s polling, where `done` is the
`radar_analyses` row count since the most recent analyze), and throttles
refreshes while running so the `TodayTracker` counts tick live. The bar's running
state is read from `radar-state.json` at page load, so a refresh resumes it. This
covers dashboard-triggered runs only (CLI runs show no progress bar), and
restarting the dashboard can leave an in-flight `analyzeRunning` set until the
next run — best-effort, with the child process and DB writes unaffected.
