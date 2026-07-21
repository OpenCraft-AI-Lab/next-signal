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
`src/paca/workflows/info_radar_recap/` — range-scoped recap synthesis.

## Agents

| Agent | Model profile | Used for |
|---|---|---|
| `radar_tier1_filter` | local_structured | Batched tier-1 relevance filter; keep/drop against the goals |
| `radar_tier2_impact` | local_structured | Per-item full-content impact summary / score / tags |
| `radar_dedup_judge` | local_structured | LLM duplicate/novel verdict after pgvector candidate retrieval |
| `radar_recap` | local_structured | Clusters a date range of kept items into 3-5 themed narratives with citations |

## Tools

- info-radar collector: `uv run paca info-radar pull [--source NAME]`.
- info-radar analysis: `uv run paca info-radar analyze [--limit N] [--source NAME]`.
- info-radar recap: `uv run paca info-radar recap --since D --until D [--min-score N] [--novel-only] [--regenerate]`.
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
- info-radar recaps: Postgres `radar_recaps`, one row per
  `(since, until, min_score, novel_only)`
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
- A recap is identified by `(since, until, min_score, novel_only)`. A repeat
  request is a cache hit; regeneration upserts that row rather than appending.
- Recap ranges are bounded by `analyzed_at` in the radar timezone, inclusive —
  the same convention the day groups use, so a 7-day recap covers exactly the
  seven day rows beneath it. `published_at` is never used (nullable, and it
  would disagree with every other date on the page).
- The recap agent receives `summary`, never `impact_md`: the recap synthesizes
  across items, and the per-item deep dive would triple prompt size for content
  the themes exist to abstract away.
- Selection caps at the top 60 by score. Both `item_count` and
  `considered_count` are persisted so the reader is told when a recap covers a
  subset — the cap is never applied silently.
- Recap citations to unknown ids are dropped; a theme left with no valid
  citation is dropped; if no theme survives, the run is an error and nothing is
  stored as `done`. A regeneration that fails keeps the previous recap readable.
- `radar_recaps` holds **no** foreign key to `radar_items` — citation ids live
  in the `themes` JSONB so a recap survives the 30-day sweep. Readers render a
  citation whose source is gone as plain text.
- A stale recap (further analyses landed in its range) is **labelled**, never
  auto-regenerated: regenerating on load would turn every visit to a live range
  into a minute of local inference.
- Never dump a whole provider dict into the logger.
- Analysis **output language is driven by the request locale** (`run(locale=)` /
  `analyze --locale`), no longer by the goals language. locale ∈ {`zh`, `en`},
  default `en`; goals / article body may be in any language (input only) — the
  locale fixes only the output language. Each stage has `zh` / `en` pure-language
  prompts (`prompts/agents/radar_*.md` = zh base, `radar_*.en.md` = en variant);
  tier-1's drop-category cue vocabulary stays bilingual in both variants
  (idiomatic, not literal) because either locale may analyze an article in the
  other language. The tier-2 two-step scoring rubric now lives in two files — a
  rubric change must update both `radar_tier2_impact.md` and
  `radar_tier2_impact.en.md`.
- `radar_analyses.locale` records each row's generation language; there is no
  post-hoc translation, so a mixed-language corpus is expected. dedup candidate
  retrieval is **not** locale-filtered (cross-language dedup is intentional;
  embeddings are multilingual).

## Specs and status

Specs: [`openspec/specs/info-radar/`](../../openspec/specs/info-radar/),
[`openspec/specs/info-radar-analysis/`](../../openspec/specs/info-radar-analysis/),
[`openspec/specs/info-radar-recap/`](../../openspec/specs/info-radar-recap/),
[`openspec/specs/dashboard-radar-reader/`](../../openspec/specs/dashboard-radar-reader/).

Current status: info-radar pull, analysis, recap, the dashboard reader, the
goals editor, and the Folo subscriptions table are all in place. There is no background
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

The `/radar` **Recap** panel picks a range (last 7 days / last 30 days / custom
from–to, presets resolved in the radar timezone) and inherits the filter bar's
score threshold and novel-only setting as its quality gate, so the recap and the
item list describe the same population — and a different gate is a different
cached recap. Generation spawns `paca info-radar recap` detached and polls
`GET /api/radar/recap` for the row's `status`; on `running` → `done` the client
calls `router.refresh()` so the server-rendered panel picks up the result.
Failures surface the stored error rather than polling forever. The panel is
omitted entirely under `?export=1`.
