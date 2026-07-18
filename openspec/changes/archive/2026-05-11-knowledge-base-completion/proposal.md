## Why

The artifact pipeline (Phase 6 Phases A/B/C) is shipped: every saved item produces durable markdown and (best-effort) GBrain ingest. What remains: a scheduled re-ingest workflow, a search tool surface for specialist agents, a dashboard page, and a `paca doctor` health check for the GBrain CLI.

## What Changes

- Add a `knowledge_ingest` workflow that walks `digitalpaca-wiki/`, diffs against GBrain, and re-embeds changed/new files.
- Add a `search_knowledge(query, topic=None)` tool so specialists can query the KB without going through the full agent.
- Add a `/knowledge` dashboard page listing documents, with re-index and search-test actions.
- Add a GBrain CLI / service health check to `paca doctor`.
- Schedule the ingest workflow weekly.

## Capabilities

### New Capabilities

- `knowledge-ingest-workflow`: scheduled diff-and-reembed workflow over the wiki tree.
- `knowledge-search-tool`: registered tool that queries GBrain.

### Modified Capabilities

- `cli`: `paca doctor` adds GBrain health check.
- `knowledge-pipeline`: gains a periodic re-ingest companion that complements the synchronous `paca knowledge save`.

## Impact

- Code: `src/paca/tools/knowledge/search.py`, `src/paca/workflows/knowledge_ingest.py`, dashboard page.
- Configs: schedule entry in `configs/schedules.yaml`.
- Depends on `launchd-scheduler` change for the weekly trigger.
