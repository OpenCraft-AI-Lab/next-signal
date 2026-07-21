## Context

`radar_analyses` already holds everything a recap needs — per-item `summary`, `impact_md`, `score`, `tags`, joined to `radar_items` for title/source/url. What's missing is a cross-item layer: `/radar` is day-scoped, and past days collapse to a count + median. The reader can see *that* last Tuesday kept 9 items; it cannot see what the week was about.

Three constraints shape the design:

1. **Local inference is slow.** A week's recap is a single call over ~40 item summaries — 30–60s on the OMLX endpoint. Nothing in the request path can wait for that.
2. **`local_structured` caps `max_tokens` at 4096**, deliberately (`configs/models.yaml` documents the reasoning at length: an uncapped structured-output agent can hang for 10+ minutes when xgrammar loops). The recap's output must fit that budget, and the cap must not be "temporarily" widened.
3. **The radar's day semantics are timezone-bound.** Day grouping uses `timezone(INFO_RADAR_TIMEZONE, analyzed_at)::date`. A recap range that used UTC or `published_at` would silently disagree with the day rows sitting right above it on the same page.

## Goals / Non-Goals

**Goals:**

- Turn a date range into 3–5 themed narratives with citations back to source items.
- Make repeat viewing free; make regeneration explicit.
- Be honest when a cached recap no longer covers everything in its range.
- Reuse the established fire-and-forget spawn + poll pattern rather than inventing a second async mechanism.

**Non-Goals:**

- Scheduled or automatic recaps. Manual trigger only; cadence is not a contract.
- Any change to the two-tier analysis pipeline, its agents, or its outputs.
- Push/notification delivery. The recap is read where it is generated.
- Recap history. One row per request key; regeneration replaces.

## Decisions

### D1: Recap identity is its inputs — `UNIQUE (since, until, min_score, novel_only)`

A recap is fully determined by the range plus the quality gate, so that tuple is the natural key. Regeneration upserts in place.

*Alternative considered:* append-only rows with `generated_at` ordering, latest wins. Rejected — it accumulates rows nobody reads, and there is no consumer for recap history. If one appears later, adding a history table is easier than pruning a table that grew one row per click.

This mirrors `radar_analyses`' `UNIQUE (radar_item_id)` idempotence idiom.

### D2: Staleness is detected, not prevented

A recap over an in-progress range (e.g. "last 7 days" generated this morning) goes stale as the analyzer writes more rows. Caching by key alone would silently serve this morning's answer all day.

The recap row stores `item_count` and `max_analyzed_at` — the watermark of what actually fed the LLM. On read, one cheap `COUNT(*) / MAX(analyzed_at)` over the same range+gate tells us whether new rows have landed. If they have, the panel renders the cached recap **plus** an explicit "N signals analyzed since this recap" marker next to the regenerate control.

*Alternative considered:* auto-expire cached recaps whose range ends today. Rejected — it turns every page load on a live range into a 60s inference job, which is exactly the cost the cache exists to avoid. Showing a stale answer *labeled as stale* respects the operator more than silently burning a minute of GPU.

### D3: Feed summaries, not `impact_md`; cap at 60 items and say so

The LLM input per item is `id`, `title`, `score`, `tags`, `summary`. `impact_md` is deliberately excluded: it is the per-item deep dive, and the recap's job is synthesis *across* items. Including it would roughly triple prompt size for content the themes are supposed to abstract away.

A month-range recap can exceed 200 kept items, so selection takes the **top 60 by score**. This is a real bound, not defensive padding. Both `item_count` (fed) and `considered_count` (matched the gate) are persisted so the UI can state "synthesized from the top 60 of 143" rather than implying full coverage. Silent truncation would make the recap read as exhaustive when it isn't.

### D4: Range bounds use `analyzed_at` in the radar timezone, inclusive

`timezone($tz, ra.analyzed_at)::date BETWEEN $since AND $until`. Matches `getDayGroups` / `getItemsForDay` exactly, so a 7-day recap covers precisely the seven day-rows shown beneath it.

*Alternative considered:* `published_at`. Rejected — it is nullable, and it would make the recap disagree with every other date on the page.

### D5: Presets are rolling windows, not calendar periods

"Last 7 days" / "Last 30 days" / custom from–to. Calendar week ("本周") requires picking a week-start convention that differs by locale, and on a Monday it produces a one-day recap. Rolling windows have one unambiguous meaning in both locales.

### D6: A `status` column drives the poll, and carries failures

`status` is `'running' | 'done' | 'error'`. The workflow writes the row with `status='running'` before the LLM call, then fills content and flips to `'done'`, or records `'error'` plus the message.

This does three jobs one state file could not: the dashboard poll reads the same row it will eventually render; a failed generation surfaces in the UI instead of polling forever; and a second trigger for a key already `'running'` is a cheap no-op.

**On regeneration, existing content columns are preserved while `status='running'`.** If the regenerate fails, the operator keeps the old readable recap plus an error marker — strictly better than blanking a good answer to show a failed one.

### D7: Output schema, and what happens when the model misbehaves

```
RecapOutput { headline: str, themes: list[Theme] }
Theme        { title: str, narrative: str, item_ids: list[int] }
```

Validation follows the house pattern of degrading rather than discarding:

- `item_ids` not present in the input set are **dropped** with a logged warning. A hallucinated citation should cost that citation, not the whole recap.
- Themes left with zero valid citations are dropped — an uncited theme is unverifiable.
- If **no** theme survives, the run is an error: `status='error'`, nothing persisted as `done`. This mirrors tier-2's rule that a failed analysis is not frozen into the table; the next attempt retries cleanly.

Theme count is requested as 3–5 in the prompt but not hard-enforced in code. Rejecting a good 6-theme recap over an off-by-one would be worse than accepting it.

### D8: Two files, SQL separated

`src/paca/workflows/info_radar_recap/__init__.py` (factory, `run()`, pydantic schemas, the agent call) and `store.py` (candidate selection, upsert, read). The sibling `info_radar_analysis/` splits further into `stages/` because it has four sequential LLM stages; recap has one, so that structure would be ceremony. Keeping SQL in `store.py` matches every other DB-touching module in the repo.

The workflow config is the established thin shell — `expose.agent_os: false` + `extra.run_now` — invoked by `paca info-radar recap` and `paca run-workflow`.

### D9: `max_tokens` stays at 4096

The recap agent references `model_profile: local_structured` and inherits the cap. Budget check: 5 themes × ~150 output tokens + headline ≈ 900 tokens, comfortably inside 4096. No profile change, no per-agent override. `configs/models.yaml` documents why widening this cap has already been tried and reverted; this change must not relitigate it.

### D10: Empty range short-circuits before the LLM

Zero items clearing the gate → no agent call, no row written. CLI prints the reason and exits zero; the panel shows an empty state. Spending 60s to have a model narrate the absence of input would be absurd.

## Risks / Trade-offs

- **Citations dangle after the 30-day sweep** → Accepted deliberately. `radar_recaps` holds no FK to `radar_items`; citation ids live in JSONB. A recap is a point-in-time artifact and should outlive its sources. The UI renders a citation whose item is gone as plain non-clickable text rather than a broken link.
- **Top-60 cap can hide long-tail items in wide ranges** → Mitigated by surfacing `considered_count` in the UI, so coverage is stated rather than implied.
- **Regeneration is destructive (D1)** → Mitigated by D6 preserving old content until new content succeeds. Worst case an operator regenerates and prefers the previous wording, which is unrecoverable. Judged acceptable; recaps are derived, and the sources remain.
- **A stale-but-cached recap could be mistaken for current** → Mitigated by D2's explicit marker. The failure mode is visible, not silent.
- **Local model quality on cross-item synthesis is unproven here** → The three existing analysis agents are per-item; clustering is a harder task. If output quality disappoints, the `local_structured` profile already carries `fallback_profile: deepseek_structured`, and the prompt is a file, not code.

## Migration Plan

Additive only. `scripts/bootstrap_db.py` gains one `CREATE TABLE IF NOT EXISTS` and is safe to re-run against an existing database — the container bootstrap already runs it on every start. No backfill: recaps are generated on demand, and an empty `radar_recaps` is the correct initial state.

Rollback is dropping the table and reverting the code; nothing else reads it.

## Open Questions

- Should the recap be exportable through the existing `?export=1` Markdown/PDF route? Natural fit, but it touches the export requirement and is easy to add once the panel exists. Deferred, not blocked.
- Is a 60-item cap right for a 30-day range? Chosen from the current keep rate (~40/week); worth revisiting once there is real usage data rather than tuning it blind now.
