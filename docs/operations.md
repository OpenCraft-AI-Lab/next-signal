# Operations & Troubleshooting

> **English** · [中文](./zh/operations.md)

## Installation

> **Containers are the recommended path** — see
> [`containerized-deployment.md`](./containerized-deployment.md), or the
> [README quick start](../README.md#quick-start-docker-compose). What follows is
> the host-native alternative, which is what you want if you need the local OMLX
> model in-process.

```bash
brew install uv
brew install --cask postgres-app          # or brew install postgresql@16
uv sync
cp .env.example .env && $EDITOR .env       # at minimum DATABASE_URL + one LLM key
createdb next_signal
uv run python scripts/bootstrap_db.py
uv run paca doctor
uv run paca serve                          # → http://localhost:7777
uv run paca dashboard                      # → http://localhost:3000
```

## Required and optional services

Required for a minimal working setup: Postgres 16+ with pgvector, an
OpenAI-compatible OMLX endpoint, and the GBrain CLI (required for knowledge
search).

Optional: folocli auth (the info-radar collector), a GitHub token (knowledge's
GitHub bookmarking — anonymous access is capped at 60 req/h), and OpenCLI
(WeChat article ingest).

The Dashboard is a separate Next.js process and does not require `paca serve` to
be running alongside it: its server actions spawn one-shot `paca` CLI children,
and data pages read Postgres directly.

## Environment variables

Key values in the repo-local `.env`:

- `DATABASE_URL`
- `OMLX_BASE_URL` / `OMLX_API_KEY`
- Cloud model / API keys, as needed
- `GBRAIN_BIN` (when `gbrain` is not on `PATH`; the dashboard and backend resolve
  it the same way)
- `PACA_WIKI_DIR` / `PACA_WIKI_RAW_DIR` (**required**, no code default — when
  missing, the knowledge pipeline and the dashboard wiki view fail loud)
- `PACA_STATE_DIR` / `PACA_AGENT_TMP_DIR` (optional, for tests or alternate paths)

Never read these directly from an arbitrary module — go through the corresponding
core/helper function. The complete key list is in `.env.example`.

| Integration | Env var |
|---|---|
| LLM: Anthropic / OpenAI / Google / DeepSeek | `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` / `DEEPSEEK_API_KEY` (plus optional `DEEPSEEK_BASE_URL`, default `https://api.deepseek.com`) |
| Folo (info-radar) | `FOLO_TOKEN` (optional; falls back to `~/.folo/config.json`) plus optional `FOLO_CLI_ARGV` to override the default `npx --yes folocli@<v>` |
| GBrain / OpenCLI (knowledge) | `GBRAIN_BIN` (when `gbrain` is not on `PATH`) / `OPENCLI_BIN` (WeChat download — path to `main.js` or a wrapper) |
| GitHub (knowledge bookmarking) | `GITHUB_TOKEN` (optional; anonymous is 60 req/h) |
| OMLX embedder (info-radar analysis dedup) | `OMLX_BASE_URL` must be reachable; `configs/models.yaml::embedders.local.model_id` defaults to `Qwen3-Embedding-0.6B-8bit` (1024-dim) and the OMLX server must have that model loaded |

Every cloud integration checks its key at call time. A missing key fails only the
corresponding tool — it never blocks startup.

## Where state lives

- Project repo: configs, prompts, code, tests, OpenSpec specs.
- User state (`~/.next-signal/`): `knowledge_ingest_manifest.json`, `agent-tmp/`.
- Knowledge base: `~/Projects/digitalpaca-wiki/` (clean) and
  `~/Projects/digitalpaca-wiki-raw/` (raw) — these paths come from
  `PACA_WIKI_DIR` / `PACA_WIKI_RAW_DIR`, they are not hardcoded defaults.
- agno-managed tables (sessions / memory / knowledge / traces): local Postgres +
  pgvector.
- Logs: stdout only (structlog — console rendering on a TTY, JSON otherwise).
  `~/Library/Logs/next-signal/` is created, but nothing currently writes files
  there.

Under Docker Compose these map to the `pstate` volume and the wiki bind mounts
instead — see [`containerized-deployment.md`](./containerized-deployment.md).

## Health check

```bash
uv run paca doctor                            # host-native
docker compose exec dashboard paca doctor     # in the container
```

It checks `DATABASE_URL`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`,
`OMLX_BASE_URL`, Postgres reachability, configured agents, registered tools, the
GBrain CLI/service (`gbrain doctor --fast`), folocli auth (`folocli whoami` —
either `FOLO_TOKEN` or `~/.folo/config.json` is enough), and that info-radar's
`configs/info_radar/goals.yaml` exists and parses (without it,
`paca info-radar analyze` raises a loud `RuntimeError`).

The code does **not** distinguish "required" from "optional" checks — **any**
failure exits non-zero, including the folocli auth listed as optional above. The
required/optional split above only means "if this machine will not use that
feature, you can ignore its ✗".

A missing `DEEPSEEK_API_KEY` counts as a failure — the default fallback profile
for `local*` uses DeepSeek when OMLX is unreachable. A missing
`ANTHROPIC_API_KEY` counts too, since the `claude_*` profiles need it. If you
deliberately run local-only, understand that those cloud fallbacks will fail.

In a cloud-only container, OMLX (and Anthropic, if unset) showing ✗ is expected —
confirm Postgres, agents, and tools are ✔ and treat the rest as informational.

## Common commands

```bash
uv run paca list                                     # list agents / workflows
uv run paca doctor                                   # self-check
uv run paca run-agent <name> "<prompt>"              # one-shot agent call
uv run paca serve [--port 7777]                       # start AgentOS
uv run paca dashboard [--port 3000]                   # start the Next.js dashboard
uv run paca dashboard --build                         # dashboard production build
uv run paca dashboard --start                         # start an already-built dashboard
uv run paca knowledge ingest <url|staged-file>        # ingest into the knowledge base
#   --category <taxonomy-path>   pick the destination folder, skipping auto-classification
#   --progress                   emit one JSON event per step (used by the dashboard progress panel)
uv run paca knowledge gbrain-search "query"           # search the local GBrain
uv run paca knowledge gbrain-ingest <file|dir>        # import markdown into GBrain
uv run paca info-radar pull [--source NAME]           # run each source CLI, write radar_items
uv run paca info-radar sweep                          # delete radar_items rows older than 30 days
uv run paca info-radar analyze [--limit N] [--source NAME]
                                                      # run the two-tier analysis pipeline → radar_analyses
                                                      # manual trigger only (CLI / dashboard); no background scheduler
                                                      # `seen_at` keeps reruns idempotent at any cadence
                                                      # prerequisite: configs/info_radar/goals.yaml must exist
                                                      # (cp configs/info_radar/goals.example.yaml configs/info_radar/goals.yaml, then edit)
uv run paca info-radar subscriptions --json           # read Folo subscriptions as stable JSON lines
uv run paca info-radar recap --since D --until D [--min-score N] [--novel-only] [--regenerate]
                                                      # synthesize a date range of kept signals into
                                                      # themed narratives (cached per range + gate)
uv run paca run-workflow knowledge_ingest             # manual wiki → GBrain re-ingest
```

The Dashboard UI defaults to **English** and can be switched to Chinese from the
nav bar; the choice is stored in the `paca_locale` cookie. Only interface copy is
translated — article titles, analysis summaries, tags, and YAML content render
as stored.

For a full-chain test that touches a real GBrain index, use an isolated PGLite
brain:

```bash
uv run paca knowledge init-test-gbrain
PACA_GBRAIN_HOME=state/test-gbrain uv run paca doctor
```

`PACA_GBRAIN_HOME` is the parent directory; GBrain stores its config and
`brain.pglite` under `$PACA_GBRAIN_HOME/.gbrain/`. Keep it inside the ignored
`state/` directory and leave the production `~/.gbrain` alone.

## Troubleshooting

- **`DATABASE_URL not set`** → copy `.env.example` to `.env` and fill it in.
- **Postgres unreachable** → start Postgres.app or the Homebrew service, then
  rerun `paca doctor`.
- **An OMLX profile fell back to DeepSeek** → check `OMLX_BASE_URL` /
  `OMLX_API_KEY` and the endpoint's `/v1/models`. Once OMLX is back, a
  long-running process must call `paca.core.models.reset_cache()` before it
  retries local.
- **GBrain search / re-index fails** → run `paca doctor` and
  `gbrain doctor --fast`. When embedding fails, ingest should fail loud *after*
  writing the wiki artifact, leaving the manifest un-advanced; fix the cause and
  rerun `paca run-workflow knowledge_ingest`.
- **Dashboard won't start** → confirm `pnpm` is on `PATH`, then use
  `uv run paca dashboard --build` to surface Next.js compile errors. The
  dashboard does not need `paca serve`, but `/radar` needs Postgres,
  `/knowledge` needs the GBrain CLI, and `/subscriptions` needs Folo auth.
- **knowledge ingest rejects a local file** → local file input must be staged
  under `PACA_AGENT_TMP_DIR`. The dashboard's `/radar` Folo ingest stages the
  full text from `folocli entry get` into `PACA_AGENT_TMP_DIR/radar-ingest/`
  automatically; non-Folo radar items still require a valid `radar_items.url`.
- **An agent can't see a tool** → check that the tool is registered
  (`_IN_TREE_TOOLS`, `tools/<domain>.register()`, workflow tool exposure, or
  integration registration), that the agent YAML uses the exact registered name,
  and run `tests/test_registry.py`.
- **Container-specific issues** (build failures, volume mapping, the cloud-only
  embedder gap) → see
  [`containerized-deployment.md`](./containerized-deployment.md) §7–§8.
