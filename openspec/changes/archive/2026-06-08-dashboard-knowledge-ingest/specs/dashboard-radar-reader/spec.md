## MODIFIED Requirements

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
