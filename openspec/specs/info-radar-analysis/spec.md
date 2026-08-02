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

The tier-2 impact stage SHALL fetch full article content using `folocli entry get <source_id>` for each tier-1-kept item before invoking the tier-2 agent. The fetched content MUST be read from the JSON envelope at `data.entries.content`.

The fetched body MUST be flattened to plain text before any length test or truncation: `<script>` and `<style>` blocks are dropped whole, block-level closing tags and `<br>` become newlines, all remaining tags are removed, and HTML entities are unescaped. Feed bodies are raw publisher markup and have measured as high as 91% tags, which both wastes the content budget and pushes real prose past the truncation point.

If the fetch raises, times out, returns `ok: false`, yields empty content, **or yields fewer than 200 characters of flattened text**, the workflow SHALL fall back to title+description and tag the resulting analysis row with `content_status='fallback'`. `content_status='full'` SHALL be set only when the flattened text reaches 200 characters. A paywalled publisher's lede is not a full article, and reporting it as one makes the tier-2 agent read an absence of detail as an absence of evidence.

Before being sent to the tier-2 agent, content (fetched or fallback) MUST be truncated to the first 16000 characters.

#### Scenario: full content available

- **WHEN** `folocli entry get` returns `ok: true` with a body whose flattened text is at least 200 characters
- **THEN** the tier-2 agent receives the flattened text and the resulting `radar_analyses` row sets `content_status='full'`

#### Scenario: markup is stripped before the tier-2 agent call

- **WHEN** the fetched body contains image tags, entities, and `<script>` blocks around its prose
- **THEN** the tier-2 agent receives only the prose with paragraph boundaries preserved as newlines, and no tag, tracking URL, or script text remains

#### Scenario: lede-only body reports fallback

- **WHEN** `folocli entry get` returns `ok: true` but the body flattens to fewer than 200 characters of text
- **THEN** the workflow uses title+description and writes the analysis row with `content_status='fallback'`

#### Scenario: fetch failure falls back to description

- **WHEN** `folocli entry get` raises a timeout or returns `ok: false`
- **THEN** the workflow logs the failure, calls the tier-2 agent with title+description only, and writes the analysis row with `content_status='fallback'`

#### Scenario: oversized content is truncated before the tier-2 agent call

- **WHEN** flattened content exceeds 16000 characters
- **THEN** only the first 16000 characters are included in the tier-2 agent's input

### Requirement: Tier 2 `score` measures consequence, not methodological rigor

The `radar_tier2_impact` prompt SHALL define `score` as how much the item should change the user's judgment or actions, and SHALL NOT define it as a measure of evidence quality. Methodological strength — controlled ablations, adversarial tests, conference acceptance, multi-institution authorship — SHALL be reported in `impact` as a reason to trust the item's numbers and MUST NOT raise `score` on its own.

The prompt SHALL state an ordering constraint that a flagship model, chip, or agent release from a frontier lab or major vendor outranks a single-lab narrow-task paper, regardless of which is more rigorous.

The prompt SHALL NOT contain a within-band numeric adjustment finer than the model's run-to-run sampling spread, which measured ±9 points at the `local_structured` temperature. A previous three-axis ±3 adjustment was removed for this reason: 36% of observed scores fell on values its arithmetic cannot produce.

#### Scenario: rigor is reported without inflating the score

- **WHEN** the tier-2 agent analyses a single-lab paper with a clean controlled ablation that no third party has reproduced or adopted
- **THEN** the ablation quality is described in `impact` and does not by itself place the item above a flagship release in `score`

#### Scenario: an unverifiable first-party number still scores on consequence

- **WHEN** a frontier lab publishes open weights with self-reported benchmark numbers that nobody has yet reproduced
- **THEN** `score` reflects the consequence of the weights being available and `impact` states who reported the numbers and how an outsider could check them

### Requirement: Tier 2 treats feed contents as real despite the model's training cutoff

The `radar_tier2_impact` prompt SHALL instruct the agent that feed items postdate its training data and that product names, version numbers, companies, dates, and benchmark names appearing in a feed item are real and already happened. The agent MUST NOT tag an item `fiction`, `rumor`, or `misinformation`, argue in `impact` that it contradicts known reality, or reduce `score`, on the basis that a name or date is unfamiliar. Factual scepticism SHALL be reserved for publisher-self-reported figures that no outside party can check.

#### Scenario: an unrecognised model name is not treated as fabrication

- **WHEN** an item announces a model release whose name and date fall after the agent's training cutoff
- **THEN** the agent scores it on consequence, and neither tags it as fabricated nor cites unfamiliarity as a reason to score it down

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

### Requirement: Tier-2 prose fields follow the configured output language

The `summary` and `impact` fields returned by `radar_tier2_impact` SHALL be
written in the configured output language, independent of the language of
`goals` and independent of the language of the article body. The prompt's own
language rule SHALL be phrased unconditionally, so an agent built without rule
injection still behaves correctly.

The previously shipped conditional phrasing ("match the language of `goals`")
SHALL be removed. It was measured to produce an English `summary` in 64/64
replays and 13/13 real production rows against Chinese goals, while `impact`
stayed Chinese in the very same responses.

`tags` remain lowercase kebab-case English and are unaffected.

#### Scenario: English article under a Chinese target

- **WHEN** `SIGNAL_OUTPUT_LANG=zh`, the goals are Chinese, and the fetched article body is English
- **THEN** both `summary` and `impact` are written in Chinese, with proper nouns kept in their original form

#### Scenario: Chinese article under an English target

- **WHEN** `SIGNAL_OUTPUT_LANG=en`, the goals are Chinese, and the fetched article body is Chinese
- **THEN** both `summary` and `impact` are written in English

#### Scenario: tier-1 reason follows the same language

- **WHEN** a tier-1 verdict is produced under a configured output language
- **THEN** the one-sentence `reason` is written in that language, while the English goal identifiers it cites remain unchanged

### Requirement: Downstream radar agents do not re-derive language from their input

`radar_recap` and `radar_dedup_judge` SHALL take their output language from the
configured setting rather than from the language of the summaries they are given.
Both previously inherited it from their input, which made their language a
side effect of whatever tier-2 happened to emit.

#### Scenario: recap over mixed-language summaries

- **WHEN** a recap covers a period whose stored summaries are a mix of languages
- **THEN** the headline, theme titles, and narratives are all written in the configured output language
