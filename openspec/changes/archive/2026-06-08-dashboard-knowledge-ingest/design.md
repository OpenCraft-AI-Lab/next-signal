## Context

The single-source ingest pipeline (`ingest_one` in `src/paca/workflows/knowledge_ingest.py`) runs five sequential agno steps: **fetch → clean → enrich → classify → persist**. `classify` calls the `knowledge_classifier` LLM agent to pick a wiki folder from `configs/knowledge_taxonomy.yaml`; `persist` validates the category, writes the wiki markdown, and ingests into GBrain. The CLI `paca knowledge ingest <value>` wraps `ingest_one` and prints the final result JSON.

The dashboard `/knowledge` page (`dashboard/app/knowledge/page.tsx`) is a server component that reads the wiki tree (`lib/wiki.ts`), runs GBrain search (`lib/actions/knowledge.ts`), and triggers a **detached** weekly re-index via `spawnPacaDetached` — fire-and-forget, toast says "started". The dashboard already reads backend config files directly in TS (`lib/goals.ts` reads `goals.yaml`, `lib/wiki.ts` walks the wiki), so reading the taxonomy YAML in TS is an established pattern.

Two gaps: (1) no way to add a source from the dashboard, and (2) the only existing "run something" pattern is detached, which cannot report per-step progress.

## Goals / Non-Goals

**Goals:**
- Paste a URL (or staged file path) in `/knowledge` and ingest it without leaving the page.
- Optionally pin the destination folder from the taxonomy; empty = keep auto-classification.
- Show the pipeline running live (each stage pending → running → done/failed) and the final result.
- Show live progress for *every* ingest in one place, including jobs triggered from `/radar`'s "Ingest to wiki" — both entry points feed one shared job registry.
- Keep the existing CLI, result JSON shape, and detached re-index path working unchanged.

**Non-Goals:**
- Editing the produced artifact (frontmatter/body) from the dashboard — out of scope, like the existing aspirational Edit/Open buttons.
- Bulk / multi-URL ingest, drag-and-drop file upload, or progress for the weekly re-index.
- New taxonomy categories or a folder-management UI — the selector lists existing taxonomy paths only.
- Durable ingest history — the job registry is in-memory and ephemeral (bounded recent list); no DB/file persistence, no history across dashboard restarts.

## Decisions

### 1. Category override skips classify (not post-hoc move)

`ingest_one` gains `category: str | None = None`. The override is passed through `additional_data`; the `classify` step uses it when present and valid, otherwise runs the LLM classifier as today. `persist` already calls `validate_category`, so an invalid override fails loud there — but we validate **up front** in `ingest_one`/CLI against `taxonomy.category_paths()` to fail before any fetch work.

- *Why over a post-classify override:* skipping the LLM is cheaper and matches intent ("put it here"). Gating inside the existing `classify` step keeps the workflow's 5-step shape and per-step progress events intact (classify still emits an event, just deterministic).
- *Alternative rejected:* a 6th "move" step — redundant with `persist`'s category handling and would duplicate path logic.

### 2. Live progress = CLI JSONL events + shared in-process job registry + SSE feed

Progress must be visible from `/knowledge` even for a job started elsewhere (the `/radar` "Ingest to wiki" action). A request-scoped stream (one SSE tied to the request that launched the ingest) cannot show a job another page kicked off, so progress lives in a **shared, job-keyed registry** that any page subscribes to. Three coordinated pieces:

- **Backend (CLI ↔ Python):** unchanged from Decision elsewhere — `ingest_one` accepts `on_progress: Callable[[dict], None] | None`; the CLI `--progress` flag prints each `{"step", "status": "start"|"done"|"error", ...}` event as a JSON line to stdout, with the final result JSON as the last line (valid JSONL).
- **Dashboard registry + runner** (`dashboard/lib/ingest/jobs.ts`): a module-level `Map<jobId, IngestJob>` plus an `EventEmitter`. `startIngestJob(value, {category?, source})` creates a job (`status: running`, empty step state), spawns `uv run paca knowledge ingest <value> [--category <c>] --progress` **non-detached**, reads child stdout line-by-line (buffering across chunks), parses each JSON line into the job's step state / final result, emits an update on the emitter, and marks the job `done`/`error` on child exit. It returns the `jobId` immediately; the child and its stdout listeners outlive the call because the registry holds the reference (single Node process, request lifecycle does not unregister them). Finished jobs linger briefly (bounded recent list) then drop.
- **Two entry points → one runner:** the `/knowledge` form calls a thin server action `startKnowledgeIngest(value, category?)` → `startIngestJob(..., source: "knowledge")`; `radar.ts::ingestToWiki` calls `startIngestJob(url, source: "radar")` instead of `spawnPacaDetached`. Both return a jobId + a "started" toast.
- **Subscribe feed** (`dashboard/app/api/knowledge/ingest/stream/route.ts`, GET, SSE): on connect, replays a snapshot of all active + recently-finished jobs, then streams emitter updates via a `ReadableStream` until the client disconnects (listener removed on cancel). The `/knowledge` "active ingests" panel holds one such connection and renders a card per job.

- *Why split start (server action) from stream (GET Route Handler):* starting a job returns a single value (the id) → a server action fits the existing `lib/actions/*` pattern (matches today's `ingestToWiki`). Streaming needs an incrementally-flushed `Response` body → a Route Handler. Neither needs the other's shape.
- *Why a global SSE feed, not per-job `?job=<id>`:* `/knowledge` wants "everything currently running," and jobs may already be in flight when the page loads (radar-triggered). A single feed that snapshots-then-tails covers page reload and cross-page triggers without the client having to know job ids up front.
- *Why CLI JSONL, not importing Python from Node:* the CLI is already the dashboard↔backend boundary (`spawnPacaDetached` shells `uv run paca`). Keeping that boundary avoids a second integration surface.
- *Why in-memory over per-job JSONL files (chosen by the operator):* most direct/live and least code; acceptable for a local single-process dashboard. Trade-off accepted: state is lost on a dashboard restart and it assumes one Node process (see Risks). The file-backed alternative (`~/.intelligent-digitalpaca/ingest-jobs/<id>.jsonl` + directory tail) would survive restarts and reuse the detached-to-logfile pattern, but adds tail/watch logic; revisit if restart-resilience or multi-process becomes a need.
- *Alternative rejected (simplest):* keep `spawnPacaDetached` everywhere and just toast "started". Loses the live pipeline view the user explicitly asked for, and cannot show radar-triggered ingests on `/knowledge` at all.

### 3. Folder selector = native grouped `<select>`, list read from taxonomy YAML in TS

A new `dashboard/lib/taxonomy.ts` reads `configs/knowledge_taxonomy.yaml` and returns `{ path, scope }[]` (mirrors `lib/goals.ts` / `lib/wiki.ts` direct reads; the taxonomy file is the single source of truth shared with the backend classifier).

The selector is a **native HTML `<select>`**:
- First option is "auto-classify" with an empty value (the default); selecting it sends no category override.
- Remaining options are the taxonomy paths, grouped into `<optgroup>` by their top-level namespace (`investing`, `knowledge`, `opencraft`, `radar`) derived from the path prefix; the standalone `life` path (no `/`) sits ungrouped. Each option's `title` attribute carries the category `scope` text so hovering shows the description.

- *Why native `<select>` over a custom combobox:* only ~10 options in a shallow 2-level hierarchy for a single power-user who knows the taxonomy — a native control is zero custom code, fully keyboard/screen-reader accessible, and consistent with the 最简实现 rule. Scope hints ride along as option tooltips.
- *Alternative rejected (custom combobox with inline scope subtitles + typeahead):* nicer discoverability but ~40 lines of custom popover/filter logic that 10 static options don't justify. Revisit only if the taxonomy grows large or scope text needs to be always-visible.
- *Alternative rejected:* a `paca knowledge categories --json` CLI command — extra round-trip and a new command for a static list the dashboard can read directly. Reconsider only if the list ever becomes dynamic.

### 4. Stream lifecycle and result handling

The runner marks a job `done` when the child exits 0 with a final `ok:true` result, or `error` on a non-zero exit / `ok:false` final line (capturing stderr). The SSE feed emits the terminal job state to subscribers; the panel surfaces `markdown_path` / `category` / GBrain status on success (or the failing step on error) and triggers a tree refresh (router refresh / `revalidatePath("/knowledge")`) so the new doc appears in the sidebar.

## Risks / Trade-offs

- **Long-running job / first-token latency** (`uv run` cold start + fetch + 3 LLM steps can be tens of seconds) → progress events keep the panel responsive; the runner records a `running` job immediately so the card appears before the slow steps. No artificial timeout on the runner.
- **In-memory registry lost on dashboard restart** → accepted trade-off of the chosen model: the ingest child keeps running (not parented to a request) and its artifact write still completes, but the live progress view for in-flight jobs disappears after a restart. No persistence by design.
- **Single Node process assumption** → module-level `Map` + `EventEmitter` only work if start-action and stream-handler share one process; true for local `next start`, but dev HMR can reset module state mid-session. Acceptable for a local dashboard; documented so we don't debug "lost jobs" in dev as a bug.
- **stdout cleanliness (confirmed gotcha)** → `src/paca/core/logging.py` configures structlog with the default `PrintLoggerFactory`, which writes to **stdout**. So backend log lines can interleave with the `--progress` JSONL. Mitigation is mandatory, not optional: the runner splits on newlines and `try`-parses each line, **skipping any non-JSON line**; optionally `--progress` mode points structlog at stderr. Either keeps the event stream clean.
- **Unbounded registry growth** → finished jobs are kept in a small bounded recent list (drop oldest / after a TTL) so a long-lived dashboard process does not accumulate job records forever.
- **Invalid category from a stale UI** → validated up front against `category_paths()`; loud `RuntimeError` / non-zero exit surfaced as a job `error`, no silent fallback.
- **Partial failure mid-pipeline** (e.g. GBrain offline at persist) → the artifact is still on disk (existing invariant); the job's error names the failing step so the user knows the wiki file exists even though indexing failed.

## Migration Plan

Additive on the backend: new CLI flags default to current behavior (`--category` unset = classify, `--progress` off = single result line). New dashboard files: the job registry/runner lib, the SSE feed Route Handler, the form + active-ingests components. The only edit to existing dashboard behavior is `radar.ts::ingestToWiki` switching from `spawnPacaDetached` to the shared runner — same outcome (ingest fires, toast confirms), now also tracked. No DB or config migration. Rollback = revert the change; `paca knowledge ingest <url>` and the detached re-index are untouched.

## Open Questions

- Should the progress callback also stream sub-step detail (e.g. fetch adapter name, classify result) or just step status? Starting with step status + final result; richer detail can be added to the event payload later without changing the transport.
- Should a chosen folder be remembered as the default for the next ingest? Deferred — start stateless.
