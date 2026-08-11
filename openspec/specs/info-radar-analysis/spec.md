# info-radar-analysis Specification

## Purpose

Two-tier LLM analysis layer that consumes the `radar_items` table populated by the `info-radar` collector, filters items against user-declared goals, deepens analysis on what survives via full-content fetch, and dedups against a vector-backed long-term memory before any user-facing push. Owns `radar_items.seen_at` (collector never writes it); a tier-2 failure leaves the item unpersisted and unseen so it is retried on the next analysis run.
## Requirements
### Requirement: Goals declared in a single user-editable YAML

`next_signal/workflows/info_radar_analysis/` SHALL load goal descriptors from `configs/info_radar/goals.yaml`. The file MUST contain a top-level `goals:` list. Each entry MUST declare `name` (unique, kebab-case), `description`, `topics` (list of strings), and `keywords` (list of strings). Unknown top-level keys or unknown per-entry keys SHALL raise `RuntimeError` at load time. A missing or empty `goals.yaml` SHALL raise `RuntimeError` — the workflow MUST NOT fall back to an implicit default goal.

#### Scenario: missing goals.yaml aborts the run

- **WHEN** `next-signal info-radar analyze` runs and `configs/info_radar/goals.yaml` does not exist
- **THEN** the workflow raises `RuntimeError` referencing the missing path and exits non-zero before any LLM call

#### Scenario: duplicate goal names fail fast

- **WHEN** `goals.yaml` contains two entries with the same `name`
- **THEN** the loader raises `RuntimeError` mentioning the duplicate `name`

### Requirement: Tier 1 filter uses title and description only

The tier-1 filter stage SHALL invoke the production stage adapter with the registered `radar_tier1_filter` configuration and input limited to `radar_items.title` plus `payload.entries.description` (or `summary` when description is blank). It MUST NOT fetch full article content. The selected engine SHALL return a `Tier1Batch` validated against its Pydantic schema through the adapter's provider-appropriate structured-output path.

#### Scenario: Tier 1 drop short-circuits

- **WHEN** the stage adapter returns `verdict: drop`
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

When a tier-1-kept item's `payload.entries.url` is a YouTube watch URL or `payload.feeds.url` matches `rsshub://youtube/...`, the workflow SHALL attempt native subtitle extraction via `next_signal.integrations.info_radar.youtube_subs.fetch_captions(url)`. If captions are returned, they MUST be concatenated into the tier-2 input as additional context. If the helper raises or returns empty, the workflow MUST proceed without subtitles. Audio-transcription fallback is explicitly out of scope.

#### Scenario: no captions available falls through silently

- **WHEN** subtitle fetch raises or returns empty for a YouTube item
- **THEN** the workflow logs the absence and runs tier-2 on title+description without raising

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

`scripts/bootstrap_db.py` SHALL provision `radar_analyses` and
`radar_pushed_topics` with the existing analysis columns plus
`radar_pushed_topics.embedder TEXT NOT NULL`. The embedding column SHALL remain
`vector(1024)`, whose width is enforced by `core-embedding`.

Bootstrap SHALL remove the former mixed-space IVFFlat index and create a normal
index on `embedder`. Existing rows that predate provenance SHALL be labelled
`legacy:unknown` without deleting or rewriting their vectors. The existing
`ON DELETE CASCADE` from `radar_items` to `radar_analyses` remains unchanged.

#### Scenario: bootstrap is idempotent

- **WHEN** bootstrap runs twice
- **THEN** both runs succeed with one embedder index, no old IVFFlat index, and
  unchanged topic rows

#### Scenario: DDL is stable across provider switches

- **WHEN** the active embedding provider changes
- **THEN** the vector column and indexes are not rebuilt and no row is deleted

### Requirement: CLI surface

`next-signal info-radar analyze` SHALL be a Typer subcommand under the existing `info-radar` group. It SHALL accept `--limit N` (max items processed this run) and `--source NAME` (restrict to a single collector source). It SHALL print a one-line summary including the counters from the workflow return value.

#### Scenario: limit caps the batch

- **WHEN** `next-signal info-radar analyze --limit 5` is invoked and 20 unseen items exist
- **THEN** at most 5 items are processed, and the printed summary reflects counts that sum to ≤ 5

### Requirement: Workflow entry is present and idempotent across runs

`configs/workflows/info_radar_analysis.yaml` SHALL set `expose.agent_os: false` and `extra.run_now: next_signal.workflows.info_radar_analysis:run`. How often it runs is operator-controlled and NOT a stable contract — the workflow's idempotency (`seen_at` gate plus `UNIQUE(radar_item_id)` on `radar_analyses`) SHALL make it safe to run at any frequency.

#### Scenario: manual run invokes the workflow

- **WHEN** `next-signal info-radar analyze` (or `next-signal run-workflow info_radar_analysis`) is invoked
- **THEN** it calls `next_signal.workflows.info_radar_analysis:run()` and processes unseen items

#### Scenario: running back-to-back produces no duplicate analyses

- **WHEN** two runs occur in quick succession with no collector pull between them
- **THEN** the second run processes zero items because all unseen items from the first run were marked `seen_at`

### Requirement: Tier-2 prose fields follow the configured output language

The `title`, `summary`, and `impact` fields returned by `radar_tier2_impact` SHALL be written in the configured output language, independent of the language of `goals`, the article body, and the source's original title. The prompt's own language rule SHALL be phrased unconditionally, so an agent built without rule injection still behaves correctly.

`title` is a new field: previously the dashboard displayed the source's untouched original title (`radar_items.title`) alongside a translated `summary`/`impact`, which produced visibly inconsistent language on the same card. `radar_tier2_impact` now rewrites the title into the same target language as the other two fields, using the source title (already available as prompt input) as its basis.

The previously shipped conditional phrasing ("match the language of `goals`") SHALL remain removed, per the prior measurement (English `summary` in 64/64 replays and 13/13 real production rows against Chinese goals, while `impact` stayed Chinese in the same responses).

`tags` remain lowercase kebab-case English and are unaffected.

#### Scenario: English article under a Chinese target

- **WHEN** the configured output language is `zh`, the goals are Chinese, and the fetched article body is English
- **THEN** `title`, `summary`, and `impact` are all written in Chinese, with proper nouns kept in their original form

#### Scenario: Chinese article under an English target

- **WHEN** the configured output language is `en`, the goals are Chinese, and the fetched article body is Chinese
- **THEN** `title`, `summary`, and `impact` are all written in English

#### Scenario: title is consistent with summary and impact

- **WHEN** any item completes tier-2 analysis
- **THEN** `title`, `summary`, and `impact` are all in the same resolved language — none of the three is left in the source's original language while the others are translated

#### Scenario: tier-1 reason follows the same language

- **WHEN** a tier-1 verdict is produced under a configured output language
- **THEN** the one-sentence `reason` is written in that language, while the English goal identifiers it cites remain unchanged

### Requirement: Downstream radar agents do not re-derive language from their input

`radar_recap` SHALL take its output language from the configured `global` setting rather than from the language of the summaries it is given, which previously made its language a side effect of whatever tier-2 happened to emit.

`radar_dedup_judge` is explicitly exempt from this requirement: its `reason` field is neither stored for display nor rendered anywhere in the dashboard, so it has no language contract to honor. (This corrects a prior version of this requirement, which incorrectly stated that `radar_dedup_judge` follows the configured language — the shipped prompt and config have always exempted it; only the spec text was out of date.)

#### Scenario: recap over mixed-language summaries

- **WHEN** a recap covers a period whose stored summaries are a mix of languages
- **THEN** the headline, theme titles, and narratives are all written in the configured output language

#### Scenario: dedup judge is unconstrained

- **WHEN** `radar_dedup_judge` evaluates a candidate pair whose stored summaries are in different languages
- **THEN** its `reason` field's language is not required to match the configured output language, the source summaries, or anything else

### Requirement: next-signal doctor checks goals.yaml

`next-signal doctor` SHALL include a `goals.yaml` check that reports OK with the goal count when the file exists and parses, and reports FAIL with the loader's error message otherwise. The check SHALL NOT invoke any LLM.

#### Scenario: missing goals.yaml fails the doctor check

- **WHEN** `next-signal doctor` runs and `configs/info_radar/goals.yaml` does not exist
- **THEN** the doctor output includes a FAIL line for the goals.yaml check

### Requirement: One selected engine covers the complete radar LLM pipeline

`info_radar_analysis.run` SHALL establish one stage-job context shared with its Tier-1 producer thread. Tier 1, Tier 2, and every invoked dedup judge SHALL therefore use the same pinned engine, while fetch, embedding, ANN, and persistence remain unchanged.

#### Scenario: CLI selection reaches all radar LLM stages

- **WHEN** a batch starts with `claude_cli` selected and at least one item is kept with ANN candidates
- **THEN** Tier 1, Tier 2, and the dedup judge all invoke Claude Code and neither Codex nor an agno text model is invoked

### Requirement: Dedup gate via provider-scoped pgvector search plus LLM judge

For every tier-2 `keep` result, the workflow SHALL resolve one
`core-embedding` snapshot, embed the tier-2 summary with it, and carry the
snapshot's identity beside that vector through search and persistence. A live
settings re-read after embedding SHALL NOT determine the stored identity.

The workflow SHALL run an exact cosine search over
`radar_pushed_topics.embedding`, restricted first to rows whose `embedder`
equals the query vector's captured identity, limited to the top 5 candidates
within a configurable distance threshold (default 0.40). Rows from another
identity, including `legacy:unknown`, SHALL NOT participate in candidate
generation or be shown to the judge.

If candidates exist, the workflow SHALL invoke `radar_dedup_judge` with the new
summary and candidate summaries. A valid duplicate verdict SHALL set
`dedup_status='duplicate'` and `dedup_match_id`; a non-duplicate verdict or no
candidates SHALL set `dedup_status='novel'` and insert a new topic row containing
the exact vector and identity from the same resolved snapshot.

Changing selection parks post-migration rows under the previous identity and
switching back restores them. Pre-change `legacy:unknown` rows remain retained
but inactive unless an operator explicitly relabels them after independently
verifying their provenance.

#### Scenario: novel item stores its resolved identity

- **WHEN** provider-scoped search finds no candidate
- **THEN** the workflow stores a novel analysis and a topic row containing the
  summary, vector, captured identity, and item id

#### Scenario: duplicate item links to same-space topic

- **WHEN** same-identity candidates exist and the judge returns duplicate
- **THEN** the analysis links to the matched topic and appends the item id

#### Scenario: embedding failure remains conservative

- **WHEN** snapshot resolution or embedding raises
- **THEN** the workflow logs loudly, stores the analysis as novel, and inserts no
  topic row

#### Scenario: settings change cannot mislabel an in-flight vector

- **WHEN** provider A is resolved and state changes to B before topic insertion
- **THEN** the current item's search and insert still use identity A, while the
  next item resolves B

#### Scenario: another vector space does not affect candidate generation

- **WHEN** the table contains rows under identities A, B, and `legacy:unknown`
  and the query identity is B
- **THEN** exact distance ordering examines only B rows

#### Scenario: switching back restores post-migration memory

- **WHEN** the operator switches from A to B and later back to A
- **THEN** previously stored A rows become candidates again without re-embedding

