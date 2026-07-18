## Why

`info-radar` collects hundreds of items per day into `radar_items`, but right now there is no consumer — the `seen_at` column is never written, nothing is summarized, nothing reaches the user. The user wants signal, not raw feed firehose. We need an analysis layer that filters out noise, deepens analysis on what survives, and pushes a deduplicated stream tied to user-declared goals.

## What Changes

- New `paca/workflows/info_radar_analysis.py` workflow that consumes `radar_items WHERE seen_at IS NULL` and writes results to a new `radar_analyses` table.
- Two-tier sequential pipeline (no agno Team — fixed shape):
  - **Tier 1 filter** (cheap, local model): reads `title + payload.entries.description`, outputs `keep` / `drop` + reason against the user's goal. Dropped items are marked `seen_at` immediately.
  - **Tier 2 impact** (more expensive, configurable model): for kept items, fetches full content via `folocli entry get` (correcting the prior `entry read` mistake), produces an impact-vs-goal write-up + summary.
  - **Dedup gate** (post-tier-2): pgvector ANN search over previously-pushed `radar_pushed_topics`, then an LLM judge reads the top-k candidates and decides whether the new item is genuinely novel or a rehash of something already presented.
- New user-editable `configs/info_radar/goals.yaml` declaring `goal` + `topics` + `keywords`. The analysis agents reference this via prompt injection.
- New business tables: `radar_analyses` (one row per analyzed item: verdict, impact_md, summary, score, dedup status, pushed_at) and `radar_pushed_topics` (topic text + embedding + linked item ids; the dedup memory).
- New CLI: `paca info-radar analyze [--limit N] [--source NAME]` for manual runs; existing `paca info-radar pull|sweep` untouched.
- New scheduler entry: `info_radar_analysis`, thin workflow shell pattern reusing the existing scheduler infra. Cadence is operator-configurable (seeded with a reasonable default); `seen_at` makes the workflow idempotent so frequency can be tuned without code changes.
- YouTube enrichment: best-effort native-subtitle extraction only (use existing `paca/integrations/knowledge/bilibili.py`-style captions-first path; **skip** audio-transcription fallback in this change). If subtitles unavailable, tier 2 falls back to title + description.
- Per-item failure isolation: a tier-1 or tier-2 LLM error on one item never blocks the rest of the batch.

## Capabilities

### New Capabilities
- `info-radar-analysis`: two-tier LLM analysis over `radar_items` with goal-conditioned filtering, full-content impact analysis, and semantic dedup memory before user-facing push.

### Modified Capabilities
- `info-radar`: add a requirement clarifying that `seen_at` is owned by the analysis layer (collector never writes it). The 30-day retention requirement is unchanged but now coexists with `radar_analyses` rows that reference `radar_items.id`.

## Impact

- **Code**: new package `paca/workflows/info_radar_analysis/` (stages: tier1_filter, fetch_full, tier2_impact, dedup, persist); new agents `configs/agents/radar_tier1_filter.yaml`, `radar_tier2_impact.yaml`, `radar_dedup_judge.yaml` (+ prompts); new tools / integration helper for `folocli entry get`; YouTube subtitle helper under `paca/integrations/info_radar/` reusing the bilibili captions pattern.
- **DB**: new tables `radar_analyses` and `radar_pushed_topics` in `scripts/bootstrap_db.py`. `radar_pushed_topics.embedding` is `vector(<dim>)` — uses existing pgvector extension already provisioned for agno.
- **Config**: new `configs/info_radar/goals.yaml`, new `configs/workflows/info_radar_analysis.yaml`, new `configs/agents/radar_*.yaml`, new entry in `configs/schedules.yaml`.
- **CLI**: new `paca info-radar analyze` subcommand; `paca doctor` adds a `goals.yaml` presence check.
- **Docs**: `docs/architecture.md` collector vs analysis distinction; `docs/operations.md` analyze schedule + goals.yaml location; `CLAUDE.md` Financial-News-style summary block for info-radar analysis.
- **Out of scope**: Discord push (downstream consumer reads `radar_analyses` later); dashboard surfacing; audio transcription for video sources; cross-source semantic dedup of `radar_items` themselves (we only dedup at push time).
