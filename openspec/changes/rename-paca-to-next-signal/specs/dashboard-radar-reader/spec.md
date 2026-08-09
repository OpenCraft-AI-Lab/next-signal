## MODIFIED Requirements

### Requirement: Ingest-to-wiki action

The `/radar/[id]` page AND each `/radar` item card SHALL expose an "Ingest to wiki" action that ingests the item via a Next.js server action. The server action SHALL re-fetch `source`, `source_id`, `url`, and `title` from DB by `radar_items.id` (never trusting a client-passed URL). For Folo-sourced rows, it SHALL fetch full content via `folocli entry get <source_id>`, stage that content as an HTML file under `NEXT_SIGNAL_AGENT_TMP_DIR`, and create a tracked job in the shared ingest-job registry (source `radar`) that runs `next-signal knowledge ingest <staged-file>`. For non-Folo rows, it SHALL validate `radar_items.url` via `new URL(...)` and create a tracked job that runs `next-signal knowledge ingest <url>`. Failures before the shared runner is called SHALL not create a job or spawn a subprocess and SHALL report an error via `sonner` toast. The job's progress SHALL be observable from the `/knowledge` active-ingests panel.

#### Scenario: ingest fires, is tracked, and toasts

- **WHEN** the operator clicks "Ingest to wiki" on a Folo-sourced item whose `source_id` resolves to full entry content
- **THEN** the server action stages that full content as an HTML file, creates a job in the shared ingest-job registry (source `radar`) that runs `next-signal knowledge ingest <staged-file>`, returns after the job is created, and a `sonner` toast confirms the ingest started

#### Scenario: non-Folo ingest uses URL

- **WHEN** the operator clicks "Ingest to wiki" on a non-Folo item with a valid `url`
- **THEN** the server action creates a job in the shared ingest-job registry (source `radar`) that runs `next-signal knowledge ingest <url>`, returns after the job is created, and a `sonner` toast confirms the ingest started

#### Scenario: progress visible on knowledge

- **WHEN** a radar-triggered ingest job is in progress and the operator opens `/knowledge`
- **THEN** the active-ingests panel shows that job's per-step progress, labeled source `radar`

#### Scenario: invalid URL is rejected

- **WHEN** the operator clicks "Ingest to wiki" on a non-Folo item whose `url` is `NULL` or does not parse as a valid `URL`
- **THEN** the action does NOT create a job or spawn a subprocess and the toast shows an error explaining the URL is missing or malformed

### Requirement: Combined `Pull + Analyze` trigger

The dashboard top nav SHALL render a single primary `Pull + Analyze` button (mounted into foundation's `<NavTriggerSlot />`) that runs a Next.js server action which (1) synchronously awaits `uv run next-signal info-radar pull`, records pull start/completion timestamps and inserted-row count in `radar-state.json`, then (2) captures the current unseen-item count (`radar_items WHERE seen_at IS NULL`) as the analyze denominator, records it together with an `analyzeRunning` marker and the analyze-start timestamp in `radar-state.json`, and spawns `uv run next-signal info-radar analyze` **tracked** (the dashboard process holds the child reference) with stdout/stderr routed to the dashboard actions log. The action SHALL return immediately after the spawn (not awaiting analyze) with one `sonner` toast confirming pull completion and analyze kickoff. The spawned child's exit (close or error) SHALL flip `analyzeRunning` back to false. If `analyzeRunning` is already true when the action runs, the action SHALL skip the analyze spawn and return a toast indicating a run is already in progress.

#### Scenario: combined run kicks off both phases

- **WHEN** the operator clicks `Pull + Analyze`
- **THEN** the action awaits `next-signal info-radar pull` to completion, captures the unseen-item count as the analyze denominator, records `analyzeRunning: true` + `analyzeTotal` + the analyze-start timestamp in `radar-state.json`, spawns `next-signal info-radar analyze` tracked, and returns `{ ok: true, message: "Pull complete · analyze started" }`

#### Scenario: analyze finish flips the running marker

- **WHEN** the spawned `next-signal info-radar analyze` child exits (zero or non-zero)
- **THEN** the dashboard's exit handler sets `analyzeRunning: false` in `radar-state.json`, leaving `lastAnalyzeAt` and `analyzeTotal` intact

#### Scenario: button reflects in-flight pull

- **WHEN** the action is in-flight through the pull phase
- **THEN** the button label reads `Pulling…` while pull is awaited; after the action returns, the button returns to its default label (there is no fixed-duration client-side `Analyzing…` timer — the analyze phase is reflected by the live progress view instead)

#### Scenario: pull failure surfaces in the toast

- **WHEN** `next-signal info-radar pull` exits non-zero
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

### Requirement: Recap generation is spawn-and-poll, with visible status

Triggering a recap SHALL spawn the CLI detached through the shared `spawnCliDetached` launcher and return immediately — the request path MUST NOT block on inference, which takes 30–60s locally. The page SHALL then poll the recap row for the selected key and render according to `status`: `'running'` shows an in-progress state, `'done'` renders the panel, `'error'` surfaces the failure message. A recap that ends in `'error'` after a regeneration SHALL still display its previously stored content alongside the error. Triggering while the key is already `'running'` SHALL NOT start a second generation.

#### Scenario: trigger returns immediately

- **WHEN** the reader triggers a recap
- **THEN** the server action spawns `next-signal info-radar recap` detached and returns a started response without waiting for completion

#### Scenario: poll surfaces a failure instead of hanging

- **WHEN** a recap generation ends with `status='error'`
- **THEN** the panel stops polling and displays the stored error message

#### Scenario: failed regeneration still shows the prior recap

- **WHEN** a regeneration of an existing `done` recap ends in `'error'`
- **THEN** the panel shows the previously stored headline and themes together with the error indication
