# knowledge-reindex

## Purpose
Keep the local wiki indexed in GBrain by re-ingesting only changed markdown files on demand.

## Requirements
### Requirement: Ingest workflow walks the wiki tree

`paca.workflows.knowledge_ingest` SHALL walk `~/Projects/digitalpaca-wiki/`, compute the diff against the current GBrain index, and call `gbrain_ingest` for new or changed paths.

#### Scenario: only changed files re-embed

- **WHEN** the workflow runs and only one document has changed
- **THEN** exactly one `gbrain_ingest` call is made

#### Scenario: failed embed does not advance manifest

- **WHEN** `gbrain_ingest` fails for a changed markdown file
- **THEN** the workflow raises a loud failure
- **AND** the manifest entry for that file is not advanced

### Requirement: Workflow runs on demand

The workflow SHALL be triggerable on demand via `paca run-workflow knowledge_ingest`, which the dashboard `Re-index` action invokes. There is no background scheduler.

#### Scenario: dashboard triggers a re-index

- **WHEN** the operator clicks `Re-index` on the dashboard `/knowledge` page
- **THEN** `paca run-workflow knowledge_ingest` runs the re-embed + Related-refresh sync and a toast confirms it started
