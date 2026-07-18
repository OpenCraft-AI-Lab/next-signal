## 1. DB schema

- [x] 1.1 Add `radar_analyses` DDL to `scripts/bootstrap_db.py` (per design §D7) including `UNIQUE(radar_item_id)` and the partial index on unpushed-novel-keep rows.
- [x] 1.2 Add `radar_pushed_topics` DDL (per design §D8) with `vector(1024)` and ivfflat cosine index.
- [x] 1.3 Run `uv run python scripts/bootstrap_db.py` against the dev DB and confirm both tables exist with the expected columns/indexes.

## 2. Config surfaces

- [x] 2.1 Add `configs/info_radar/goals.example.yaml` with one sample goal (commit), and document copying to `goals.yaml` in `docs/operations.md`.
- [x] 2.2 Add `configs/workflows/info_radar_analysis.yaml` (`expose.agent_os: false`, `extra.run_now: paca.workflows.info_radar_analysis:run`).
- [x] 2.3 Add an enabled `configs/schedules.yaml` entry `info_radar_analysis`. Seed cron with a reasonable default (e.g. `0 10,18 * * *`); cadence is operator-configurable and not a contract.
- [x] 2.4 Add an embedder profile (e.g., `embedder.local` with model `Qwen3-Embedding-0.6B-8bit`) to `configs/models.yaml`; document in `docs/architecture.md` briefly.

## 3. Goals loader

- [x] 3.1 Create `src/paca/workflows/info_radar_analysis/__init__.py` package skeleton.
- [x] 3.2 Create `src/paca/workflows/info_radar_analysis/goals.py`: `Goal` dataclass + `load_goals(path=None) -> list[Goal]`. Fail fast on missing file, empty list, unknown keys, duplicate names.
- [x] 3.3 Tests `tests/test_info_radar_analysis_goals.py`: valid file, missing file raises, empty list raises, duplicate names raise, unknown top-level keys raise.

## 4. Embedder helper

- [x] 4.1 Add `src/paca/core/models.py::get_embedder()` returning a callable `(text: str) -> list[float]` that POSTs to `OMLX_BASE_URL + /v1/embeddings` with the configured embedder profile model name. Read OMLX endpoint via existing `omlx_endpoint()`.
- [x] 4.2 Loud failure: connection error → `RuntimeError` (caller decides fallback).
- [x] 4.3 Tests `tests/test_get_embedder.py`: smoke test with monkeypatched httpx returning a 1024-element vector; failure path raises.

## 5. radar_analyses store

- [x] 5.1 Create `src/paca/workflows/info_radar_analysis/store.py`: short-lived psycopg helpers `fetch_unseen_items(limit, source) -> list[dict]`, `insert_analysis(...)` with `ON CONFLICT (radar_item_id) DO NOTHING`, `mark_seen(radar_item_id)`, `insert_topic(summary, embedding, item_id)`, `append_item_to_topic(topic_id, item_id)`, `ann_search_topics(embedding, k=5, threshold=0.40)`.
- [x] 5.2 Tests `tests/test_info_radar_analysis_store.py` against a real Postgres (skip if `DATABASE_URL` unset, same shape as `test_info_radar_store.py`): insert + idempotent re-insert, ANN search with a known-close and known-far vector, topic append.

## 6. Agents (configs + prompts)

- [x] 6.1 `configs/agents/radar_tier1_filter.yaml` + `prompts/agents/radar_tier1_filter.md`. Local model profile. `extra.db: false`. `output_schema`: `Tier1Verdict` pydantic class.
- [x] 6.2 `configs/agents/radar_tier2_impact.yaml` + `prompts/agents/radar_tier2_impact.md`. Default to a smarter model profile (local first). `extra.db: false`. `output_schema`: `Tier2Analysis` pydantic class.
- [x] 6.3 `configs/agents/radar_dedup_judge.yaml` + `prompts/agents/radar_dedup_judge.md`. Local model. `extra.db: false`. `output_schema`: `DedupVerdict` pydantic class.
- [x] 6.4 Add the three pydantic schemas in `src/paca/workflows/info_radar_analysis/schemas.py`.

## 7. folocli entry get integration

- [x] 7.1 Add `entry_get(source_id, *, timeout=60)` to `src/paca/integrations/info_radar/folo.py`. Validate `ok==true` envelope, return `data.entries` dict with `content` key. Loud `RuntimeError` on envelope mismatch.
- [x] 7.2 Tests `tests/test_folo_entry_get.py`: happy path, ok=false, timeout, missing content key.

## 8. YouTube subtitle helper (opportunistic)

- [x] 8.1 Create `src/paca/integrations/info_radar/youtube_subs.py::fetch_captions(url) -> str | None`. Try youtube-transcript-api first; if missing or rate-limited, fall back to yt-dlp `--write-auto-sub --skip-download --sub-format srv1 -o -`. Never raise — return `None` on any failure (logged once at WARN). NO audio transcription path.
- [x] 8.2 Add `youtube-transcript-api` as a dependency: `uv add youtube-transcript-api`. `yt-dlp` already used elsewhere if present; otherwise add `uv add yt-dlp`.
- [x] 8.3 Smoke test `tests/test_youtube_subs.py`: monkeypatch the captions client to return a known transcript; another test where captions raise → returns `None`.

## 9. Pipeline stages

- [x] 9.1 `src/paca/workflows/info_radar_analysis/stages/tier1.py::run(item, goals) -> Tier1Verdict`. Build prompt with goals + title + description, call agent via `build_from_name("radar_tier1_filter")`.
- [x] 9.2 `src/paca/workflows/info_radar_analysis/stages/fetch.py::run(item) -> tuple[str, str]` returning `(content, content_status)` — calls `folo.entry_get`, falls back to description on failure, opportunistically appends YouTube captions.
- [x] 9.3 `src/paca/workflows/info_radar_analysis/stages/tier2.py::run(item, content, goals) -> Tier2Analysis`. Same agent invocation pattern.
- [x] 9.4 `src/paca/workflows/info_radar_analysis/stages/dedup.py::run(summary) -> DedupOutcome` performing embed → ANN → judge agent (only when candidates present). Returns `{status: novel|duplicate, matched_topic_id?}`.

## 10. Workflow orchestration

- [x] 10.1 `src/paca/workflows/info_radar_analysis/__init__.py::run(*, limit=None, source=None) -> dict`. Load goals once, fetch unseen items, iterate. Per-item try/except wrap. Return counters dict.
- [x] 10.2 `src/paca/workflows/info_radar_analysis.py` thin shell module so `paca.workflows.info_radar_analysis:run` import path works (re-exports `run` from the package).
- [x] 10.3 Wire the workflow into the registry / config loader (mirror what `knowledge_ingest` and `info_radar_pull` do).
- [x] 10.4 Tests `tests/test_info_radar_analysis_runner.py` (mocks for all store + agent calls): one-tier1-drop, one-tier2-keep-novel, one-tier2-keep-duplicate, one-tier2-error-isolated, one-fetch-fallback. Verify counters and that `mark_seen` is called in each case.

## 11. CLI

- [x] 11.1 Add `analyze` subcommand to the existing `info_radar_app` Typer group in `src/paca/interfaces/cli.py`. Args `--limit`, `--source`. Print one-line counters summary.
- [x] 11.2 Add `_check_goals_yaml()` to `paca doctor` and include it in the doctor sweep.
- [x] 11.3 Tests in `tests/test_cli_info_radar_analyze.py` and extend `tests/test_cli_doctor.py` for the new goals check.

## 12. Docs

- [x] 12.1 `CLAUDE.md`: add `info-radar Analysis（当前默认）` block summarizing the pipeline, table names, schedule, goals.yaml location. Update the CLI list with `paca info-radar analyze`. Bump the test count.
- [x] 12.2 `docs/architecture.md`: add the analysis layer to the collector→analysis arrow; note `radar_analyses` and `radar_pushed_topics` in the business tables list.
- [x] 12.3 `docs/operations.md`: add the twice-daily schedule, the goals.yaml location, the embedder profile env requirements, and the doctor check.

## 13. End-to-end verification

- [ ] 13.1 Manual smoke: `uv run python scripts/bootstrap_db.py`, copy `goals.example.yaml` → `goals.yaml` with a real user goal, then `uv run paca info-radar pull` followed by `uv run paca info-radar analyze --limit 10`. Inspect `radar_analyses` rows and counters.
- [ ] 13.2 Run `paca doctor` — confirm the goals.yaml check shows OK.
- [ ] 13.3 `paca schedule run-now info_radar_analysis` to validate scheduler dispatch.
- [x] 13.4 Run full test suite: `uv run pytest -q`. All green.

## 14. Stretch (deferred unless requested)

- [ ] 14.1 `paca info-radar analyze --replay <radar_item_id>`: bypass tier-1 and re-run tier-2 on a specific item. Useful when tier-1 is suspected of false-dropping.
- [ ] 14.2 `paca info-radar topics list` to inspect `radar_pushed_topics` (audit memory).
- [x] 14.3 Batch tier-1 (design §D12): chunk items, send up to 10 per prompt with `Tier1Batch` schema, validate length + indices, fall back to per-item on chunk failure. New `Tier1Batch` / `Tier1Decision` schemas; tier1 stage exposes both `run_batch` and `run` (single = batch-of-1). Runner restructured into batched-tier1 + per-item-rest phases. New tests in `test_info_radar_analysis_tier1.py` plus 4 batch cases in `test_info_radar_analysis_runner.py`.
