## 1. Run-state: analyze progress fields

- [x] 1.1 Extend `RadarRunState` in `dashboard/lib/radar/run-state.ts` with `analyzeRunning: boolean` and `analyzeTotal: number`; read both with safe defaults (`false` / `0`) in `readState` so pre-existing `radar-state.json` files load unchanged.
- [x] 1.2 Replace `recordAnalyzeSpawn()` with `recordAnalyzeStart(total: number)` — sets `lastAnalyzeAt = now()`, `analyzeTotal = total`, `analyzeRunning = true` — and add `recordAnalyzeFinish()` — sets `analyzeRunning = false` (leaves `lastAnalyzeAt` / `analyzeTotal` intact). Keep the atomic tmp-rename write.

## 2. Action: capture denominator + tracked spawn

- [x] 2.1 In `runPullAndAnalyze` (`dashboard/lib/actions/radar.ts`), after the pull completes and `recordPullClick`, run `SELECT count(*)::text AS n FROM radar_items WHERE seen_at IS NULL` to get the analyze denominator.
- [x] 2.2 If `getRunState().analyzeRunning` is already true, skip the analyze spawn and return an "analyze already running" toast (success-style, no error).
- [x] 2.3 Replace the `spawnPacaDetached(["info-radar","analyze"])` + `recordAnalyzeSpawn()` path with: `await recordAnalyzeStart(total)`, then `spawn("uv", ["run","paca","info-radar","analyze"], { cwd: REPO_ROOT, env, stdio: [...,logfd,logfd] })` **non-detached**; hold the child reference on `globalThis` (mirror the `lib/ingest/jobs.ts` registry pattern) so it is not GC'd; attach `child.on("close", () => void recordAnalyzeFinish())` and `child.on("error", () => void recordAnalyzeFinish())`. Return immediately (do not await analyze). Keep the spawn logging to `dashboard-actions.log`.
- [x] 2.4 Confirm `spawn-paca.ts` / `recordAnalyzeSpawn` no longer have unused references after the swap; remove the orphaned `recordAnalyzeSpawn` export if nothing else uses it.

## 3. Poll endpoint

- [x] 3.1 Add `dashboard/app/api/radar/run/route.ts` (GET, `runtime = "nodejs"`, `dynamic = "force-dynamic"`): read `getRunState()`; if `lastAnalyzeAt` is set, compute `done = count(radar_analyses WHERE analyzed_at >= lastAnalyzeAt)` via the existing `pg` pool (`lib/db`); return `{ running: analyzeRunning, done, total: analyzeTotal }` as JSON. When `lastAnalyzeAt` is null, return `{ running: false, done: 0, total: 0 }`.

## 4. UI: progress bar + button cleanup

- [x] 4.1 Add `dashboard/components/radar/run-progress.tsx` (client): props `{ initialRunning, initialDone, initialTotal }`. When running, poll `GET /api/radar/run` every ~1.5 s; render a compact progress bar with an `analyzing N/M` label (clamp fill to 100 %). On a `running → false` transition, do one final `router.refresh()` and stop polling. While running, call `router.refresh()` on a throttled cadence (~every other tick) so `TodayTracker` updates live. Render nothing when not running.
- [x] 4.2 In `dashboard/app/radar/page.tsx`, read `getRunState()` and pass `analyzeRunning` / the live `done` (initial) / `analyzeTotal` into `<RunProgress />`, mounted near `TodayTracker` (only on the `isToday` view). Keep the existing layout otherwise untouched.
- [x] 4.3 In `dashboard/components/radar/pull-analyze-button.tsx`, remove the fake `Analyzing…` `setTimeout` phase and its `useEffect`. Keep the real `Pulling…` phase while the action is awaited; after the action returns, drop straight back to idle (the analyze phase is now owned by `<RunProgress />` + run-state). Toast still reflects the action result.
- [x] 4.4 Add i18n strings (en + zh) under `t.radar.*` for the progress label (e.g. `analyzing N/M`, `analyzeDone`) following the existing dictionary structure; reuse existing `pullAnalyze.*` keys where they still apply.

## 5. Verify

- [x] 5.1 `cd dashboard && npm run lint && npm run build` (or the repo's configured equivalents) pass with the new route/component.
- [x] 5.2 Run the dashboard dev server: click `Pull + Analyze` with unseen items present; confirm the bar appears, advances `done/total` while the analyzer runs, the `TodayTracker` counters move live, and the bar clears when the run finishes. Confirm a mid-run page reload re-shows the bar (seeded from `radar-state.json`).
- [x] 5.3 Confirm a zero-unseen click (`total = 0`) does not show a stuck/0-of-0 bar, and a second click while running is rejected with the "already running" toast.
- [x] 5.4 Update `docs/modules/info_filter.md` "规范与状态" to note the dashboard live analyze-progress view and the new `radar-state.json` fields.
