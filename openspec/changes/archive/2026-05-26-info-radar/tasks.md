## 1. Recon (resolve open questions before coding)

- [x] 1.1 ~~Run `node $OPENCLI_BIN zhihu --help -f yaml`; pick subcommand.~~ **Deferred from v1**: opencli zhihu is Chrome-bridge driven, too heavy for v1 ops. Findings in design.md Appendix A. Architecture remains multi-source; opencli can be added later as a one-parser addition.
- [x] 1.2 Operator ran `folo login` (token at `~/.folo/config.json`, user Jin Fang); captured `timeline --limit 3` sample. Schema in design.md Appendix B. Key findings: pin `folocli@0.0.5` (npx cache resolves wrong version otherwise); entry shape has awkward double-nested `entries.entries.*` for the actual article; `nextCursor` available for future incremental pagination (v1 ignores per D7).

## 2. Database

- [x] 2.1 Add `radar_items` DDL (table + two indexes) to `scripts/bootstrap_db.py`.
- [x] 2.2 Run `uv run python scripts/bootstrap_db.py` against the local DB and verify the table + indexes exist (`\d radar_items` in psql).

## 3. Collector package skeleton

- [x] 3.1 Create `src/paca/collectors/__init__.py` and `src/paca/collectors/info_radar/__init__.py`.
- [x] 3.2 Add `src/paca/collectors/info_radar/schema.py` with the frozen `RadarItem` dataclass.
- [x] 3.3 Add `src/paca/collectors/info_radar/store.py`: `upsert_items(source, items)` using `INSERT ... ON CONFLICT DO NOTHING`; `sweep_expired()`; `query_recent(...)` / `query_unseen(...)` always AND-ing the 30-day window.
- [x] 3.4 Add `src/paca/collectors/info_radar/parsers/__init__.py` exporting `PARSERS: dict[str, ParserFn]`.

## 4. Integrations

- [x] 4.1 Add `src/paca/integrations/info_radar/__init__.py`.
- [x] 4.2 Add `src/paca/integrations/info_radar/folo.py` (default_argv + whoami helper for doctor).

## 5. Parsers

- [x] 5.1 Add `src/paca/collectors/info_radar/parsers/folo.py` with `folo_timeline(stdout, source_name)`. Validates `ok == true`; raises `RuntimeError` on schema surprise. Register in `PARSERS["folo_timeline"]`. Field mapping uses the schema captured in task 1.2.

## 6. Runner

- [x] 6.1 Add `src/paca/collectors/info_radar/loader.py`: load + validate `configs/info_radar/sources.yaml`, fail-fast on unknown parser. Architecture supports future `${...}` argv-template expansion (e.g., for opencli) but v1 only resolves literal argv.
- [x] 6.2 Add `src/paca/collectors/info_radar/runner.py`: `run_all(only: str | None = None) -> list[SourceResult]`. For each enabled source: subprocess.run with timeout, dispatch to parser, upsert, log structured result. Per-source failure isolation (D9). Best-effort `sweep_expired()` at the end.

## 7. Config

- [x] 7.1 Add `configs/info_radar/sources.yaml` with one folo entry (chosen in 1.2).
- [x] 7.2 Add `FOLO_TOKEN=` and `FOLO_CLI_ARGV=` (commented, defaults to `npx folocli@0.0.5`) to `.env.example`.

## 8. CLI

- [x] 8.1 Register `paca info-radar pull [--source NAME]` subcommand wiring through to `runner.run_all`. Prints per-source line `source: written=N skipped=K` and exits 1 only if every source errored.
- [x] 8.2 Register `paca info-radar sweep` subcommand calling `store.sweep_expired()` and printing the deleted count.
- [x] 8.3 Extend `paca doctor`: add `_check_folocli()` (verify `FOLO_TOKEN` env + `folocli whoami` returns `ok: true`).

## 9. Scheduler shell

- [x] 9.1 Add `src/paca/workflows/info_radar_pull.py` with a `run(**inputs)` function the scheduler invokes via `extra.run_now` (returns `{sources_run, items_written, items_skipped, errors, all_failed}`). A `factory()` stub satisfies `WorkflowConfig.factory` and raises if AgentOS ever tries to bind it. Spec wording referenced a class; the function form is what the scheduler actually calls. Documented in module docstring.
- [x] 9.2 Add `configs/workflows/info_radar_pull.yaml` with `factory` + `expose.agent_os: false` + `extra.run_now`; workflow loader picks it up (`paca list` shows it under Workflows).
- [x] 9.3 Add an `info_radar_pull` entry to `configs/schedules.yaml` at `{minute: 0}` (top of every hour); flipped to `enabled: true` after end-to-end verification.

## 10. Tests

- [x] 10.1 Add `tests/test_info_radar_parsers.py` — 7 cases covering happy path, summary fallback, missing fields, error envelope, non-JSON, malformed entries, schema validation.
- [x] 10.2 Add `tests/test_info_radar_store.py` — 4 DB-backed cases (skip if `DATABASE_URL` unset OR `radar_items` table missing): write, dedup, recent query, sweep.
- [x] 10.3 Add `tests/test_info_radar_runner.py` — 7 cases covering happy path, per-source failure isolation, all-failed detection, timeout isolation, parser error isolation, `--source` filter, disabled-source skip.
- [x] 10.4 Add `tests/test_info_radar_loader.py` — 7 cases covering valid load, unknown parser, argv_template rejection, unknown keys, duplicate names, missing file.

## 11. Docs

- [x] 11.1 Added paragraph to `CLAUDE.md` under "代码组织铁律" → "runnable / tools / integrations" introducing `paca/collectors/` with the judgment rule.
- [x] 11.2 Added "CLI-based 集成（folocli 等）" subsection to "外部集成模式" covering version pinning, token env-var auth priority, and the rule that agent/scheduler entry points live outside the integration module.

## 12. Verify end-to-end

- [x] 12.1 With folo login complete, `uv run paca info-radar pull` wrote 100 items to `radar_items` for the `folo_timeline_articles` source.
- [x] 12.2 Re-ran `uv run paca info-radar pull` immediately; output `written=0 skipped=100` — dedup confirmed.
- [x] 12.3 `uv run paca doctor` shows `✔ folocli  logged in as Jin Fang`; only ✗ is the pre-existing `ANTHROPIC_API_KEY` unrelated to this change.
- [x] 12.4 ~~`paca schedule install`~~ is stubbed pending the separate `launchd-scheduler` change. Surrogate verification: `paca schedule list` shows `info_radar_pull enabled`; `paca schedule run-now info_radar_pull` invokes the workflow shell and returns the proper summary (`{"sources_run": 1, "items_written": 3, ...}`). Launchd plist generation will be picked up by the `launchd-scheduler` change with no additional info-radar work.
- [x] 12.5 `uv run pytest -q` → **237 passed, 1 skipped** (212 baseline + 25 new info-radar tests; the skip is the existing `@integration` marker, not ours).
