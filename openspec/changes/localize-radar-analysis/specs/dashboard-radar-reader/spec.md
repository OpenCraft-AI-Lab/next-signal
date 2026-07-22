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

### Requirement: Radar index page

The dashboard SHALL render `/radar` showing analyzed `radar_items` grouped by `analyzed_at::date`, with today's group expanded by default and prior days collapsed. The page hero SHALL render `<RadarAlpaca />` (from foundation's `dashboard/components/brand/`) alongside the page title and a "N kept" subtitle. Item cards SHALL render the analysis `display_title` when present, falling back to the source `radar_items.title` when it is null (unanalyzed / legacy rows), so the prominent title follows the analysis run's locale.

#### Scenario: today's items appear at the top

- **WHEN** the operator visits `/radar`
- **THEN** the page renders a section labelled with today's calendar date containing every `radar_analyses` row where `analyzed_at::date = today` and `verdict = 'keep'`, ordered per the current sort param

#### Scenario: card title follows the analysis locale

- **WHEN** a kept item has a non-null `display_title` generated under `locale="zh"`
- **THEN** its card shows the Chinese `display_title` rather than the English source feed title

#### Scenario: card falls back to the feed title

- **WHEN** a shown item has a null `display_title`
- **THEN** its card shows the raw `radar_items.title`

#### Scenario: past days are grouped and collapsed

- **WHEN** the operator visits `/radar`
- **THEN** prior calendar days appear as collapsed sections below today's section, each showing the day, the kept-count, and the median score, expandable to reveal the items

#### Scenario: drop verdicts are filtered out of the reading view

- **WHEN** the operator visits `/radar`
- **THEN** rows where `verdict = 'drop'` are NOT shown in either today's section or any past-day section — they only contribute to the tracker counters

### Requirement: Radar detail page

The dashboard SHALL render `/radar/[id]` for any `radar_items.id`, displaying the full analysis if one exists or a "not yet analyzed" placeholder if not. When an analysis `display_title` is present it SHALL be the page's prominent title, and the original `radar_items.title` SHALL be preserved and shown as a secondary source-title line so the localized headline never hides the source's own words.

#### Scenario: analyzed item shows full analysis

- **WHEN** the operator visits `/radar/<id>` for a `radar_items.id` with an existing `radar_analyses` row where `verdict='keep'`
- **THEN** the page shows the analysis `display_title` as the heading (falling back to `radar_items.title` when null), the original feed `radar_items.title` as a secondary source-title line, source, `published_at`, tags, the `summary` text, the `impact_md` rendered as markdown via `react-markdown` (with `remark-gfm`, `rehype-raw`, `rehype-sanitize`), the `tier1_reason`, `content_status`, `dedup_status` (with the matched `topic_summary` if `duplicate`), and the source `radar_items.excerpt` plus an external link to `radar_items.url`

#### Scenario: localized heading preserves the original title

- **WHEN** a kept item has a Chinese `display_title` and an English feed `radar_items.title`
- **THEN** the detail heading is the Chinese `display_title` and the English original title remains visible as the source-title line

#### Scenario: unanalyzed item shows a placeholder

- **WHEN** the operator visits `/radar/<id>` for a `radar_items.id` that has no `radar_analyses` row
- **THEN** the page shows the raw `radar_items` fields (title / source / excerpt / url) and a "not yet analyzed" notice — no error

#### Scenario: missing id returns 404

- **WHEN** the operator visits `/radar/<id>` for an id that does not exist in `radar_items`
- **THEN** the page returns a Next.js 404 response
