## Context

`/radar`'s `Pull + Analyze` button (`dashboard/components/radar/pull-analyze-button.tsx`) calls the `runPullAndAnalyze` server action (`dashboard/lib/actions/radar.ts`):

1. **Pull** — `execFileAsync("uv", ["run","paca","info-radar","pull"])`, *awaited* (blocking). Counts inserted rows, `recordPullClick(n)`.
2. **Analyze** — `spawnPacaDetached(["info-radar","analyze"])`, *fire-and-forget*, stdout → log file. `recordAnalyzeSpawn()`.

The button shows `Pulling…` while the action is awaited, then `Analyzing…` for a hard-coded **6-second** client timer, then resets. The 6 s is unrelated to the real run.

The analyzer (`src/paca/workflows/info_radar_analysis/runner.py`) processes N unseen `radar_items` through tier1 → fetch → tier2 → dedup, calling `mark_seen(item_id)` and `insert_analysis(...)` **per item**. `TodayTracker` (`dashboard/components/radar/today-tracker.tsx`, a server component) already renders the full counter breakdown from `radar_analyses` + `radar_items`, but only at page-load — it never moves during a run.

`radar-state.json` (`dashboard/lib/radar/run-state.ts`) already records `lastPullStartAt` / `lastPullAt` / `lastPullNew` / `lastAnalyzeAt`. The analyze nav chip already counts `radar_analyses.analyzed_at >= lastAnalyzeAt`.

## Goals / Non-Goals

**Goals:**
- Show real analyze progress (`done / total`) on `/radar` while a dashboard-triggered run is in flight, and let the existing tracker counters update live.
- Survive a page reload mid-analyze (progress reappears).
- Reuse data the analyzer already writes — no new event protocol, no backend changes.

**Non-Goals:**
- Per-source pull progress (operator: pull stays simple — `Pulling…` + the existing `+N` chip).
- Progress for scheduled (launchd) or CLI-initiated runs (operator: out of scope). Those still write the same DB rows; they simply do not get the live bar.
- Sub-stage detail per item (which item is in tier2 right now, etc.).
- DB schema changes or a persistent run history.

## Decisions

### 1. Numerator from the DB, denominator + finish from `radar-state.json`

The per-item `insert_analysis` is the progress signal that **already exists**. So:

- **`done`** = `count(radar_analyses WHERE analyzed_at >= lastAnalyzeAt)` — the *same* query the analyze nav chip already uses. No new write path.
- **`total`** = the count of unseen `radar_items` captured **right before** the analyze spawn (`SELECT count(*) FROM radar_items WHERE seen_at IS NULL`), stored as `analyzeTotal` in `radar-state.json`. Captured *after* pull, because pull may add unseen rows.
- **`running`** = a new `analyzeRunning` boolean in `radar-state.json`, set true at spawn and flipped false by the spawned child's exit handler.

*Why not pure DB inference for "running"* (e.g. `running := done < total`): tier1-`error` items deliberately are **not** `mark_seen`'d and produce **no** `radar_analyses` row (they retry next batch), so `done` can legitimately finish below `total`. A `done >= total` finish test would hang the bar forever on any tier1 error. An explicit finish marker is robust; `done/total` is only the bar's *visual fill*, never the authoritative "is it done".

### 2. Spawn analyze *tracked*, not detached, to get a finish signal

To flip `analyzeRunning` false reliably, the dashboard needs the child's exit. Replace `spawnPacaDetached` in `runPullAndAnalyze` with a `spawn` whose reference is held (stored on `globalThis`, like `lib/ingest/jobs.ts`) so it is not GC'd; attach `child.on("close", …) → recordAnalyzeFinish()`. stdout/stderr still go to the same `dashboard-actions.log` (we do **not** parse them — progress comes from the DB). The action still returns immediately after the spawn (it does not await analyze).

- *Why over keeping it detached + a staleness timeout:* a tracked child gives a precise, immediate finish; a timeout would either cut long runs short or leave the bar lingering.
- *Concurrency guard:* if `analyzeRunning` is already true, `runPullAndAnalyze` skips the analyze spawn and toasts that a run is in progress (the in-flight button-disable covers the common case; this covers a post-reload double click). `mark_seen` + `UNIQUE(radar_analyses.radar_item_id)` make a stray double-run harmless regardless.

### 3. 1.5 s poll, not SSE

A thin `GET /api/radar/run` returns `{ running, done, total }`. The client polls every ~1.5 s while `running`. Precision is not required (operator), and a single-value poll is far less machinery than an SSE feed for a singleton run. Contrast with `/knowledge`, which needs SSE because it multiplexes *many* concurrent jobs with *per-step* events; radar analyze is one run with a single scalar of interest.

### 4. Reuse `TodayTracker` for the breakdown; the bar is the only new visual

The new `run-progress.tsx` renders just the `done/total` bar + an `analyzing…` label. The detailed tier1/tier2/dedup/histogram breakdown is **already** `TodayTracker`. So while `running`, the poller calls `router.refresh()` on a throttled cadence (e.g. every other poll, ~3 s) so the server-rendered tracker re-queries and updates live; on the `running → false` transition it does one final `router.refresh()` so the tracker and item feed settle. No counter logic is duplicated into the client.

### 5. Seed `running` from server state on load

`/radar` (server component) reads `getRunState()` and passes `{ analyzeRunning, analyzeTotal, analyzeStartedAt }` into `run-progress.tsx` as initial props. So a full reload mid-analyze immediately shows the bar and starts polling — progress is not tied to the click that started it.

### 6. Drop the fake timer in the button

`pull-analyze-button.tsx` keeps the real `Pulling…` phase (the action is still awaited through pull). The `Analyzing…` 6-second `setTimeout` is removed; the analyze phase is now owned by `run-progress.tsx` / run-state, not a client timer.

## Risks / Trade-offs

- **Stale `analyzeRunning` after a dashboard restart mid-analyze** → the tracked child is parented to the old Node process; if the dashboard restarts, its close handler is lost and `analyzeRunning` can stay true. Accepted (mirrors `/knowledge`'s "lost on restart" caveat). Self-heals on the next `Pull + Analyze` (which rewrites the start marker) and the analyze subprocess + its DB writes are unaffected. Optional cheap mitigation if it bites: the poll route treats `running` as false once `done >= total` AND no new rows for a generous interval — deliberately deferred to keep this minimal.
- **`router.refresh()` cadence cost** → refreshing re-runs the `/radar` server queries every few seconds during a run. Fine for a local single-user dashboard; the throttle (~3 s, not every 1.5 s tick) keeps it modest. If it ever matters, fold the counters into the poll JSON instead.
- **`total` drift** → if a separate pull lands while analyze runs, new unseen rows are not in this run's `total`, so the bar could read e.g. `40/38`. Harmless; the bar clamps display to 100 % and the authoritative finish is the close marker.
- **Pull still blocks the action** → unchanged from today; acceptable since pull is short and the operator only wants the count.

## Migration Plan

Purely additive on the dashboard. `radar-state.json` gains two optional fields read with defaults (old files without them read as `analyzeRunning:false`, `analyzeTotal:0`). The only behavioral edit is `runPullAndAnalyze` swapping `spawnPacaDetached` + `recordAnalyzeSpawn` for a tracked spawn + `recordAnalyzeStart`/`recordAnalyzeFinish`. Rollback = revert; the CLI, scheduler, and nav chips are untouched.

## Open Questions

- Should the progress bar also show a coarse phase label beyond `analyzing N/M` (e.g. "tier1 / tier2")? Deferred — `TodayTracker` already shows the tier breakdown; start with the single bar.
- Should `done` exclude `verdict='drop'` items so the bar tracks "kept work" rather than "items processed"? Starting with **items processed** (every analysis row) since that matches "how far through the batch are we"; revisit if the drop ratio makes the bar feel misleading.
