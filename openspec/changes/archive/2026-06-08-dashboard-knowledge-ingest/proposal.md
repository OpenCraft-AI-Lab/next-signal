## Why

Ingesting a link into the wiki today only works from the terminal (`paca knowledge ingest <url>`). The `/knowledge` dashboard page can read and search the wiki and trigger a full re-index, but has no way to add a new source. The operator wants to paste a link, optionally pin which folder it lands in, and watch the multi-step pipeline (fetch → clean → enrich → classify → persist) run live instead of waiting blind for a detached subprocess.

## What Changes

- Add an ingest form to the `/knowledge` page: a URL/text input, an **optional** folder (category) selector populated from the wiki taxonomy, and a submit action.
- When a folder is chosen, the ingest **skips the LLM classify step** and writes to that folder; when left empty, classification stays automatic (current behavior).
- Route every ingest through a **shared in-process job registry**: both the `/knowledge` form and the existing `/radar` "Ingest to wiki" action create a tracked job instead of a detached fire-and-forget subprocess.
- Add an **"active ingests" panel** to `/knowledge` that subscribes (SSE) to the registry and renders **live per-step progress** for *every* running job regardless of where it was triggered — each stage shows pending → running → done/failed, labeled with its source (knowledge / radar) — ending with the final result (wiki path, category, GBrain index status) and a refreshed wiki tree.
- `paca knowledge ingest` gains a `--category <path>` option (validated against the taxonomy, loud failure on an unknown path) and a `--progress` flag that emits one JSON event per pipeline step to stdout, with the existing result JSON as the final line.
- The ingest workflow / `ingest_one` accepts an optional category override and an optional progress callback; the JSON result shape is unchanged.

## Capabilities

### New Capabilities
- `dashboard-knowledge-ingest`: the `/knowledge` dashboard ingest form (URL input + optional taxonomy folder selector) plus a shared in-process ingest-job registry and an "active ingests" panel that streams live per-step progress for every job — whether started here or from `/radar` — and refreshes the wiki tree on completion.

### Modified Capabilities
- `knowledge-pipeline`: `paca knowledge ingest` adds `--category` (validated) and `--progress` (JSONL step events) options; `ingest_one` / the ingest workflow accept an optional category override (skipping classify when set) and an optional per-step progress callback, without changing the result JSON shape. (The `paca knowledge ingest` command requirement already lives in this spec, so the CLI flag changes are homed here rather than in `core-cli`.)
- `dashboard-radar-reader`: the `/radar` "Ingest to wiki" action routes through the shared ingest-job runner (instead of a detached subprocess), so its progress is trackable in the `/knowledge` active-ingests panel.

## Impact

- Backend: `src/paca/workflows/knowledge_ingest.py` (`ingest_one`, classify step gating, progress hook), `src/paca/workflows/stages/knowledge_ingest/classify.py` (honor an override), `src/paca/interfaces/cli.py` (`knowledge ingest` flags). Category validation reuses `taxonomy.category_paths`.
- Dashboard: a shared in-process ingest-job registry + runner (`dashboard/lib/ingest/`), an SSE feed Route Handler under `dashboard/app/api/knowledge/ingest/`, new ingest-form + active-ingests components under `dashboard/components/knowledge/`, a taxonomy reader under `dashboard/lib/`, i18n strings, and wiring into `dashboard/app/knowledge/page.tsx`. `dashboard/lib/actions/radar.ts::ingestToWiki` switches from `spawnPacaDetached` to the shared runner.
- No DB changes. No new external dependencies. The registry is in-process (single Node process): in-flight progress views are lost on a dashboard restart, though the ingest subprocess and its artifact write are unaffected. Existing `paca knowledge ingest <url>` and the detached re-index path keep working unchanged.
