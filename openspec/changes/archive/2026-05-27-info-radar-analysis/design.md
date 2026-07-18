## Context

The `info-radar` change shipped a collector that fills `radar_items` with raw entries from folo CLI feeds. Today nothing reads that table — `seen_at` is never written, no summary reaches the user. This change adds the consumer.

Constraints inherited from the project:
- **Local-first**: tier-1 filter should run on a local OMLX profile; tier-2 may use a smarter (still local-preferred) model. No mandatory cloud call.
- **Failure isolation**: a single LLM blow-up on one item must not stall a batch (D9 pattern from info-radar collector).
- **Postgres business tables**: we own DDL, use short-lived `psycopg.connect()` for our own rows; agno's tables stay separate.
- **No defensive coding**: missing config → loud `RuntimeError`; we do not silently default a goal.
- **Source of truth**: user-facing goal/topics/keywords live in YAML the user can hand-edit, like the finance `portfolio.yaml`.

Closest cousin in the codebase: `financial_news_analyst` (config-driven agent reading a YAML watchlist, writing markdown signals). We adopt its shape where it fits, but the output sink is a DB table (per user decision), not a markdown file.

## Goals / Non-Goals

**Goals:**
- Filter cheaply via tier-1 before paying tier-2 cost. We do NOT target a specific drop rate — these feeds are already user-curated, so the keep ratio is unknown and will fluctuate; tier-1's job is to enforce goal-relevance, not hit a noise quota.
- Produce per-item impact analysis explicitly grounded in user's declared goal.
- Avoid presenting the same news twice — even when phrased differently — via LLM-judged semantic dedup over a pgvector-backed memory.
- Idempotent re-runs: scheduled cadence is operator-configurable and not a contract; `seen_at` is the gate that makes each run pick up exactly the new items since last successful analysis, regardless of how often the schedule fires.
- Survive partial outages: one bad item, one bad source, one missing subtitle → others still flow.

**Non-Goals:**
- Discord/dashboard push UX. We persist; a downstream change wires push.
- Audio transcription for video sources. Captions or nothing.
- Cross-source semantic dedup at collector level (kept simple per `(source, source_id)`).
- LLM-driven team coordination (Sequential pipeline only — no agno Team).
- Multi-user goals. Single user, one `goals.yaml`.

## Decisions

### D1: Sequential pipeline, not agno Team

The flow is fixed: tier1 → fetch_full → tier2 → dedup_check → persist. No dynamic routing. An agno Team adds a leader-LLM hop with zero value and reintroduces nondeterminism we'd then need to test around. We implement it as a workflow with explicit stage functions in `paca/workflows/stages/info_radar_analysis/`, each calling `build_from_name(...)` for its agent. Mirrors the `knowledge_ingest` workflow shape we already trust.

Alternative considered: agno Team in `route` mode with a router agent picking tier1 vs tier2. Rejected — flow is statically known.

### D2: Two-tier with full content fetched only after tier1 keep

Tier1 input is `title + payload.entries.description` (already in the row, no extra CLI call). Tier1 emits `{verdict: keep|drop, reason}` via a pydantic-constrained schema. Drop → mark `seen_at`, write a `radar_analyses` row with `verdict='drop'` and stop.

Tier2 fetches full content with `folocli entry get <id>` (correcting prior `entry read` mistake — `entry get` returns full body in `data.entries.content` for all sampled feeds including wechat2rss). On fetch failure (timeout, ok=false envelope, empty content), tier2 degrades to title+description and tags the analysis with `content_status: 'fallback'`.

Tier2 emits `{summary, impact, score (0-100), tags[]}` against the goal. Schema enforced via OMLX json_schema constrained decoding (same path knowledge_frontmatter uses).

### D3: YouTube subtitle enrichment is opportunistic only

We add a thin `paca/integrations/info_radar/youtube_subs.py` helper that tries to fetch native captions for items whose `payload.feeds.url` matches `rsshub://youtube/...` or whose `payload.entries.url` is a youtube watch URL. Implementation reuses the captions-first half of `paca/integrations/knowledge/bilibili.py` (youtube-transcript-api preferred; otherwise yt-dlp `--write-auto-sub --skip-download`). **Audio transcription fallback explicitly out of scope** per user direction — if no native subs, tier2 sees only title + description.

YouTube enrichment is a tier-2 input augmentation, not a separate stage. If the captions call raises or returns empty, we log and proceed without subs.

### D4: Dedup memory = pgvector ANN + LLM judge

When tier2 produces a summary, we:
1. Embed the summary (see D5) and run ANN search over `radar_pushed_topics.embedding` with cosine distance, limit 5, distance threshold `0.40` (configurable).
2. If candidates exist, send `(new_summary, [candidate_summaries...])` to `radar_dedup_judge` agent. Output schema `{is_duplicate: bool, matched_topic_id: int|null, reason: str}`.
3. If `is_duplicate=true`, persist `radar_analyses` with `dedup_status='duplicate'` and the matched topic id; do not push.
4. If `is_duplicate=false`, persist `radar_analyses` with `dedup_status='novel'` and insert a new `radar_pushed_topics` row (topic text = tier2 summary; linked item id added to `item_ids` jsonb array).

Why LLM judge on top of ANN: pure cosine threshold leaks false-dups (two different OpenAI announcements both score 0.85 vs a generic "OpenAI launches X" topic) and false-novels (paraphrases under threshold). LLM sees actual semantics; ANN keeps the input set bounded so the LLM call stays cheap.

Alternative considered: pure cosine threshold. Rejected — too brittle for "different incidents in the same general area" distinction.

Alternative considered: agno's `UserMemory` long-term memory. Rejected — its surface is conversational facts, not push history; we'd be fighting the model.

### D5: Embedder choice — OMLX OpenAI-compatible `/v1/embeddings`

We add `paca.core.models.get_embedder()` that returns a small adapter calling `OMLX_BASE_URL + /v1/embeddings` with a model name from a new `embedder` profile in `configs/models.yaml` (default `Qwen3-Embedding-0.6B-8bit`, 1024-dim — chosen for Qwen3 stack cohesion, MIT license, and well-aligned CN/EN/cross-lingual embeddings; verified post-merge that cross-language paraphrases land at cosine distance ~0.05 and unrelated content at ~0.73, so the default ANN threshold of 0.40 cleanly separates them). If OMLX is down or the embedder profile is misconfigured, dedup gate **conservatively returns `novel`** (we'd rather show a likely-dup than swallow a novel item — push pipeline can show first-time-shown badge). This single failure mode is loud-logged.

DDL: `radar_pushed_topics.embedding vector(1024)`. If a future embedder changes dim, we add a new column and migrate offline — out of scope here.

Alternative considered: GBrain bridge. Rejected — GBrain is the knowledge-wiki embedder and its slug/page model is inappropriate for ephemeral push-history rows.

### D6: Goals.yaml schema (minimal v1)

```yaml
goals:
  - name: ai_research_tracking
    description: "Stay current on AI research with practical engineering impact."
    topics:
      - "LLM inference optimization"
      - "agentic systems / tool use"
    keywords: ["mlx", "vllm", "agno", "claude code", "open source agent"]
    weight: 1.0
```

Multiple goals supported; tier1/tier2 receive all goals concatenated. `weight` reserved for future ranking, unused in v1. `name` unique; loader fails fast on duplicates and unknown top-level keys (same pattern as `info_radar/sources.yaml`). If `goals.yaml` is missing or empty, the analysis run aborts with `RuntimeError` — no implicit default goal.

### D7: radar_analyses schema

```sql
CREATE TABLE radar_analyses (
    id              BIGSERIAL PRIMARY KEY,
    radar_item_id   BIGINT NOT NULL REFERENCES radar_items(id) ON DELETE CASCADE,
    verdict         TEXT NOT NULL,            -- 'drop' | 'keep'
    tier1_reason    TEXT,
    summary         TEXT,                     -- tier2 output, null when verdict='drop'
    impact_md       TEXT,                     -- tier2 markdown, null when verdict='drop'
    score           INTEGER,                  -- tier2 0-100, null when 'drop'
    tags            JSONB NOT NULL DEFAULT '[]'::jsonb,
    content_status  TEXT,                     -- 'full' | 'fallback' (description-only) | null
    dedup_status    TEXT,                     -- 'novel' | 'duplicate' | null (drop)
    dedup_match_id  BIGINT REFERENCES radar_pushed_topics(id) ON DELETE SET NULL,
    pushed_at       TIMESTAMPTZ,              -- set by downstream push consumer
    analyzed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (radar_item_id)
);
CREATE INDEX radar_analyses_unpushed_idx
  ON radar_analyses (analyzed_at)
  WHERE verdict='keep' AND dedup_status='novel' AND pushed_at IS NULL;
```

`UNIQUE(radar_item_id)` makes re-runs idempotent via `ON CONFLICT DO NOTHING`. ON DELETE CASCADE: when collector's 30-day sweep removes a `radar_items` row, the analysis goes with it — fine, analysis is downstream-bounded.

### D8: radar_pushed_topics schema

```sql
CREATE TABLE radar_pushed_topics (
    id              BIGSERIAL PRIMARY KEY,
    topic_summary   TEXT NOT NULL,            -- tier2 summary that seeded this topic
    embedding       vector(1024) NOT NULL,
    item_ids        JSONB NOT NULL,           -- [radar_item_id, ...] grouped under this topic
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX radar_pushed_topics_embedding_idx
  ON radar_pushed_topics
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
```

Topics are *never* deleted automatically — the user's memory of "I saw this" doesn't reset because a radar_item rolled out. If the table grows unbounded, that's a future maintenance concern; v1 retention = forever. (Realistic ceiling: ~5 novel items/day × 365 = 1825 rows/year — trivial.)

### D9: Per-item failure isolation

Each item runs in its own try/except inside the batch loop. Tier-1 raise → log + skip item (no `seen_at` write so it retries next batch). Tier-2 raise on a kept item → write `radar_analyses` with `verdict='keep'`, `content_status='error'`, no summary/impact; mark `seen_at` so we don't keep failing on it. Dedup raise on a kept item → conservatively treat as `novel` and persist. Counters: `tier1_kept`, `tier1_dropped`, `tier2_ok`, `tier2_fallback`, `tier2_error`, `dedup_novel`, `dedup_duplicate` — returned by the workflow `run()`.

### D10: Scheduler integration

`info_radar_analysis` workflow shell follows the same pattern as `info_radar_pull`:
- `configs/workflows/info_radar_analysis.yaml` with `expose.agent_os: false`, `extra.run_now: paca.workflows.info_radar_analysis:run`.
- `configs/schedules.yaml` adds an enabled entry. Cadence is **operator-configurable, not a contract** — `seen_at` makes the workflow idempotent against any schedule. We seed it with a reasonable starting default (e.g. `0 10,18 * * *`) but the user may tune frequency up or down without code changes; running more often just means smaller batches.
- Workflow function signature `run(*, limit: int | None = None, source: str | None = None) -> dict` so `paca info-radar analyze` can forward CLI args.

### D11: Doctor check

`paca doctor` adds `_check_goals_yaml()`: presence, non-empty, parses with the same loader the workflow uses, and reports the number of goals. No connectivity check beyond the existing ones (folocli check already covers tier2 fetch path).

### D12: Tier-1 is batched

Tier-1 is the hot path (most items drop here) and its per-item input is tiny (title + ~200-char description). The runner therefore sends up to `_BATCH_SIZE=10` items in a single prompt to `radar_tier1_filter` and expects a parallel array of `Tier1Decision` back.

Why batched at this stage specifically:
- **OMLX is single-GPU**: `configs/models.yaml` caps `concurrency.omlx=2`, so true request parallelism tops out at 2x. The real win is *fewer requests with more items per request*, amortizing prefill.
- **Tier-1 inputs are small**: 10 items fit comfortably in context; the model just emits 10 short verdicts.
- **Tier-2 cannot batch**: full-article content (~16k chars/item) blows context after 2-3 items. Tier-2 stays per-item.

Validation + fallback:
- Agent output is `Tier1Batch(decisions: list[Tier1Decision])` with each decision tagged by `index` matching the input position.
- The runner asserts `len(decisions) == len(items)` AND `{d.index} == {0..N-1}`. Either mismatch → raise → fall back to per-item calls for that chunk.
- Per-item fallback uses `tier1.run(item, goals)` which is itself a batch of size 1 — one agent, one prompt shape.
- An item that fails *both* the batch AND its per-item retry is recorded as `tier1_error` and **not marked seen**, so the next run can re-attempt it.

Alternatives considered: concurrent single-item requests via `asyncio.gather`. Rejected — the OMLX concurrency cap of 2 makes the ceiling 2x and the structured-output overhead per request is paid every time. Batched prompts pay it once for N items.

## Risks / Trade-offs

- **Tier1 false drops** → user misses something. Mitigation: log all dropped item ids + reason; `paca info-radar analyze --replay <id>` can re-run tier2 on a specific item bypassing tier1. (Stretch task — see tasks.md.)
- **LLM judge cost on dedup** → not free. Mitigation: only called when ANN returns ≥1 candidate; goals.yaml + budget yields ≤5 candidates per check; topics table grows slowly.
- **Embedder dim drift** if we ever swap models → `vector(1024)` column is rigid. Mitigation: documented in D5; cross-bridge migration out of scope.
- **`folocli entry get` rate limits** → unknown ceiling. Mitigation: batch size cap (`limit` arg), sequential calls with `time.sleep(0.5)` between, surface 429-shaped errors loud.
- **YouTube subtitle availability is unreliable** → many videos lack captions. Mitigation: explicit `content_status='fallback'` on the analysis row makes degraded analyses observable; user can decide later whether to re-ingest with manual help.
- **Goals.yaml churn** → user edits goals mid-batch. Mitigation: loader is called once at run start; no live reload during a batch.
- **No backfill of pushed_topics** → first runs after merge will show every recent item as "novel" even if it's old news in user's head. Mitigation: documented; user can manually seed `radar_pushed_topics` rows or accept one noisy first batch.

## Migration Plan

1. Apply `scripts/bootstrap_db.py` to create `radar_analyses` and `radar_pushed_topics` (idempotent IF NOT EXISTS).
2. User creates `configs/info_radar/goals.yaml` (sample committed under `configs/info_radar/goals.example.yaml`).
3. Manual `paca info-radar analyze --limit 20` smoke run; inspect rows in `radar_analyses`.
4. Add scheduler entry; `paca schedule run-now info_radar_analysis` to validate end-to-end.

Rollback: drop the two new tables, remove scheduler entry, delete `configs/info_radar/goals.yaml`. `radar_items` and the collector are untouched.

## Open Questions

- None blocking implementation. Push channel (Discord vs dashboard) decided in a future change.
