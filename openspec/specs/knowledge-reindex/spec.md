# knowledge-reindex

## Purpose
Keep the local wiki indexed in GBrain by re-ingesting only changed markdown files on demand or on a weekly schedule.

## Requirements
### Requirement: Ingest workflow walks the wiki tree

`paca.workflows.knowledge_ingest` SHALL walk `/Users/digital-paca/Projects/digitalpaca-wiki/`, compute the diff against the current GBrain index, and call `gbrain_ingest` for new or changed paths.

#### Scenario: only changed files re-embed

- **WHEN** the workflow runs and only one document has changed
- **THEN** exactly one `gbrain_ingest` call is made

#### Scenario: failed embed does not advance manifest

- **WHEN** `gbrain_ingest` fails for a changed markdown file
- **THEN** the workflow raises a loud failure
- **AND** the manifest entry for that file is not advanced

### Requirement: Workflow runs on a schedule

The workflow SHALL be registered in `configs/schedules.yaml` to run weekly via the launchd scheduler, with a manual `paca schedule run-now` override available.

#### Scenario: weekly cadence

- **WHEN** seven days have elapsed since the last successful run
- **THEN** the launchd dispatcher invokes the workflow on next wake
