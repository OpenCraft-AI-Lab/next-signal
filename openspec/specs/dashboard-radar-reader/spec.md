# dashboard-radar-reader

## Purpose

Provide the local dashboard reader for `info-radar`: browse kept analysis output by day, inspect item details, trigger pull/analyze runs, and ingest selected items into the wiki.
## Requirements
### Requirement: Radar index page

The dashboard SHALL render `/radar` showing analyzed `radar_items` grouped by `analyzed_at::date`, with today's group expanded by default and prior days collapsed. The page hero SHALL render `<RadarAlpaca />` (from foundation's `dashboard/components/brand/`) alongside the page title and a "N kept" subtitle.

#### Scenario: today's items appear at the top

- **WHEN** the operator visits `/radar`
- **THEN** the page renders a section labelled with today's calendar date containing every `radar_analyses` row where `analyzed_at::date = today` and `verdict = 'keep'`, ordered per the current sort param

#### Scenario: past days are grouped and collapsed

- **WHEN** the operator visits `/radar`
- **THEN** prior calendar days appear as collapsed sections below today's section, each showing the day, the kept-count, and the median score, expandable to reveal the items

#### Scenario: drop verdicts are filtered out of the reading view

- **WHEN** the operator visits `/radar`
- **THEN** rows where `verdict = 'drop'` are NOT shown in either today's section or any past-day section — they only contribute to the tracker counters

### Requirement: Today's run tracker

The `/radar` page SHALL render a tracker stats row above today's items computed live from `radar_items` and `radar_analyses` aggregates for today's calendar date, including pulled-by-source breakdown, tier-1 / tier-2 / dedup counters, and a 0..100 score histogram. The tracker SHALL NOT show a `finishedAt` timestamp or `durationSec` value. While a dashboard-triggered analyze run is active, the page SHALL refresh the tracker on a recurring cadence so its counters update without a manual page reload, and SHALL refresh once more when the run completes.

#### Scenario: tracker shows pulled-by-source counts

- **WHEN** the tracker renders
- **THEN** it shows the count of `radar_items` rows with `fetched_at::date = today`, broken down by `source`

#### Scenario: tracker shows tier-1 / tier-2 / dedup counters

- **WHEN** the tracker renders
- **THEN** it shows: tier-1 `kept` vs `dropped` (from `verdict`), tier-2 `ok` vs `fallback` vs `error` (from `content_status`, where rows with `verdict='keep'` and `content_status` set contribute), and dedup `novel` vs `duplicate` (from `dedup_status`)

#### Scenario: tracker shows a 0..100 score histogram

- **WHEN** the tracker renders
- **THEN** it shows an 11-bucket histogram (buckets of 10 across `0..100`) of `radar_analyses.score` for `verdict='keep' AND analyzed_at::date = today`, with bar heights proportional to bucket counts and bar colors derived from `scoreHue` / `scoreLOff` (from foundation's `lib/score.ts`) at the bucket midpoint

#### Scenario: tracker omits run-finished metadata

- **WHEN** the tracker renders
- **THEN** no `finishedAt` timestamp or `durationSec` value appears anywhere in the tracker — the tracker header is the date + source chips only

#### Scenario: tracker counters move while an analyze run is active

- **WHEN** an analyze run started from the dashboard is in progress
- **THEN** the page refreshes the tracker on a recurring cadence so its tier / dedup / histogram counters advance as rows are written, and a final refresh occurs when the run completes — without the operator manually reloading

### Requirement: Filter bar

The `/radar` page SHALL render a filter bar between the tracker and the item list, with controls for sort (`Score ↓` / `Score ↑` / `Newest`), `Novel only`, `Last feed`, and `Score ≥ N` (0–100, step 5, default 65). Filter state SHALL live in URL query params via `nuqs` so a filtered view is shareable. Server and client parsers SHALL use the same pure parse/serialize helpers while keeping `nuqs/server` out of client component imports.

#### Scenario: defaults apply when no query params are present

- **WHEN** the operator visits `/radar` with no query params
- **THEN** the visible item list is sorted by score descending, includes only `novel` items, and includes only items with `score >= 65`

#### Scenario: filter state round-trips through the URL

- **WHEN** the operator changes any filter control
- **THEN** the URL query params update (`?sort=newest&novelOnly=0&minScore=70&lastFeedOnly=1`), and reloading the page restores the same view

#### Scenario: empty state appears when filters exclude everything

- **WHEN** filters exclude every kept item for today
- **THEN** the items area shows an empty-state message hinting at lowering the score threshold or turning off `Novel only`

#### Scenario: past-day URLs pin the calendar day

- **WHEN** the operator follows a past-day link such as `/radar?day=2026-05-29`
- **THEN** the item list, counters, and detail pagination use that pinned day rather than silently falling back to today's list

#### Scenario: last-feed filter uses the most recent dashboard-triggered run

- **WHEN** `lastFeedOnly=1` is active on today's view
- **THEN** the tracker and item list are bounded to the latest dashboard-triggered pull/analyze timestamps recorded in `~/.intelligent-digitalpaca/radar-state.json`, falling back to latest DB clusters only when that state is absent

### Requirement: Radar detail page

The dashboard SHALL render `/radar/[id]` for any `radar_items.id`, displaying the full analysis if one exists or a "not yet analyzed" placeholder if not.

#### Scenario: analyzed item shows full analysis

- **WHEN** the operator visits `/radar/<id>` for a `radar_items.id` with an existing `radar_analyses` row where `verdict='keep'`
- **THEN** the page shows the item title, source, `published_at`, tags, the `summary` text, the `impact_md` rendered as markdown via `react-markdown` (with `remark-gfm`, `rehype-raw`, `rehype-sanitize`), the `tier1_reason`, `content_status`, `dedup_status` (with the matched `topic_summary` if `duplicate`), and the source `radar_items.excerpt` plus an external link to `radar_items.url`

#### Scenario: unanalyzed item shows a placeholder

- **WHEN** the operator visits `/radar/<id>` for a `radar_items.id` that has no `radar_analyses` row
- **THEN** the page shows the raw `radar_items` fields (title / source / excerpt / url) and a "not yet analyzed" notice — no error

#### Scenario: missing id returns 404

- **WHEN** the operator visits `/radar/<id>` for an id that does not exist in `radar_items`
- **THEN** the page returns a Next.js 404 response

### Requirement: Detail prev / next pagination

The `/radar/[id]` page SHALL show prev / next controls that paginate through the same day-scoped filtered list as `/radar` (using the same query params), with an "X of N · Y left" counter. The end-of-list SHALL show a "back to radar" affordance instead of a next button.

#### Scenario: filter params propagate

- **WHEN** the operator clicks an item card from `/radar?minScore=70`
- **THEN** the detail URL preserves `?minScore=70`, prev / next jump within that filtered subset, and the counter reflects the filtered total

#### Scenario: day params propagate

- **WHEN** the operator clicks an item from `/radar?day=2026-05-29`
- **THEN** the detail URL preserves the `day` query param, prev / next stay inside the 2026-05-29 list, and every "Back to radar" affordance returns to `/radar?day=2026-05-29`

#### Scenario: end of list

- **WHEN** the operator is on the last item of today's filtered list
- **THEN** the next-card area is replaced by a "You've reached the last item · Back to radar" affordance

### Requirement: Ingest-to-wiki action

The `/radar/[id]` page AND each `/radar` item card SHALL expose an "Ingest to wiki" action that ingests the item via a Next.js server action. The server action SHALL re-fetch `source`, `source_id`, `url`, and `title` from DB by `radar_items.id` (never trusting a client-passed URL). For Folo-sourced rows, it SHALL fetch full content via `folocli entry get <source_id>`, stage that content as an HTML file under `PACA_AGENT_TMP_DIR`, and create a tracked job in the shared ingest-job registry (source `radar`) that runs `paca knowledge ingest <staged-file>`. For non-Folo rows, it SHALL validate `radar_items.url` via `new URL(...)` and create a tracked job that runs `paca knowledge ingest <url>`. Failures before the shared runner is called SHALL not create a job or spawn a subprocess and SHALL report an error via `sonner` toast. The job's progress SHALL be observable from the `/knowledge` active-ingests panel.

#### Scenario: ingest fires, is tracked, and toasts

- **WHEN** the operator clicks "Ingest to wiki" on a Folo-sourced item whose `source_id` resolves to full entry content
- **THEN** the server action stages that full content as an HTML file, creates a job in the shared ingest-job registry (source `radar`) that runs `paca knowledge ingest <staged-file>`, returns after the job is created, and a `sonner` toast confirms the ingest started

#### Scenario: non-Folo ingest uses URL

- **WHEN** the operator clicks "Ingest to wiki" on a non-Folo item with a valid `url`
- **THEN** the server action creates a job in the shared ingest-job registry (source `radar`) that runs `paca knowledge ingest <url>`, returns after the job is created, and a `sonner` toast confirms the ingest started

#### Scenario: progress visible on knowledge

- **WHEN** a radar-triggered ingest job is in progress and the operator opens `/knowledge`
- **THEN** the active-ingests panel shows that job's per-step progress, labeled source `radar`

#### Scenario: invalid URL is rejected

- **WHEN** the operator clicks "Ingest to wiki" on a non-Folo item whose `url` is `NULL` or does not parse as a valid `URL`
- **THEN** the action does NOT create a job or spawn a subprocess and the toast shows an error explaining the URL is missing or malformed

### Requirement: Combined `Pull + Analyze` trigger

The dashboard top nav SHALL render a single primary `Pull + Analyze` button (mounted into foundation's `<NavTriggerSlot />`) that runs a Next.js server action which (1) synchronously awaits `uv run paca info-radar pull`, records pull start/completion timestamps and inserted-row count in `radar-state.json`, then (2) captures the current unseen-item count (`radar_items WHERE seen_at IS NULL`) as the analyze denominator, records it together with an `analyzeRunning` marker and the analyze-start timestamp in `radar-state.json`, and spawns `uv run paca info-radar analyze` **tracked** (the dashboard process holds the child reference) with stdout/stderr routed to the dashboard actions log. The action SHALL return immediately after the spawn (not awaiting analyze) with one `sonner` toast confirming pull completion and analyze kickoff. The spawned child's exit (close or error) SHALL flip `analyzeRunning` back to false. If `analyzeRunning` is already true when the action runs, the action SHALL skip the analyze spawn and return a toast indicating a run is already in progress.

#### Scenario: combined run kicks off both phases

- **WHEN** the operator clicks `Pull + Analyze`
- **THEN** the action awaits `paca info-radar pull` to completion, captures the unseen-item count as the analyze denominator, records `analyzeRunning: true` + `analyzeTotal` + the analyze-start timestamp in `radar-state.json`, spawns `paca info-radar analyze` tracked, and returns `{ ok: true, message: "Pull complete · analyze started" }`

#### Scenario: analyze finish flips the running marker

- **WHEN** the spawned `paca info-radar analyze` child exits (zero or non-zero)
- **THEN** the dashboard's exit handler sets `analyzeRunning: false` in `radar-state.json`, leaving `lastAnalyzeAt` and `analyzeTotal` intact

#### Scenario: button reflects in-flight pull

- **WHEN** the action is in-flight through the pull phase
- **THEN** the button label reads `Pulling…` while pull is awaited; after the action returns, the button returns to its default label (there is no fixed-duration client-side `Analyzing…` timer — the analyze phase is reflected by the live progress view instead)

#### Scenario: pull failure surfaces in the toast

- **WHEN** `paca info-radar pull` exits non-zero
- **THEN** the action returns `{ ok: false, message: <error excerpt> }`, no analyze is spawned, `analyzeRunning` is not set, and the toast shows the error

#### Scenario: second click while a run is active is rejected

- **WHEN** the operator triggers `Pull + Analyze` while `analyzeRunning` is already true
- **THEN** the action skips spawning a second analyze and returns a toast indicating a run is already in progress

#### Scenario: zero-result click is still visible

- **WHEN** the operator clicks `Pull + Analyze` and the pull inserts zero new `radar_items`
- **THEN** the nav chip shows the latest click timestamp with `+0`, and `Last feed` does not fall back to stale rows from a previous DB cluster

#### Scenario: analyze chip counts rows since the latest spawn

- **WHEN** the dashboard has a latest analyze spawn timestamp in `radar-state.json`
- **THEN** the analyze nav chip count is computed from `radar_analyses.analyzed_at >= lastAnalyzeAt`, so a new spawn initially shows `0` until rows are actually written

### Requirement: Live analyze progress view

The `/radar` page SHALL render a live analyze progress indicator while a dashboard-triggered analyze run is active. Progress SHALL be expressed as `done / total`, where `total` is the unseen-item count captured at analyze start (`analyzeTotal` in `radar-state.json`) and `done` is `count(radar_analyses WHERE analyzed_at >= lastAnalyzeAt)`. The indicator SHALL obtain these values by polling a `GET /api/radar/run` endpoint approximately every 1.5 seconds while running, and SHALL stop polling and clear the indicator when the run is no longer running. The indicator's running state SHALL be seeded from `radar-state.json` when the page loads, so a reload during an active run re-shows progress. The `done / total` value is a display fill only; whether a run is "running" is governed solely by the `analyzeRunning` marker, not by `done` reaching `total`.

#### Scenario: progress bar advances during a run

- **WHEN** an analyze run started from the dashboard is in progress
- **THEN** the `/radar` page shows a progress indicator that reads `analyzing N/M` and advances as `radar_analyses` rows are written, polling `GET /api/radar/run` about every 1.5 seconds

#### Scenario: progress reappears after a mid-run reload

- **WHEN** the operator reloads `/radar` while an analyze run is still active
- **THEN** the progress indicator is shown immediately on load (seeded from `radar-state.json`) and resumes polling, without requiring the operator to have started the run in that browser tab

#### Scenario: indicator clears when the run finishes

- **WHEN** the active analyze run's child process exits and `analyzeRunning` becomes false
- **THEN** the next poll observes `running: false`, the page does a final refresh so the tracker and item list reflect the completed run, and the progress indicator is removed

#### Scenario: no run, no indicator

- **WHEN** no analyze run is active (`analyzeRunning` is false or `radar-state.json` has no analyze record)
- **THEN** `GET /api/radar/run` returns `running: false` and the `/radar` page renders no progress indicator

#### Scenario: zero-denominator run does not show a stuck bar

- **WHEN** an analyze run starts with `analyzeTotal = 0` (no unseen items)
- **THEN** the page does not render a `0/0` progress bar that appears stuck; the run completes and clears normally

### Requirement: Direct Postgres reads from server components

The dashboard SHALL read `radar_items`, `radar_analyses`, and `radar_pushed_topics` directly from Postgres via the `pg` package in server components, using `DATABASE_URL` (with `+psycopg` driver tag stripped if present).

#### Scenario: DATABASE_URL is honored

- **WHEN** server components run any radar query
- **THEN** they connect using `DATABASE_URL` from the environment, transparently dropping the `+psycopg` driver tag if present, and reuse a single `pg.Pool` across requests

### Requirement: Design conformance

Implementations of the `/radar` and `/radar/[id]` pages SHALL match the committed reference in `dashboard/design/pages-radar.jsx` (plus shared primitives in `components.jsx` and tokens in `styles.css` / `pages.css`), in both light and dark themes on a 1440-wide desktop viewport.

#### Scenario: implementer follows the mock

- **WHEN** the implementer starts the `/radar` or `/radar/[id]` task
- **THEN** they first read `dashboard/design/pages-radar.jsx` end-to-end, and the final rendered page matches the mock in both light and dark themes

