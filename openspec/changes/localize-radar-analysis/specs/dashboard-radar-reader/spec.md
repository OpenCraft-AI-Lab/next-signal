## MODIFIED Requirements

### Requirement: Combined `Pull + Analyze` trigger

The dashboard top nav SHALL render a single primary `Pull + Analyze` button (mounted into foundation's `<NavTriggerSlot />`) that runs a Next.js server action which (1) synchronously awaits `uv run paca info-radar pull`, records pull start/completion timestamps and inserted-row count in `radar-state.json`, then (2) captures the current unseen-item count (`radar_items WHERE seen_at IS NULL`) as the analyze denominator, records it together with an `analyzeRunning` marker and the analyze-start timestamp in `radar-state.json`, and spawns `uv run paca info-radar analyze --locale <locale>` **tracked** (the dashboard process holds the child reference), where `<locale>` is the active UI locale (`paca_locale`, normalized to `zh`/`en`), with stdout/stderr routed to the dashboard actions log. The action SHALL return immediately after the spawn (not awaiting analyze) with one `sonner` toast confirming pull completion and analyze kickoff. The spawned child's exit (close or error) SHALL flip `analyzeRunning` back to false. If `analyzeRunning` is already true when the action runs, the action SHALL skip the analyze spawn and return a toast indicating a run is already in progress.

#### Scenario: combined run kicks off both phases

- **WHEN** the operator clicks `Pull + Analyze`
- **THEN** the action awaits `paca info-radar pull` to completion, captures the unseen-item count as the analyze denominator, records `analyzeRunning: true` + `analyzeTotal` + the analyze-start timestamp in `radar-state.json`, spawns `paca info-radar analyze --locale <locale>` tracked, and returns `{ ok: true, message: "Pull complete · analyze started" }`

#### Scenario: analyze uses the active UI locale

- **WHEN** the operator has the dashboard set to English and clicks `Pull + Analyze`
- **THEN** the spawned analyze command includes `--locale en`, so the generated analyses are in English

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
