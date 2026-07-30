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
- Tier-2 `score` measures **consequence** — how much an item should change the
  reader's judgment or actions — explicitly not evidence quality. Methodological
  rigor (ablations, adversarial tests, conference acceptance) is reported in
  `impact` as a reason to trust the numbers and never raises the score on its own.
  The rubric is: a mechanical "what can an outsider obtain right now?" step that
  sets a floor for non-paper items, then an anchor table of named score points
  with an explicit ordering constraint (a flagship release outranks a single-lab
  narrow-task paper regardless of rigor). The ≤65 ceiling for the `opinion` tag is
  backstopped in code (`stages/tier2.py::_apply_ceilings`), and high-signal
  individuals named in the goals are exempted via a prompt-driven `frontier-voice`
  tag.
- No within-band numeric adjustment finer than the sampling spread. A previous
  three-axis ±3 mechanism was removed: it could move a score by at most ±9, which
  is the run-to-run spread at the `local_structured` temperature, and 36% of
  observed scores landed on values its arithmetic cannot produce — the model was
  never executing it.
- The tier-2 prompt tells the agent that feed items postdate its training data and
  are real. Without this, unfamiliar model names and future-looking dates get
  scored as fabrication — one frontier launch was tagged `misinformation` and
  scored 0 / 15 / 15 across three repeats.
- `content_status` reflects whether a real article body was obtained, not merely a
  non-empty response. Feed bodies are flattened to plain text before any length
  test or truncation (one feed measured 91% markup, so the 16k cap was delivering
  ~1,400 characters of prose), and a body under 200 characters of flattened text
  reports `fallback` — a paywalled publisher's lede is not an article. The tier-2
  prompt has a companion clause telling the agent that thin content is missing
  length, not evidence; without it, honest labelling measured −5.3 points because
  an evidence-graded rubric reads absent detail as absent evidence. **The two must
  ship together.**
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

## Tuning and evaluation

Scoring behaviour is measured, not adjusted by feel. `scripts/radar_eval.py`
replays the real tier-1 and tier-2 stages over hand-labelled subsets of
`radar_items` and writes to `radar_eval_cases` / `radar_eval_runs` /
`radar_eval_results`. Those tables are created by the script's own `init`
subcommand and deliberately **not** by `scripts/bootstrap_db.py` — they carry no
runtime behaviour. The dedup gate is skipped, because it writes shared production
state and does not affect verdict or score.

Article content is snapshotted at `load` time and replayed, so a variant
comparison is attributable to the prompt rather than to whether folocli answered
that day. Each run records a `prompt_digest` — a hash of both prompts plus
`goals.yaml` — so a set of numbers always traces to the text that produced it.

Three label sets live in `configs/info_radar/`:

| set | items | purpose |
| --- | --- | --- |
| `eval_cases.yaml` | 60 | adversarial; stacked with known failures |
| `eval_cases_focus.yaml` | 36 | decision boundary only |
| `eval_cases_holdout.yaml` | 55 | independently labelled — **never tune against this** |

The holdout set was labelled by three agents that read only `goals.yaml`, were
forbidden from reading `prompts/` or any existing label set, and only unanimous
items were kept. It is the only set with a claim to being unbiased. The one time
tuning was validated solely on the sets it was tuned against, four rounds climbed
from 26/54 to 38/60 while measuring 40% on holdout against production's 75%.

Process rules, with the measurement that justifies each, are in
`.claude/skills/radar-prompt-tuning/SKILL.md`. Read it before editing any radar
prompt.

**Measured and rejected — do not retry without reading the record:** rewriting
the tier-1 drop categories around event type rather than headline diction. It
looked like a clear win on the adversarial set and its guardrail bucket never
regressed, but on holdout it raised false keeps from 4 to 16 and cut the pass rate
from 75% to 40%. The guardrail was the failure: 17 items of gold prices, Fed
commentary, celebrity divorce and Java release notes, which never failed and so
measured nothing. The real drop distribution is vendor PR that looks like a launch
and mechanism papers that look like breakthroughs.

Also note that the primary metric matters more than it looks: bucket pass rates
were used for seven rounds and did not align with the reader's experience. What
did align was sweeping the dashboard threshold and counting visible signal versus
leaked noise at each cut point — a false keep scoring 35 never reaches the reader.

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
