## 1. Rewriter

- [x] 1.1 Add `scripts/rename_paca.py` implementing the ordered transform from design.md: sentence deletions, then `PACA_*` env mapping, then literal identifier renames (dashboard symbols, cookies, tmpdir prefixes, packaging names, Postgres role, `` `paca` `` → `` `next-signal` ``), then `(?<![A-Za-z])paca\.` → `next_signal.`, then `(?<![A-Za-z])paca/` → `next_signal/`, then the CLI rule `(?<![A-Za-z/_-])paca(?=\s+(doctor|list|serve|dashboard|run-agent|run-workflow|knowledge|info-radar|…))` → `next-signal`, then a final case-sensitive bare-word pass for prose. Default to dry-run; `--write` applies. **The script is a throwaway migration tool — deleted once the rename verified clean (task 9.7), so it cannot be re-run against a renamed tree or drift into dead code.**
- [x] 1.2 Give the script a `--report` mode that prints every line still matching `(?<![A-Za-z])paca` after the transform, so an unclassified occurrence is visible rather than silently left behind.
- [x] 1.3 Hardcode the exclusion list — `.git`, `node_modules`, `.next`, `.venv`, `state`, `__pycache__`, the script itself, and **all** of `openspec/` — and assert the archive is untouched at the end of every run. `openspec/` is excluded wholesale, not just the archive: the change's own planning artifacts deliberately hold both names, and `openspec/specs/` must keep its old requirement headers until `/opsx:archive` applies the RENAMED deltas.
- [x] 1.4 Verify on a dry run that the script rewrites 176 files (1121 occurrences) with exactly one unclassified leftover — the dead `PACA.scoreHue` reference, left case-sensitively for task 5.6.

## 2. Environment variables

- [x] 2.1 Run the rewriter's env-only pass over `src/`, `tests/`, `scripts/`, `dashboard/`, `configs/`, `docs/`, `README.md`, `README.zh-CN.md`, `.env.example`, `docker-compose.yml`, `Dockerfile`.
- [x] 2.2 Rename the GBrain helper's local names in `src/paca/integrations/gbrain.py`: parameter `paca_home` → `gbrain_home`, `paca_url` → `gbrain_url`, and the `paca_home_to_gbrain_home` mapping helper.
- [x] 2.3 Update `.env.example` comments so each renamed variable's explanation still matches (the `NEXT_SIGNAL_STATE_DIR` default note, the `GBRAIN_HOME` dual-purpose note, the wiki-path block).
- [x] 2.4 Verify: `grep -rn "PACA_" . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=.venv` returns hits only under `openspec/` — the archive, this change's own artifacts, and `openspec/specs/`, which keeps the old names until the deltas are applied at archive time.

## 3. Python package

- [x] 3.1 `git mv src/paca src/next_signal`, then delete the stale `src/next_signal/**/__pycache__` directories so old bytecode cannot mask a broken import.
- [x] 3.2 Run the rewriter's module pass over `src/`, `tests/`, `scripts/`, `configs/` — imports, dotted module strings (`"paca.os_app:app"`, `__import__(f"paca.tools.…")`, monkeypatch targets), and the `factory:` / `run_now:` / `tool_fn:` values in the five `configs/workflows/*.yaml` files.
- [x] 3.3 Update `pyproject.toml`: `[tool.uv.build-backend] module-name = "next_signal"` and `[project.scripts] next-signal = "next_signal.interfaces.cli:app"` replacing the `paca` entry.
- [x] 3.4 Run `uv sync` to reinstall the editable package under the new module name and drop the stale `.venv/bin/paca` entry point.
- [x] 3.5 Verify: `uv run pytest -q` is green, matching the pre-change baseline (all passing plus the usual `@pytest.mark.integration` skips).
- [x] 3.6 Verify: `uv run next-signal list` prints agents / workflows / teams — this resolves every workflow `factory:` from YAML, which `pytest` does not exercise.

## 4. CLI name

- [x] 4.1 Run the rewriter's CLI pass over `src/`, `tests/`, `scripts/`, `configs/`, `dashboard/`, `Dockerfile`, `docker-compose.yml`, `.claude/launch.json`.
- [x] 4.2 Hand-check the occurrences the CLI rule cannot match by pattern: the `interfaces/cli.py` module docstring, the `logTag` default in the dashboard launcher, `Dockerfile` `CMD`, the compose `command:` entry, and `.claude/launch.json`'s `runtimeArgs` + config `name`.
- [x] 4.3 Verify: `uv run next-signal doctor` runs and reports the same three known ✗ checks as before the rename — no new failure, no changed check.

## 5. Dashboard

- [x] 5.1 `git mv dashboard/lib/actions/spawn-paca.ts dashboard/lib/actions/spawn-cli.ts` and update the three importers (`lib/actions/knowledge.ts`, `recap.ts`, `review.ts`).
- [x] 5.2 Rename the exported symbol `spawnPacaDetached` → `spawnCliDetached` and the `globalThis` keys `PacaGlobal` / `pacaPgPool` / `pacaIngestJobs` / `pacaRadarAnalyze` → `AppGlobal` / `nsPgPool` / `nsIngestJobs` / `nsRadarAnalyze`.
- [x] 5.3 Rename the cookie constants: `LOCALE_COOKIE` value `paca_locale` → `ns_locale` in `lib/i18n/dictionaries.ts`, and `RECAP_COLLAPSED_COOKIE` value `paca_recap_collapsed` → `ns_recap_collapsed` in `lib/radar/recap-ui.ts`.
- [x] 5.4 Set `dashboard/package.json` `"name"` to `next-signal-dashboard`.
- [x] 5.5 Rename the temp-directory prefixes: `paca-goals-` / `paca-wiki-` / `paca-taxonomy-` in the three `lib/*.test.ts` suites, and the Chrome `--user-data-dir` `paca-radar-chrome` in `app/api/radar/export/route.ts`.
- [x] 5.6 Fix the stale `lib/score.ts` comment referencing `dashboard/design/data.js::PACA.scoreHue` — that file no longer exists, so point it at the live source of the hue scale or drop the reference.
- [x] 5.7 `rm -rf dashboard/.next`, then verify `pnpm build` succeeds and the `lib/goals.test.ts`, `lib/taxonomy.test.ts`, `lib/wiki.test.ts` suites pass against the renamed env vars.

## 6. Deployment

- [x] 6.1 Update `docker-compose.yml`: the `POSTGRES_USER` / `POSTGRES_PASSWORD` defaults `paca` → `next_signal`, both `DATABASE_URL` and `GBRAIN_DATABASE_URL` interpolations, the `pg_isready` healthcheck, the renamed container env keys, the two bind-mount source variables, the `command:` entry, and the three explanatory comments.
- [x] 6.2 Update `Dockerfile` (`CMD`, the editable-install and PATH comments) and `scripts/container_bootstrap.sh` (`GBRAIN_DATABASE_URL` / `GBRAIN_HOME` reads plus its comments).
- [x] 6.3 Document the `ALTER ROLE paca RENAME TO next_signal;` migration for an existing `pgdata` volume in `docs/containerized-deployment.md` and `docs/zh/containerized-deployment.md`.

## 7. Documentation

- [x] 7.1 Run the rewriter over `docs/` (all 16 files, EN and ZH together), `README.md`, `README.zh-CN.md`, `dashboard/README.md`, `dashboard/README.zh-CN.md`.
- [x] 7.2 Run the rewriter over `CLAUDE.md` and the three `.claude/skills/*/SKILL.md` files (`code-review`, `docker-verify`, `radar-prompt-tuning`).
- [x] 7.3 Add the operator migration steps to `docs/operations.md` and `docs/zh/operations.md`: edit the git-ignored `.env` (it sets `PACA_LOG_LEVEL`, `PACA_WIKI_DIR`, `PACA_WIKI_RAW_DIR` today), run the `ALTER ROLE`, and expect the dashboard locale and recap panel to reset once as the old cookies go stale.
- [x] 7.4 Neutralise the two prose references to the operator's external wiki repo — `configs/knowledge_taxonomy.yaml` line 1 and `prompts/agents/knowledge_classifier.md` line 1 — to "the wiki" / "知识库" without renaming those repositories.
- [x] 7.5 Verify: for each of the 16 `docs/` files, the EN and ZH members of the pair changed together — no file renamed on one side only.

## 8. Live specs

- [x] 8.1 Confirm `openspec validate rename-paca-to-next-signal --strict` still passes after implementation.
- [x] 8.2 Edit the two non-requirement lines directly in `openspec/specs/` — the `core-cli` header line and the `core-integrations` header paragraph — since no delta operation can express content outside a requirement block. Done ahead of archive; the RENAMED `FROM:` headers are untouched, so all 16 still resolve.
- [x] 8.3 Update `openspec/config.yaml`: the project description's "(Python package `paca`)" clause, the four `src/paca/…` path references, and the `uv run paca ...` convention line.

## 9. Full verification

- [x] 9.1 Verify: every surviving `paca` token is accounted for — `openspec/changes/archive/` (179, historical), this change's own artifacts (156, hold both names by design), `openspec/specs/` (188, renamed when the deltas are applied at archive time), the migration tables in the four operations/deployment docs (44, intentional). Plus `digitalpaca-wiki*`, the operator's external repos.
- [x] 9.2 Verify: `uv run pytest -q` green and `uv run ruff check src` clean.
- [x] 9.3 Rebuild the container image — `docker compose build` — because `/app` is baked into the image, not bind-mounted, so an un-rebuilt container would verify stale code.
- [x] 9.4 Verify in-container, model-free: `docker compose exec dashboard next-signal doctor` and `docker compose exec dashboard next-signal info-radar pull`.
- [x] 9.5 Verify the dashboard renders `/radar` and `/knowledge` against the running stack, and that the language toggle writes the new `ns_locale` cookie.
- [x] 9.6 Update the `avoid-paca-name` memory note: the "don't retroactively rename existing paca surfaces" guidance is superseded by this change.
- [x] 9.7 Delete `scripts/rename_paca.py` once the leftover report is clean. It is one-shot, already applied, and its transform is documented in design.md — keeping it in `scripts/` would leave a tool that silently damages the migration guides if anyone re-ran it.

## 10. Regression tests

Mutation testing after the rename landed — reintroduce `paca` at one site, run the
suite, see whether it goes red — found 18 of 28 rename surfaces with no test behind
them. `tests/test_shipped_refs.py` closes the ones where the failure is both silent
and unrecoverable-by-retry. Every task below was verified by re-running the same
mutation and confirming the new test fails.

- [x] 10.1 Resolve every shipped workflow's `factory` / `extra.run_now` / `extra.tool_fn` ref. Only `knowledge_ingest` had cover, and only incidentally — it is the one workflow exposed as an agent tool, so the registry tests resolve it. The other four are `expose.agent_os: false` thin shells that expose nothing, which is exactly why nothing reached them, and exactly the CLI and dashboard entry points an operator actually invokes. This is the risk design.md recorded with a manual `next-signal list` gate; the gate is now automatic.
- [x] 10.2 Load every shipped agent config and resolve its prompt file. Six of ten were covered by accident; the radar agents' tests `monkeypatch` `build_from_name` to a dummy, so their real YAML was never read. Uses `load_agent`, not `build_from_name` — the latter resolves a model profile and raises without provider keys, which would make the suite depend on the operator's `.env`.
- [x] 10.3 Guard both parametrized sweeps against an empty glob, which would make them vacuously pass.
- [x] 10.4 Check the `uvicorn.run(...)` target in `cli.py` and the `[project.scripts]` target in `pyproject.toml` name real modules. Both are strings nothing resolves until `next-signal serve` or the console script runs. Uses `importlib.util.find_spec` rather than importing — `os_app` builds the whole runtime on import and loads `.env`.
- [x] 10.5 Assert every `process.env.*` the dashboard reads has a counterpart in `src/next_signal/`, with a documented allowlist for the four dashboard-only vars. `NEXT_SIGNAL_STATE_DIR`, `NEXT_SIGNAL_AGENT_TMP_DIR`, and `WIKI_DIR` are hardcoded independently in both runtimes with only a doc comment claiming they mirror; renaming one side alone points the dashboard and the pipeline at different directories with no error. Catches drift in either direction.
