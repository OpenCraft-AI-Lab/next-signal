## ADDED Requirements

### Requirement: Knowledge ingest form on the dashboard

The `/knowledge` page SHALL render an ingest form with a text input for a URL or staged file path, an optional folder (category) selector, and a submit control. Submitting with an empty input SHALL be rejected client-side without starting a run.

#### Scenario: operator pastes a URL and submits

- **WHEN** the operator enters a URL into the ingest input and submits
- **THEN** the dashboard starts an ingest run for that value and shows the live progress view

#### Scenario: empty input is rejected

- **WHEN** the operator submits the ingest form with a blank input
- **THEN** no run starts and the form indicates the input is required

### Requirement: Optional folder selector from the taxonomy

The ingest form SHALL offer a folder selector implemented as a native `<select>` whose options are the category paths from `configs/knowledge_taxonomy.yaml`, plus a default "auto-classify" option carrying an empty value. The selector SHALL default to auto-classify. Category options SHALL be grouped by their top-level namespace (the path prefix before `/`) using `<optgroup>`, with paths that have no namespace shown ungrouped. Each category option SHALL expose its taxonomy `scope` text as a hover tooltip.

#### Scenario: folder list mirrors the taxonomy

- **WHEN** the ingest form renders
- **THEN** the selector lists every category `path` declared in the taxonomy, grouped under its namespace, and an auto-classify option as the default selection

#### Scenario: scope shown on hover

- **WHEN** the operator hovers a category option
- **THEN** the option's tooltip shows that category's taxonomy `scope` description

#### Scenario: chosen folder is passed through

- **WHEN** the operator picks a folder and submits
- **THEN** the ingest run is invoked with that category as the destination, bypassing automatic classification

#### Scenario: auto-classify left selected

- **WHEN** the operator submits without changing the selector from auto-classify
- **THEN** the ingest run is invoked without a category override and classification stays automatic

### Requirement: Shared ingest-job registry

The dashboard SHALL track ingest runs in a shared in-process job registry. Every ingest entry point — the `/knowledge` form and the `/radar` "Ingest to wiki" action — SHALL create a job in this registry rather than launching an untracked detached subprocess. Each job SHALL carry an id, the source label (`knowledge` or `radar`), per-step status, and a terminal result or error. The registry SHALL bound its retained finished jobs so a long-lived process does not accumulate them without limit.

#### Scenario: knowledge form creates a tracked job

- **WHEN** the operator submits the `/knowledge` ingest form
- **THEN** a job is created in the registry with source `knowledge` and begins reporting per-step progress

#### Scenario: radar action creates a tracked job

- **WHEN** the operator triggers "Ingest to wiki" from `/radar`
- **THEN** a job is created in the same registry with source `radar` and is observable from `/knowledge`

### Requirement: Active-ingests panel with live per-step progress

The `/knowledge` page SHALL render an "active ingests" panel that subscribes to the job registry over a single Server-Sent Events feed and displays a card per active (and recently finished) job. On connect the feed SHALL replay current jobs so a job already running (e.g. started from `/radar` before the page loaded) is shown. Each card SHALL display the job's source and each pipeline stage (fetch, clean, enrich, classify, persist) with a live status of pending, running, or done/failed, updated without a page reload.

#### Scenario: stages advance as the pipeline runs

- **WHEN** the backend reports a step starting and then completing for a tracked job
- **THEN** that job's card moves the stage from pending to running to done without a page reload

#### Scenario: radar-triggered job is visible on knowledge

- **WHEN** an ingest started from `/radar` is in progress and the operator opens `/knowledge`
- **THEN** the active-ingests panel shows that job's card (labeled source `radar`) with its current per-step progress

#### Scenario: a failing step is surfaced

- **WHEN** the backend reports a step error or a job exits non-zero
- **THEN** the job's failing stage is marked failed and the error detail is shown to the operator

### Requirement: Ingest result and tree refresh

On a successful run the dashboard SHALL show the resulting wiki path, the destination category, and the GBrain index status, and SHALL refresh the wiki tree so the new document appears in the sidebar.

#### Scenario: success surfaces the artifact and refreshes the tree

- **WHEN** an ingest run completes successfully
- **THEN** the dashboard shows the markdown path, category, and index status
- **AND** the wiki sidebar tree includes the newly ingested document
