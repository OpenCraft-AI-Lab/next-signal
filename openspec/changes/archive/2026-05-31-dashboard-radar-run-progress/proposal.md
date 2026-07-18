## Why

Clicking `Pull + Analyze` on `/radar` today is a black box. Pull blocks (the operator just sees `Pulling…`), then analyze is spawned **detached** and the button shows `Analyzing…` for a hard-coded **6 seconds** — a fake timer unrelated to the actual run, which is a multi-minute, N-item, two-tier LLM pipeline. There is no way to see how many items the analyzer is working through or when it actually finishes; the rich `TodayTracker` counters already exist but are computed once at page load and never move during a run. `/knowledge` already shows live per-step ingest progress, so the radar page feels conspicuously blind by comparison.

This change gives `Pull + Analyze` a real, live progress view — without inventing a new event protocol — by reusing the per-item signal the analyzer **already writes to the database**.

## What Changes

- Replace the fake client-side `Analyzing…` 6-second timer with a **real progress view** driven by the actual run state.
- The combined action, after pull completes, captures the **unseen-item count** as the analyze denominator and records an `analyzeRunning` marker in `radar-state.json`; it spawns `paca info-radar analyze` **tracked** (held by the dashboard process) so the child's exit flips `analyzeRunning` back to false. The analyze numerator (`done`) reuses the existing `radar_analyses.analyzed_at >= lastAnalyzeAt` count.
- Add a thin `GET /api/radar/run` poll endpoint returning `{ running, done, total }`. The `/radar` page renders a small progress bar (`analyzing N/M`) while a run is active, polling every ~1.5 s. The bar's running state is **seeded from `radar-state.json` at page load**, so reloading mid-analyze still shows progress.
- While a run is active, the poller refreshes the page on a throttled cadence so the **existing `TodayTracker`** counter breakdown updates live; on completion it does one final refresh so the tracker and item list settle. No counter rendering is duplicated.
- **Pull stays simple** (per the operator): it remains a single blocking call surfaced as `Pulling…` + the existing `+N` pulled chip — no per-source progress.
- **Scheduled / CLI runs are out of scope** (per the operator): only dashboard-initiated runs surface live progress.

## Capabilities

### Modified Capabilities
- `dashboard-radar-reader`: the `Combined Pull + Analyze trigger` requirement drops the hard-coded 6-second `Analyzing…` timer and the pure fire-and-forget detached spawn; analyze is now spawned **tracked**, records `analyzeRunning` + the unseen-count denominator in `radar-state.json`, and the page shows a **live analyze progress bar** (`done/total`) polled from a new `GET /api/radar/run` endpoint and seeded from run-state on load. The `Today's run tracker` requirement gains a live-refresh behavior while a run is active (the counters update without a manual reload).

## Impact

- Dashboard only — **no backend / Python / DB-schema changes**. The analyzer already writes `radar_analyses` rows and `radar_items.seen_at` per item; this change only reads existing data plus a couple of new fields in the existing `radar-state.json`.
- Files: `dashboard/lib/radar/run-state.ts` (add `analyzeRunning` + `analyzeTotal`; add `recordAnalyzeStart(total)` / `recordAnalyzeFinish()`), `dashboard/lib/actions/radar.ts::runPullAndAnalyze` (capture unseen count, write start marker, spawn analyze tracked with a close handler writing the finish marker — replacing the plain `spawnPacaDetached` + `recordAnalyzeSpawn` path), a new `dashboard/app/api/radar/run/route.ts` poll endpoint, a new `dashboard/components/radar/run-progress.tsx` client component, wiring + run-state props into `dashboard/app/radar/page.tsx`, an updated `dashboard/components/radar/pull-analyze-button.tsx` (drop the fake timer), and i18n strings under `t.radar.*`.
- Accepted limitation (mirrors `/knowledge`): the tracked-child finish marker is best-effort — a dashboard restart mid-analyze can leave `analyzeRunning` stale until the next run or reload. No persistence beyond `radar-state.json`. The analyze subprocess and its DB writes are unaffected regardless.
- Existing `paca info-radar pull` / `analyze` CLI, the nav chips, and the detached scheduler path keep working unchanged.
