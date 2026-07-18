## 1. Backend: category override

- [x] 1.1 Add `category: str | None = None` to `ingest_one` in `src/paca/workflows/knowledge_ingest.py`; validate up front against `taxonomy.category_paths(load_taxonomy())` and raise a loud `RuntimeError` on an unknown path before running the workflow.
- [x] 1.2 Pass the override through `additional_data` (e.g. `{"category": ...}`) and update `classify_step` / `classify.py` so the classify step uses a valid override and skips the `knowledge_classifier` agent; falls back to LLM classification when absent.
- [x] 1.3 Add a test in `tests/` covering: valid override sets category + skips classifier, omitted override classifies, invalid override raises (use a fake/monkeypatched fetch + classifier so no network/LLM is needed).

## 2. Backend: per-step progress

- [x] 2.1 Add `on_progress: Callable[[dict], None] | None = None` to `ingest_one`; emit `{"step", "status": "start"|"done"|"error", ...}` around each workflow step (wrap step executors or iterate with a callback). Ensure the result JSON shape is unchanged.
- [x] 2.2 Verify a failing step emits an `error` event naming the step before the error propagates; cover with a test using a callback recorder.

## 3. CLI flags

- [x] 3.1 Add `--category` and `--progress` options to `knowledge_ingest_cmd` in `src/paca/interfaces/cli.py`; wire `--category` to `ingest_one(category=...)`.
- [x] 3.2 With `--progress`, pass an `on_progress` callback that prints each event as a JSON line to stdout and flushes; keep the final result JSON as the last line (valid JSONL). Without `--progress`, behavior is the current single result line.
- [x] 3.3 Smoke-test the CLI output shape (e.g. `--progress` produces N event lines + 1 result line; route non-event logging to stderr so stdout stays clean JSONL).

## 4. Dashboard: job registry + plumbing

- [x] 4.1 Add `dashboard/lib/taxonomy.ts` that reads `configs/knowledge_taxonomy.yaml` (resolve path via `lib/paths`) and returns `{ path, scope }[]`, mirroring `lib/goals.ts`.
- [x] 4.2 Add `dashboard/lib/ingest/jobs.ts`: a module-level `Map<jobId, IngestJob>` + `EventEmitter`, and `startIngestJob(value, {category?, source})` that spawns `uv run paca knowledge ingest <value> [--category <c>] --progress` non-detached at `REPO_ROOT` (reuse env/log conventions from `spawn-paca.ts`), reads child stdout line-by-line with cross-chunk buffering, `try`-parses each line and **skips non-JSON** (structlog logs to stdout — see design Risks), updates job step state / final result, emits an update, and marks `done`/`error` on exit. Returns the jobId immediately; keep a bounded recent-finished list.
- [x] 4.3 Add a thin server action `startKnowledgeIngest(value, category?)` (in `lib/actions/knowledge.ts`) that calls `startIngestJob(..., source: "knowledge")` and returns the jobId + a started/toast result.
- [x] 4.4 Add the SSE feed Route Handler `dashboard/app/api/knowledge/ingest/stream/route.ts` (GET): on connect snapshot all active + recently-finished jobs, then stream registry emitter updates via a `ReadableStream`; remove the listener on client cancel/disconnect.
- [x] 4.5 Switch `dashboard/lib/actions/radar.ts::ingestToWiki` from `spawnPacaDetached` to `startIngestJob(url, {source: "radar"})`, keeping the existing DB url re-fetch + `new URL()` validation + toast.

## 5. Dashboard: UI

- [x] 5.1 Add an ingest form component under `dashboard/components/knowledge/` (URL input, submit → `startKnowledgeIngest`). Folder picker = native `<select>`: empty-value "auto-classify" default option, then taxonomy paths grouped into `<optgroup>` by namespace prefix (`life` ungrouped), each option's `title` = its `scope`. Reject empty URL input client-side.
- [x] 5.2 Add an "active ingests" panel component that opens one SSE connection to the feed (fetch + reader), renders a card per job showing its source label and the five stages (fetch/clean/enrich/classify/persist) as pending → running → done/failed; on completion shows `markdown_path` / `category` / GBrain status, on error shows the failing step + detail. Finished cards linger briefly then drop.
- [x] 5.3 On a job completing successfully, refresh the wiki tree (`router.refresh()` / `revalidatePath("/knowledge")`) so the new doc appears in the sidebar.
- [x] 5.4 Wire the form + active-ingests panel into `dashboard/app/knowledge/page.tsx` (near the existing re-index control / header) without disturbing the existing search/tree/preview layout.
- [x] 5.5 Add i18n strings (en + zh) for the form labels, folder/auto-classify options, source labels (knowledge/radar), stage names, and result/error messages, following the existing `t.knowledge.*` dictionary structure.

## 6. Verify

- [x] 6.1 `uv run pytest -q` green (new backend tests included); `uv run ruff check src` clean if configured.
- [x] 6.2 Run the dashboard dev server and ingest a real URL end-to-end from `/knowledge`: confirm stages advance live in the active-ingests panel, the artifact appears in the wiki tree, and a chosen folder lands the doc there; confirm auto-classify still works with the selector left default. Then trigger "Ingest to wiki" from `/radar`, open `/knowledge`, and confirm that job's progress appears in the panel labeled source `radar`.
- [x] 6.3 Update `docs/modules/knowledge.md` "规范与状态" and any affected `CLAUDE.md` notes to mention the dashboard ingest entry + new CLI flags.
