## MODIFIED Requirements

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

## ADDED Requirements

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
