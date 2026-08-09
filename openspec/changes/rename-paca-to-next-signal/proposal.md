## Why

The project is named `next-signal` everywhere it faces the outside world — the GitHub repo, the `pyproject` dist name, the Postgres database, the `~/.next-signal` state root, the dashboard brand marks. But the internal identifier layer is still `paca`: the Python package, the CLI binary, the `PACA_*` environment prefix, the dashboard cookies and subprocess launcher. A reader of the repo meets two names for one system, and every doc has to explain the mapping. This closes that gap while the project is still small and has one operator.

`dashboard-shell` currently carries an explicit requirement that the `paca` name **stay** in these positions; that requirement is being reversed here, deliberately and with the owner's decision on record.

## What Changes

- **BREAKING** — Python package `paca` → `next_signal`. `src/paca/` moves to `src/next_signal/`; every `from paca.…` import, dotted module string, and `configs/workflows/*.yaml` `factory:` / `run_now:` / `tool_fn:` value follows.
- **BREAKING** — CLI binary `paca` → `next-signal`. `uv run paca doctor` becomes `uv run next-signal doctor`, across all 10 subcommand groups. `pyproject.toml` gains the new console script and drops the old one; no alias is kept.
- **BREAKING** — the 13 `PACA_*` environment variables are renamed. Variables that belong to a domain lose the prefix entirely, matching the existing unprefixed `GBRAIN_BIN` / `FOLO_TOKEN` / `INFO_RADAR_TIMEZONE` convention; process-global variables take a `NEXT_SIGNAL_` prefix so generic names (`STATE_DIR`, `LOG_LEVEL`) cannot be shadowed by an unrelated process:
  - `PACA_WIKI_DIR` → `WIKI_DIR`; `PACA_WIKI_RAW_DIR` → `WIKI_RAW_DIR`; `PACA_GBRAIN_HOME` → `GBRAIN_HOME`; `PACA_GBRAIN_DATABASE_URL` → `GBRAIN_DATABASE_URL`; `PACA_WHISPER_MODEL` → `WHISPER_MODEL`; `PACA_YOUTUBE_TRANSCRIPT_LANGS` → `YOUTUBE_TRANSCRIPT_LANGS`
  - `PACA_STATE_DIR` → `NEXT_SIGNAL_STATE_DIR`; `PACA_AGENT_TMP_DIR` → `NEXT_SIGNAL_AGENT_TMP_DIR`; `PACA_LOG_LEVEL` → `NEXT_SIGNAL_LOG_LEVEL`; `PACA_DATABASE_URL` → `NEXT_SIGNAL_DATABASE_URL`
  - test-only sentinels `PACA_RUN_NETWORK_TESTS` / `PACA_TEST_VAR` / `PACA_NEVER_SET_THIS` → `NEXT_SIGNAL_*`
- **BREAKING** — dashboard cookies `paca_locale` → `ns_locale`, `paca_recap_collapsed` → `ns_recap_collapsed`. A short prefix is kept because cookies are not port-isolated: on `localhost` a bare `locale` would collide with any other local dev server.
- **BREAKING** — the default Postgres role in `docker-compose.yml` changes from `paca` to `next_signal`. `POSTGRES_USER` only takes effect at `initdb`, so an existing `pgdata` volume needs a one-time `ALTER ROLE`.
- Dashboard internals rename: `lib/actions/spawn-paca.ts` → `lib/actions/spawn-cli.ts`, `spawnPacaDetached` → `spawnCliDetached`, `PacaGlobal`/`pacaPgPool`/`pacaIngestJobs`/`pacaRadarAnalyze` → `AppGlobal`/`nsPgPool`/`nsIngestJobs`/`nsRadarAnalyze`, package name `paca-dashboard` → `next-signal-dashboard`, test tmpdir prefixes `paca-*` → `ns-*`.
- Documentation rename across both languages: `docs/` (16 files, EN + ZH), `README.md` + `README.zh-CN.md`, `dashboard/README.md` + `dashboard/README.zh-CN.md`, `CLAUDE.md`, and the three `.claude/skills/*/SKILL.md` files plus `.claude/launch.json`.
- Out of scope, deliberately: `openspec/changes/archive/**` (179 occurrences) stays untouched as a historical record of what was true at the time; the operator's external `digitalpaca-wiki` / `digitalpaca-wiki-raw` repositories keep their names, and the two prose references to them (`configs/knowledge_taxonomy.yaml`, `prompts/agents/knowledge_classifier.md`) are neutralised to "the wiki" rather than renamed.

No behaviour changes. Every rename is identifier-level; the pipelines, prompts, scoring, and data model are untouched.

## Capabilities

### New Capabilities

None. This change renames identifiers inside existing capabilities.

### Modified Capabilities

Every live spec names `paca` in normative text — as a CLI command an operator types, an environment variable they set, a YAML value the loader resolves, or a module path a requirement pins ("SHALL acquire the database via `paca.core.db.get_db()`"). All twenty therefore need a delta; leaving one out would leave it describing symbols that no longer exist.

- `core-cli`: every command requirement is named `paca <verb>`; all rename to `next-signal <verb>`
- `dashboard-shell`: the clause requiring the `paca` name to remain is **removed**; the shared subprocess launcher, the locale cookie, the wiki env var, and the README requirement rename
- `knowledge-pipeline`: `paca knowledge ingest` command plus the `PACA_WIKI_DIR` / `PACA_WIKI_RAW_DIR` resolution contract and workflow module paths
- `core-container-verification`: the model-free vs model-incurring command lists, and the `PATH`-resolution requirement that names the binary
- `info-radar-analysis`: `paca info-radar analyze`, the `paca doctor` goals check, and the `extra.run_now` YAML value
- `info-radar`: collector module paths and the `info_radar_pull` shell's `extra.run_now`
- `info-radar-recap`: implementation path `src/paca/workflows/info_radar_recap/` and the agent loader entry points
- `knowledge-review`: `paca knowledge review` and the `PACA_WIKI_DIR` misconfiguration guard
- `knowledge-reindex`: `paca run-workflow knowledge_ingest` and the `PACA_WIKI_DIR` walk root
- `dashboard-radar-reader`: `PACA_AGENT_TMP_DIR` staging plus the pull / analyze / recap / ingest command names
- `dashboard-knowledge-review`: `paca knowledge review` through the renamed launcher
- `dashboard-goals`: the `load_goals` schema-contract reference and `paca info-radar analyze`
- `dashboard-folo-subscriptions`: the folo integration module path and `uv run paca info-radar subscriptions --json`
- `core-agents`: `paca.agents.loader.build_from_name` and `paca run-agent`
- `core-agent-os`: `uv run paca serve`
- `core-database`: `paca.core.db.get_db()` / `database_url()` acquisition contract
- `core-integrations`: `src/paca/integrations/` layout, `_helpers.env` / `http_client`, `register_all`, `_MODULES`
- `core-models`: `paca.core.models.*` factory, `omlx_endpoint()`, `reset_cache()`, `get_embedder()`
- `core-tools`: `paca.registry` registration contract, `src/paca/tools/<domain>/`, `_json_extract`, `run_structured`
- `knowledge-search-tool`: `paca.tools.knowledge.search.search_knowledge` and its registration package

## Impact

**Code** — 197 files, 1304 occurrences in scope (1483 total minus 179 in the untouched archive). `src/` 208 hits across 56 files, `tests/` 135 across 49, `dashboard/` 116 across 28, `scripts/` 34 across 4, `configs/` 18 across 12.

**Docs** — `docs/` 387 hits across 16 files (EN and ZH must land in this same change), `openspec/specs/` 192 across 20, `CLAUDE.md` 69, `.claude/` 56, the four READMEs 32.

**Deployment** — `Dockerfile` `CMD`, `docker-compose.yml` (`command:`, the four `PACA_*` container env values, both bind-mount source variables, the Postgres role and healthcheck), `scripts/container_bootstrap.sh`, `.env.example`. The image must be rebuilt; `uv sync` must re-install the editable package under its new module name.

**Operator migration** — three manual steps that no script in the repo can do: edit the git-ignored `.env` (`PACA_LOG_LEVEL`, `PACA_WIKI_DIR`, `PACA_WIKI_RAW_DIR` are set there today), run `ALTER ROLE paca RENAME TO next_signal` against an existing `pgdata` volume, and accept that existing browser cookies go stale so the dashboard returns to its default locale and an expanded recap panel once.

**Not affected** — agno's session / memory / trace tables key on agent and workflow names, not module paths, so no database migration is needed there. `~/.next-signal/` and its `knowledge_ingest_manifest.json` keep their location.
