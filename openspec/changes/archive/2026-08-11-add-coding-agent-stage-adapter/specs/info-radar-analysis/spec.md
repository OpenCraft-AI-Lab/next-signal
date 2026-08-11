## MODIFIED Requirements

### Requirement: Tier 1 filter uses title and description only

The tier-1 filter stage SHALL invoke the production stage adapter with the registered `radar_tier1_filter` configuration and input limited to `radar_items.title` plus `payload.entries.description` (or `summary` when description is blank). It MUST NOT fetch full article content. The selected engine SHALL return a `Tier1Batch` validated against its Pydantic schema through the adapter's provider-appropriate structured-output path.

#### Scenario: Tier 1 drop short-circuits

- **WHEN** the stage adapter returns `verdict: drop`
- **THEN** the workflow writes a `radar_analyses` row with `verdict='drop'` and `tier1_reason` set, and sets `radar_items.seen_at` to `now()`, and does not invoke tier-2 for that item

### Requirement: Dedup gate via pgvector ANN plus LLM judge

For every tier-2 `keep` result, the workflow SHALL embed the tier-2 `summary` and run an ANN search over `radar_pushed_topics.embedding` using cosine distance, limited to the top 5 candidates within a configurable distance threshold (default 0.40). If at least one candidate is found, the workflow SHALL invoke `radar_dedup_judge` through the production stage adapter with the new summary and candidate summaries. The judge SHALL return a locally validated `{is_duplicate, matched_topic_id, reason}`. `is_duplicate=true` SHALL set the analysis row's `dedup_status='duplicate'` and `dedup_match_id`. `is_duplicate=false` (or no ANN candidates) SHALL set `dedup_status='novel'` and insert a new `radar_pushed_topics` row.

#### Scenario: novel item creates topic

- **WHEN** ANN returns no candidate within threshold, or the selected engine's judge returns `is_duplicate=false`
- **THEN** the workflow writes the analysis row with `dedup_status='novel'` and inserts a new `radar_pushed_topics` row with the summary, embedding, and the radar_item_id in `item_ids`

#### Scenario: duplicate item links existing topic

- **WHEN** the selected engine's judge returns `is_duplicate=true` with a candidate topic id
- **THEN** the workflow writes the analysis row with `dedup_status='duplicate'` and `dedup_match_id` set to the matched topic id, and appends the radar_item_id to that topic's `item_ids`

#### Scenario: embedder failure is conservative

- **WHEN** the embedding call fails
- **THEN** the workflow logs the failure loudly, persists the analysis row with `dedup_status='novel'`, and does NOT insert a `radar_pushed_topics` row

## ADDED Requirements

### Requirement: One selected engine covers the complete radar LLM pipeline

`info_radar_analysis.run` SHALL establish one stage-job context shared with its Tier-1 producer thread. Tier 1, Tier 2, and every invoked dedup judge SHALL therefore use the same pinned engine, while fetch, embedding, ANN, and persistence remain unchanged.

#### Scenario: CLI selection reaches all radar LLM stages

- **WHEN** a batch starts with `claude_cli` selected and at least one item is kept with ANN candidates
- **THEN** Tier 1, Tier 2, and the dedup judge all invoke Claude Code and neither Codex nor an agno text model is invoked
