## 1. Search tool

- [x] 1.1 `src/paca/tools/knowledge/search.py::search_knowledge(query, topic=None)`.
- [x] 1.2 Register in `_IN_TREE_TOOLS`.
- [x] 1.3 Unit test against a fixture GBrain response.

## 2. Ingest workflow

- [x] 2.1 `src/paca/workflows/knowledge_ingest.py` — diff wiki tree vs GBrain, call ingest.
- [x] 2.2 Register in `os_app._build_workflows()`.
- [x] 2.3 Add weekly schedule entry to `configs/schedules.yaml`.

## 3. Doctor + dashboard

- [x] 3.1 Add GBrain health check to `paca doctor`.
- [x] 3.2 `dashboard/app/knowledge/page.tsx` — list documents, trigger re-index, search test.

## 4. Verify

- [x] 4.1 Add a new doc to wiki → run workflow → query via `knowledge_manager`.
- [x] 4.2 Confirm `paca doctor` flags missing GBrain CLI.
