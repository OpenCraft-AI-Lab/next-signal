## MODIFIED Requirements

### Requirement: Workflow runs on demand

The workflow SHALL be triggerable on demand via `next-signal run-workflow knowledge_ingest`, which the dashboard `Re-index` action invokes. This workflow SHALL NOT be placed on the wall-clock schedule specified by `core-schedule`: re-indexing is driven by the operator editing the wiki, not by the clock, and a scheduled re-embed would spend model tokens on a corpus that has not changed. A scheduler exists in the system, but it drives the radar chain only.

#### Scenario: dashboard triggers a re-index

- **WHEN** the operator clicks `Re-index` on the dashboard `/knowledge` page
- **THEN** `next-signal run-workflow knowledge_ingest` runs the re-embed + Related-refresh sync and a toast confirms it started

#### Scenario: the scheduler leaves re-index alone

- **WHEN** a scheduled slot comes due
- **THEN** only the radar chain runs, and `knowledge_ingest` is not invoked
