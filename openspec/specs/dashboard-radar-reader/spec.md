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
- **THEN** the tracker and item list are bounded to the latest dashboard-triggered pull/analyze timestamps recorded in `~/.next-signal/radar-state.json`, falling back to latest DB clusters only when that state is absent

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

The `/radar` and `/radar/[id]` pages (`dashboard/app/radar/page.tsx` and `dashboard/app/radar/[id]/page.tsx`) SHALL render correctly in both light and dark themes on a 1440-wide desktop viewport.

#### Scenario: page renders correctly in both themes

- **WHEN** the operator toggles between light and dark theme on `/radar` or `/radar/[id]`
- **THEN** the page renders correctly in both, with no unstyled or broken elements

### Requirement: Radar feed export as Markdown or PDF

The `/radar` page SHALL offer "Download MD" and "Download PDF" links that export exactly the currently filtered view (same query params the page uses) via `GET /api/radar/export`. The PDF path SHALL drive system Chrome's headless `--print-to-pdf` (path overridable via `CHROME_BIN`) rather than bundling a PDF-rendering dependency. The page SHALL also support a `?export=1` print-only render mode with an "appendix" section, used as the source Chrome prints from.

#### Scenario: operator downloads the current filtered view as markdown

- **WHEN** the operator clicks "Download MD" with an active score/category filter
- **THEN** the exported markdown reflects the same filtered item set the page is currently showing

#### Scenario: operator downloads the current filtered view as PDF

- **WHEN** the operator clicks "Download PDF"
- **THEN** the export route renders the `?export=1` print view and drives headless Chrome to produce a PDF of it

### Requirement: Recap range selector

The radar index page SHALL offer a recap range selector with two rolling presets — last 7 days and last 30 days, both ending on the current local radar day — plus a custom `from`–`to` date pair. Presets SHALL be rolling windows rather than calendar periods, so their meaning does not depend on a locale-specific week start. The selected range SHALL be reflected in the URL query string so a recap view is linkable and survives reload. The recap request SHALL inherit the filter bar's current score threshold and novel-only setting as its quality gate, so the recap and the item list it summarizes describe the same population. The recap section SHALL be titled "Smart Recap" and SHALL sit above the "today's high-signal items" heading and its filter bar, since the recap is a synthesis over the items rather than one of them.

#### Scenario: recap section precedes the item list

- **WHEN** the radar index page renders outside export mode
- **THEN** the "Smart Recap" section appears above the filter bar and the item list

### Requirement: Smart Recap section is collapsible with a persisted preference

The Smart Recap section SHALL be collapsible from its header. The collapsed/expanded choice SHALL persist across navigation and reload — including the full re-render a filter change triggers — rather than resetting each time. Opening a specific saved recap SHALL present it expanded even when the reader's stored preference is collapsed, so a reopened recap is never hidden behind a collapsed header.

#### Scenario: collapse survives a filter change

- **WHEN** the reader collapses the Smart Recap section and then changes the score filter
- **THEN** the page re-renders with the section still collapsed

#### Scenario: reopening a saved recap shows it expanded

- **WHEN** the reader has the section collapsed and selects a recap from the saved list
- **THEN** the section renders expanded with that recap's content

#### Scenario: preset selects a rolling window

- **WHEN** the reader picks the last-7-days preset on local day 2026-07-20
- **THEN** the recap range resolves to `since` = 2026-07-14 and `until` = 2026-07-20, and the range appears in the URL

#### Scenario: quality gate follows the filter bar

- **WHEN** the reader has a minimum score of 70 and novel-only active, then requests a recap
- **THEN** the recap is requested with `min_score=70` and `novel_only=true`, keyed separately from the same range at the default gate

### Requirement: Recap panel renders themes with citations

When a recap exists for the selected range and gate, the radar index page SHALL render its headline and each theme's title and narrative, with each theme's citations shown as links to the corresponding radar detail pages. A citation whose `radar_items` row no longer exists SHALL render as plain text rather than a broken link. When the stored `considered_count` exceeds `item_count`, the panel SHALL state that the recap covers a subset (for example, "synthesized from the top 60 of 143 signals") rather than implying full coverage. All recap chrome SHALL be omitted in `?export=1` print mode unless and until export support is specified.

#### Scenario: themes render with working citations

- **WHEN** a `done` recap with three themes is displayed
- **THEN** each theme shows its title, narrative, and citation links that navigate to the cited items' detail pages

#### Scenario: capped recap states its coverage

- **WHEN** the displayed recap stores `item_count=60` and `considered_count=143`
- **THEN** the panel states that it covers 60 of 143 signals

#### Scenario: citation to a swept item degrades gracefully

- **WHEN** a displayed recap cites an item whose `radar_items` row has been removed by the 30-day sweep
- **THEN** that citation renders as plain non-clickable text and the rest of the panel is unaffected

### Requirement: Recap generation is spawn-and-poll, with visible status

Triggering a recap SHALL spawn the CLI detached through the shared `spawnPacaDetached` launcher and return immediately — the request path MUST NOT block on inference, which takes 30–60s locally. The page SHALL then poll the recap row for the selected key and render according to `status`: `'running'` shows an in-progress state, `'done'` renders the panel, `'error'` surfaces the failure message. A recap that ends in `'error'` after a regeneration SHALL still display its previously stored content alongside the error. Triggering while the key is already `'running'` SHALL NOT start a second generation.

#### Scenario: trigger returns immediately

- **WHEN** the reader triggers a recap
- **THEN** the server action spawns `paca info-radar recap` detached and returns a started response without waiting for completion

#### Scenario: poll surfaces a failure instead of hanging

- **WHEN** a recap generation ends with `status='error'`
- **THEN** the panel stops polling and displays the stored error message

#### Scenario: failed regeneration still shows the prior recap

- **WHEN** a regeneration of an existing `done` recap ends in `'error'`
- **THEN** the panel shows the previously stored headline and themes together with the error indication

### Requirement: Stale recaps are labelled, never silently regenerated

When further analyses have landed in the recap's range and gate since its `max_analyzed_at`, the panel SHALL display the cached recap together with an explicit staleness marker naming the number of newer signals, next to the regenerate control. The page MUST NOT auto-regenerate a stale recap on load — doing so would make every visit to a live range trigger a minute of inference.

#### Scenario: live range shows a staleness marker

- **WHEN** a last-7-days recap was generated and 5 further items in that range have since been analyzed
- **THEN** the panel renders the stored recap plus a marker reporting 5 newer signals, and no generation starts automatically

#### Scenario: settled range shows no marker

- **WHEN** the displayed recap's range and gate have had no analyses since `max_analyzed_at`
- **THEN** no staleness marker is shown

### Requirement: Previously-generated recaps are browsable

The radar index page SHALL list previously-generated (`done`) recaps in the past-days area, each showing its date range, item count, and headline, ordered by range newest-first. Selecting one SHALL reopen it in the recap section above without generating anything. Because a recap's identity includes its quality gate, the link SHALL carry the stored `min_score` and `novel_only` as well as the range; since those are the same parameters the filter bar uses, opening a past recap MAY also re-scope the item list to that gate, keeping the recap and the items consistent. The list SHALL be omitted in `?export=1` print mode.

#### Scenario: reopening a saved recap makes no LLM call

- **WHEN** the reader selects a recap from the saved list
- **THEN** the page navigates to that recap's range and gate, the recap section renders the stored content, and no generation is triggered

#### Scenario: saved list reflects the recap's own gate

- **WHEN** a saved recap was generated with `min_score=70` and `novel_only=true`
- **THEN** its list entry links with those parameters so the reopened recap resolves the same stored row

