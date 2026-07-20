# info-radar-analysis Specification

## Purpose

Two-tier LLM analysis layer that consumes the `radar_items` table populated by the `info-radar` collector, filters items against user-declared goals, deepens analysis on what survives via full-content fetch, and dedups against a vector-backed long-term memory before any user-facing push. Owns `radar_items.seen_at` (collector never writes it); a tier-2 failure leaves the item unpersisted and unseen so it is retried on the next analysis run.

## Requirements

### Requirement: Goals declared in a single user-editable YAML

`paca/workflows/info_radar_analysis/` SHALL load goal descriptors from `configs/info_radar/goals.yaml`. The file MUST contain a top-level `goals:` list. Each entry MUST declare `name` (unique, kebab-case), `description`, `topics` (list of strings), and `keywords` (list of strings). Unknown top-level keys or unknown per-entry keys SHALL raise `RuntimeError` at load time. A missing or empty `goals.yaml` SHALL raise `RuntimeError` — the workflow MUST NOT fall back to an implicit default goal.

#### Scenario: missing goals.yaml aborts the run

- **WHEN** `paca info-radar analyze` runs and `configs/info_radar/goals.yaml` does not exist
- **THEN** the workflow raises `RuntimeError` referencing the missing path and exits non-zero before any LLM call

#### Scenario: duplicate goal names fail fast

- **WHEN** `goals.yaml` contains two entries with the same `name`
- **THEN** the loader raises `RuntimeError` mentioning the duplicate `name`

### Requirement: Tier 1 filter uses title and description only

The tier-1 filter stage SHALL invoke a registered agent (`radar_tier1_filter`) with input limited to `radar_items.title` plus `payload.entries.description` (or `summary` when description is blank). It MUST NOT fetch full article content. The agent SHALL return a structured output enforced by an OMLX json_schema constrained-decoding `output_schema`.

#### Scenario: dropped item is marked seen and persisted as drop verdict

- **WHEN** the tier-1 agent returns `verdict: "drop"` for a `radar_item`
- **THEN** the workflow writes a `radar_analyses` row with `verdict='drop'` and `tier1_reason` set, and sets `radar_items.seen_at` to `now()`, and does not invoke tier-2 for that item

### Requirement: Tier 1 is batched with per-chunk fallback

The tier-1 stage SHALL group unseen items into chunks (default size 10) and send each chunk to `radar_tier1_filter` in a single prompt. The agent SHALL return a `Tier1Batch{decisions: list[Tier1Decision]}` containing exactly one decision per input item, each tagged with the input `index`. The runner SHALL validate (1) the decision count equals the input count and (2) the set of returned indices equals `{0..N-1}`. On either validation failure, OR on a structured-output parse failure even after the in-agent repair pass, the runner SHALL fall back to per-item calls (a batch of size 1) for that chunk so a single bad item cannot poison its neighbors. An item whose per-item fallback also fails SHALL be counted as `tier1_error` and SHALL NOT be marked seen.

#### Scenario: agent returns decisions in reordered position

- **WHEN** the tier-1 agent returns three decisions with `index` 2, 0, 1
- **THEN** the runner re-orders them by `index` and pairs each verdict with the matching input item

#### Scenario: batch returns wrong decision count

- **WHEN** the agent returns 1 decision for a chunk of 2 items
- **THEN** the runner raises, falls back to two single-item calls, and persists results from those individually

#### Scenario: both batch and per-item fallback fail for one item

- **WHEN** the chunk-level batch call fails AND the per-item retry for one specific item also raises
- **THEN** that item is counted in `tier1_error`, no `radar_analyses` row is written for it, and its `seen_at` remains NULL so a future run can retry

### Requirement: Tier 2 fetches full content via folocli entry get

The tier-2 impact stage SHALL fetch full article content using `folocli entry get <source_id>` for each tier-1-kept item before invoking the tier-2 agent. The fetched content MUST be read from the JSON envelope at `data.entries.content`. If the fetch raises, times out, returns `ok: false`, or yields empty content, the workflow SHALL fall back to title+description and tag the resulting analysis row with `content_status='fallback'`. Successful fetches set `content_status='full'`. Before being sent to the tier-2 agent, content (fetched or fallback) MUST be truncated to the first 16000 characters.

#### Scenario: full content available

- **WHEN** `folocli entry get` returns `ok: true` with non-empty `data.entries.content`
- **THEN** the tier-2 agent receives that content and the resulting `radar_analyses` row sets `content_status='full'`

#### Scenario: fetch failure falls back to description

- **WHEN** `folocli entry get` raises a timeout or returns `ok: false`
- **THEN** the workflow logs the failure, calls the tier-2 agent with title+description only, and writes the analysis row with `content_status='fallback'`

#### Scenario: oversized content is truncated before the tier-2 agent call

- **WHEN** fetched content exceeds 16000 characters
- **THEN** only the first 16000 characters are included in the tier-2 agent's input

### Requirement: Tier 2 emits structured impact analysis grounded in goals

The tier-2 agent (`radar_tier2_impact`) SHALL be invoked with the loaded goals concatenated into its prompt context and SHALL return a structured `{summary, impact, score, tags}` enforced via OMLX json_schema constrained decoding. `score` MUST be an integer in `[0, 100]`. `tags` MUST be a list of strings. `impact` SHALL be markdown describing impact on the user's declared goals specifically.

#### Scenario: tier 2 output is persisted with score and tags

- **WHEN** the tier-2 agent returns a valid structured output
- **THEN** the workflow writes `radar_analyses` with `verdict='keep'`, `summary`, `impact_md`, `score`, and `tags` populated from the agent output

#### Scenario: opinion-tagged items are score-capped

- **WHEN** the tier-2 agent tags an item `"opinion"` and returns a `score` above 65
- **THEN** the workflow caps the persisted `score` at 65

#### Scenario: frontier-voice exemption bypasses the opinion ceiling

- **WHEN** the item is by a high-signal individual carved out in `goals.yaml` (e.g. a frontier-lab founding researcher) and the tier-2 agent tags it `"frontier-voice"` instead of `"opinion"`
- **THEN** the opinion score ceiling does NOT apply and the agent's original score is persisted as-is

### Requirement: YouTube subtitle enrichment is opportunistic

When a tier-1-kept item's `payload.entries.url` is a YouTube watch URL or `payload.feeds.url` matches `rsshub://youtube/...`, the workflow SHALL attempt native subtitle extraction via `paca.integrations.info_radar.youtube_subs.fetch_captions(url)`. If captions are returned, they MUST be concatenated into the tier-2 input as additional context. If the helper raises or returns empty, the workflow MUST proceed without subtitles. Audio-transcription fallback is explicitly out of scope.

#### Scenario: no captions available falls through silently

- **WHEN** subtitle fetch raises or returns empty for a YouTube item
- **THEN** the workflow logs the absence and runs tier-2 on title+description without raising

### Requirement: Dedup gate via pgvector ANN plus LLM judge

For every tier-2 `keep` result, the workflow SHALL embed the tier-2 `summary` and run an ANN search over `radar_pushed_topics.embedding` using cosine distance, limited to the top 5 candidates within a configurable distance threshold (default 0.40). If at least one candidate is found, the workflow SHALL invoke the `radar_dedup_judge` agent with the new summary and the candidate summaries. The judge SHALL return `{is_duplicate, matched_topic_id, reason}` via constrained decoding. `is_duplicate=true` SHALL set the analysis row's `dedup_status='duplicate'` and `dedup_match_id`. `is_duplicate=false` (or no ANN candidates) SHALL set `dedup_status='novel'` and insert a new `radar_pushed_topics` row.

#### Scenario: novel item creates a new topic

- **WHEN** ANN returns no candidates within the threshold for a tier-2 summary
- **THEN** the workflow writes the analysis row with `dedup_status='novel'` and inserts a new `radar_pushed_topics` row with the summary, embedding, and the radar_item_id in `item_ids`

#### Scenario: duplicate item links to existing topic

- **WHEN** ANN returns candidates and the judge agent returns `is_duplicate=true`
- **THEN** the workflow writes the analysis row with `dedup_status='duplicate'` and `dedup_match_id` set to the matched topic id, and appends the radar_item_id to that topic's `item_ids`

#### Scenario: embedder failure conservatively treats as novel

- **WHEN** the embedder call raises
- **THEN** the workflow logs the failure loudly, persists the analysis row with `dedup_status='novel'`, and does NOT insert a `radar_pushed_topics` row

### Requirement: Per-item failure isolation

A failure (raised exception, timeout, schema-violation) in tier-1, the tier-2 fetch, the tier-2 agent, or the dedup gate for one `radar_item` SHALL NOT abort the batch. The workflow SHALL continue with the next item, log the failure with the item id, and return a counters dict including `tier1_kept`, `tier1_dropped`, `tier2_ok`, `tier2_fallback`, `tier2_error`, `dedup_novel`, `dedup_duplicate`.

#### Scenario: one tier 2 agent raises, others continue

- **WHEN** the tier-2 agent raises for one of three kept items
- **THEN** the other two items are analyzed and persisted, and the failing item is left unpersisted (no `radar_analyses` row is written) with `seen_at` remaining NULL so it is retried on the next analysis run, and the run summary reports `tier2_error=1`

### Requirement: Re-running the analysis is idempotent

The workflow SHALL select only `radar_items` with `seen_at IS NULL`. The `radar_analyses.radar_item_id` column SHALL have a `UNIQUE` constraint, and inserts SHALL use `ON CONFLICT (radar_item_id) DO NOTHING`. Setting `seen_at` SHALL happen only after the per-item analysis row is committed.

#### Scenario: a manual replay finds nothing new

- **WHEN** the analysis workflow has just completed and is invoked again with no new collector pulls
- **THEN** the second run processes zero items and returns counters all equal to zero

### Requirement: Business tables and DDL

`scripts/bootstrap_db.py` SHALL provision `radar_analyses` and `radar_pushed_topics` tables with the columns described in design.md §D7 and §D8. The `embedding` column on `radar_pushed_topics` SHALL be `vector(1024)` and an `ivfflat` cosine index SHALL be created. ON DELETE CASCADE from `radar_items` to `radar_analyses` SHALL be configured.

#### Scenario: bootstrap is idempotent

- **WHEN** `scripts/bootstrap_db.py` is run twice
- **THEN** both runs succeed and the tables / indexes exist exactly once

### Requirement: CLI surface

`paca info-radar analyze` SHALL be a Typer subcommand under the existing `info-radar` group. It SHALL accept `--limit N` (max items processed this run) and `--source NAME` (restrict to a single collector source). It SHALL print a one-line summary including the counters from the workflow return value.

#### Scenario: limit caps the batch

- **WHEN** `paca info-radar analyze --limit 5` is invoked and 20 unseen items exist
- **THEN** at most 5 items are processed, and the printed summary reflects counts that sum to ≤ 5

### Requirement: Workflow entry is present and idempotent across runs

`configs/workflows/info_radar_analysis.yaml` SHALL set `expose.agent_os: false` and `extra.run_now: paca.workflows.info_radar_analysis:run`. How often it runs is operator-controlled and NOT a stable contract — the workflow's idempotency (`seen_at` gate plus `UNIQUE(radar_item_id)` on `radar_analyses`) SHALL make it safe to run at any frequency.

#### Scenario: manual run invokes the workflow

- **WHEN** `paca info-radar analyze` (or `paca run-workflow info_radar_analysis`) is invoked
- **THEN** it calls `paca.workflows.info_radar_analysis:run()` and processes unseen items

#### Scenario: running back-to-back produces no duplicate analyses

- **WHEN** two runs occur in quick succession with no collector pull between them
- **THEN** the second run processes zero items because all unseen items from the first run were marked `seen_at`

### Requirement: paca doctor checks goals.yaml

`paca doctor` SHALL include a `goals.yaml` check that reports OK with the goal count when the file exists and parses, and reports FAIL with the loader's error message otherwise. The check SHALL NOT invoke any LLM.

#### Scenario: missing goals.yaml fails the doctor check

- **WHEN** `paca doctor` runs and `configs/info_radar/goals.yaml` does not exist
- **THEN** the doctor output includes a FAIL line for the goals.yaml check
