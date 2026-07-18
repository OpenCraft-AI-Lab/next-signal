## 1. Preconditions

- [x] 1.1 Confirm `dashboard-foundation` has landed: `pnpm dev` boots the shell with theme toggle and toast root; `Alpaca` + `RadarAlpaca` exist under `dashboard/components/brand/`; `scoreHue` / `scoreLOff` are in `dashboard/lib/score.ts`; `<NavTriggerSlot />` exists in the nav.
- [x] 1.2 Re-read `dashboard/design/pages-radar.jsx` end-to-end before writing any radar JSX. Tokens / shared primitives are already in foundation.

## 2. DB plumbing

- [x] 2.1 Add `pg` and `@types/pg` to `dashboard/package.json`; note in `dashboard/README.md` that these are added beyond the `agent-ui` mirror to support direct server-component reads.
- [x] 2.2 Author `dashboard/lib/db.ts`: export a singleton `pg.Pool` initialized from `DATABASE_URL` (or `PACA_DATABASE_URL` if set), stripping any `+psycopg` driver tag. Export a typed `query<T>(sql, params)` helper.
- [x] 2.3 Author `dashboard/lib/radar/queries.ts` with the following helpers — all queries gate on calendar-date in `America/Los_Angeles` (or operator-configured TZ via env, default LA), so "today" matches operator expectation:
  - `getDayGroups(daysBack: number)` → `{ day, keptCount, medianScore }[]`
  - `getItemsForDay(day: Date, filters: { sort, novelOnly, minScore })` → kept items joined with their `radar_analyses` row
  - `getTrackerForDay(day: Date)` → `{ date, pulledBySource: {source, n}[], pulledTotal, tier1: {kept, dropped}, tier2: {ok, fallback, error}, dedup: {novel, duplicate}, hist: number[11] }` — histogram bucketing via `LEAST(FLOOR(score/10), 10)`
  - `getItemDetail(itemId: number)` → `radar_items` LEFT JOIN `radar_analyses` LEFT JOIN `radar_pushed_topics` (on `dedup_match_id`)
  - `getFilteredTodayList(filters)` → list of `radar_items.id` for prev/next pagination
- [x] 2.4 Smoke each query against the local DB via a throwaway TS script (`pnpm tsx scripts/smoke.ts`), then delete.

## 3. Filter bar state via `nuqs`

- [x] 3.1 Author `dashboard/lib/radar/filter-params.ts` exporting `nuqs` parsers / loaders for `sort` (enum: `score-desc | score-asc | newest`, default `score-desc`), `novelOnly` (bool, default `false`), `minScore` (int 0..100 step 5, default 65).
- [x] 3.2 Author `dashboard/components/radar/filter-bar.tsx` (client component) consuming the parsers: `<Segmented>` for sort, toggle button for novel-only, range slider for min-score. Color the range thumb via `scoreHue` / `scoreLOff` to match the design.

## 4. `/radar` index page

- [x] 4.1 Author `dashboard/components/radar/today-tracker.tsx` (server component) consuming `getTrackerForDay(today)`. Render the header row (date pill + source chips — NO `run finished` or duration), then four pill clusters (pulled / tier1 / tier2 / dedup) + the histogram on the right. Drop the `run.finishedAt` and `run.durationSec` from `dashboard/design/pages-radar.jsx::RunTracker` when porting.
- [x] 4.2 Author `dashboard/components/radar/score-histogram.tsx`: 11 div bars across `0..100`, height-proportional within a 56px slot, colored via `scoreHue(bucketMid) / scoreLOff(bucketMid)`. No chart library.
- [x] 4.3 Author `dashboard/components/radar/signal-card.tsx` (client component for expand-summary toggle): score chip, dedup badge, content badge, tags, "Read source" + "Ingest" inline actions, click-to-expand summary↔impact, navigate to `/radar/[id]` on body click (carrying current filter params).
- [x] 4.4 Author `dashboard/components/radar/day-group.tsx` using `<Collapsible>` from foundation: header (label + date + kept badge + median chip + top headline preview), expanded body lists top 3 items + a "Show all N →" button (links to a date-scoped listing — left as a follow-up if the listing doesn't fit this change; for v1, "Show all" can route to `/radar?day=YYYY-MM-DD`).
- [x] 4.5 Author `dashboard/app/radar/page.tsx`: render `<RadarAlpaca size={72} />` + page title + "N kept" subtitle in the hero, then `<TodayTracker />`, then `<FilterBar />`, then today's filtered items via `<SignalCard />`, then past N days (default 14) via `<DayGroup />`. Today's items get filter params via `nuqs` `loadSearchParams()`.
- [x] 4.6 Verify against `dashboard/design/pages-radar.jsx::RadarPage` in light AND dark theme at 1440px viewport. Iterate Tailwind / token classes until parity.

## 5. `/radar/[id]` detail page

- [x] 5.1 Author `dashboard/app/radar/[id]/page.tsx`: fetch via `getItemDetail`; `notFound()` if no `radar_items` row; render placeholder if no `radar_analyses`. Render `impact_md` via `react-markdown` + `remark-gfm` + `rehype-raw` + `rehype-sanitize`.
- [x] 5.2 Show dedup matched-topic summary (from the LEFT JOIN on `radar_pushed_topics`) if `dedup_status='duplicate'`.
- [x] 5.3 Author `dashboard/components/radar/detail-pager.tsx` (server-rendered): computes today's filtered list via `getFilteredTodayList(filters)`, finds current item index, exposes prev / next ids, renders the top-of-page prev/next + bottom-of-page next-card or end-of-list affordance.
- [x] 5.4 Verify against `dashboard/design/pages-radar.jsx::RadarDetail` in light + dark themes at 1440px.

## 6. Ingest-to-wiki action

- [x] 6.1 Author `dashboard/lib/actions/radar.ts` exporting `ingestToWiki(itemId: number)`:
  - Re-fetch `radar_items.url` from DB by id (do NOT trust a client-passed URL).
  - Validate via `new URL(url)`; on failure, return `{ ok: false, message: "URL missing or malformed" }`.
  - Call `spawnPacaDetached(["knowledge", "ingest", url], { verb: "Ingest", logTag: "radar-ingest" })` from foundation's `lib/actions/spawn-paca.ts` — do NOT reimplement the spawn pattern.
- [x] 6.2 Add an `<IngestButton itemId>` client component (used both on `/radar/[id]` and inside `<SignalCard />`) that calls the action and surfaces the result via `sonner` toast.
- [x] 6.3 Manually verify: pick a radar item with a valid URL, click Ingest from card AND detail, confirm the toast appears, confirm `paca knowledge ingest <url>` is running (`pgrep -af "paca knowledge"`), confirm a wiki file lands under `PACA_WIKI_DIR` on completion.

## 7. Combined `Pull + Analyze` trigger

- [x] 7.1 Extend `dashboard/lib/actions/radar.ts` with `runPullAndAnalyze()`:
  - Pull phase is awaited (operator wants real success/failure signal for pull). Use raw `await execFile("uv", ["run", "paca", "info-radar", "pull"], { cwd: REPO_ROOT })` here — the spawn helper is for fire-and-forget, this is the synchronous half. Surface non-zero exit as `{ ok: false, message: <stderr excerpt> }`.
  - On pull success, call `spawnPacaDetached(["info-radar", "analyze"], { verb: "Analyze", logTag: "radar-analyze" })`. The returned message replaces the inline "Pull complete · analyze started" — use the helper's message verbatim ("Analyze started") or prefix it with "Pull complete · " in the action wrapper.
  - Return `{ ok: true, message: "Pull complete · analyze started" }`.
- [x] 7.2 Author `dashboard/components/radar/pull-analyze-button.tsx` (client component) mounted into foundation's `<NavTriggerSlot />`:
  - Local `phase` state: `null | "pulling" | "analyzing"`.
  - On click: set `phase="pulling"`, call `runPullAndAnalyze()`. On `ok`: set `phase="analyzing"`, toast success, set 6s timer to clear `phase`. On error: clear phase, toast error.
  - Button label / icon reflects phase: `Pull + Analyze` (default, sparkle icon) / `Pulling…` (loader) / `Analyzing…` (loader).
  - Button is disabled while phase is non-null.
- [x] 7.3 Manually verify: click button → `Pulling…` for the duration of the pull → toast "Pull complete · analyze started" → button reads `Analyzing…` for ~6s → returns to default. `radar_items` row count for today's `fetched_at` increases immediately. `radar_analyses` row count for today's `analyzed_at` increases within a few minutes.

## 8. Polish + docs

- [x] 8.1 Update `dashboard/README.md` with a `Radar` section: what `/radar` shows, how the tracker is computed, how the filter bar's URL params work, how `Pull + Analyze` works and what its caveats are (analyze is detached; failures land in logs).
- [x] 8.2 Add a one-line callout in root `CLAUDE.md` "当前状态" mentioning the new radar reader page.
- [x] 8.3 Smoke from a clean shell: `pnpm dev` in `dashboard/`, navigate `/` → redirected to `/radar`, see today's tracker + filter bar + items, click a card → detail, prev/next jumps within filter, click Ingest, click `Pull + Analyze`.
