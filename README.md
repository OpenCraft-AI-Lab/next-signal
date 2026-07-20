# next-signal

> **English** · [简体中文](./README.zh-CN.md)

A local-first info-radar + knowledge framework built on
[agno](https://github.com/agno-agi/agno). The Python package is named `paca`.

One runnable-orchestrator chassis plus capability building blocks. A single
AgentOS process hosts every agent and workflow; the CLI drives the same set of
capabilities through a centralized runnable loader, and the Dashboard is a
separate Next.js process (it reads Postgres directly or spawns one-shot `paca`
CLI children). State lives in a local Postgres + pgvector. Local models via
OMLX (Qwen3) come first, with cloud models as an explicit fallback.

## Quick start (Docker Compose)

**Containers are the supported way to run next-signal.** The whole stack —
Postgres + pgvector, schema bootstrap, and the dashboard — comes up with one
command, and the container image already bundles the peer CLIs (`gbrain`,
`opencli`, `folocli`) so there is nothing else to install.

```bash
git clone https://github.com/OpenCraft-AI-Lab/next-signal.git
cd next-signal
cp .env.example .env && $EDITOR .env   # see "Minimum .env" below
docker compose up --build              # postgres + bootstrap + dashboard
```

Then open <http://localhost:3000>.

**Minimum `.env`** — the build fails fast without these:

| Key | Why |
|---|---|
| One cloud LLM key: `DEEPSEEK_API_KEY` (primary), or `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | Containers cannot reach Apple Metal, so the cloud path is the default |
| `PACA_WIKI_DIR` | Host path of your clean wiki repo — bind-mounted read-write |
| `PACA_WIKI_RAW_DIR` | Host path of your raw archive repo — bind-mounted read-write |

`DATABASE_URL` and the in-container wiki/state paths are set by
`docker-compose.yml`; do not override them in `.env`.

Everyday container commands:

```bash
docker compose up -d                          # start detached
docker compose exec dashboard paca doctor     # self-check inside the container
docker compose exec dashboard paca list       # list agents / workflows
docker compose run --rm dashboard paca info-radar pull
docker compose logs -f dashboard              # tail the dashboard
docker compose down                           # stop, keep pgdata/pstate volumes
```

> Run any end-to-end verification through the container, not on the host — that
> keeps the verification environment identical to what actually ships. Full
> design, volume and env-var mapping:
> [docs/containerized-deployment.md](./docs/containerized-deployment.md).

**Optional — local LLM.** OMLX/MLX needs the Metal GPU and therefore **cannot be
containerized**. The cloud fallback covers chat, but the *embedder* is
OMLX-only, so `paca info-radar analyze` dedup needs it. Run an OMLX server on
the host and point the container at it:

```bash
OMLX_BASE_URL=http://host.docker.internal:<port>/v1   # in .env
```

**Host-native setup** (no Docker; required if you want the local model in-process)
is the alternative path — see [docs/operations.md](./docs/operations.md#installation).

## Common commands

Inside the container, drop the `uv run` prefix (`paca` is already on `PATH`).

```bash
uv run paca list                                     # list agents / workflows
uv run paca doctor                                   # check env / Postgres / OMLX / tools / GBrain
uv run paca run-agent <name> "<prompt>"              # one-shot agent call
uv run paca serve [--port 7777]                       # start AgentOS
uv run paca dashboard [--port 3000]                   # start the dashboard
uv run paca knowledge ingest <url|staged-file>        # ingest into the knowledge base
uv run paca info-radar pull [--source NAME]           # pull sources into radar_items
uv run paca info-radar analyze [--limit N]            # two-tier analysis pipeline
uv run paca run-workflow knowledge_ingest             # wiki → GBrain re-ingest
uv run pytest -q                                      # tests
```

## Documentation map

| You want to… | Read |
|---|---|
| Understand how the system is built, and why | [docs/architecture.md](./docs/architecture.md) |
| Add an agent / tool / integration / model / domain | [docs/development.md](./docs/development.md) |
| Install, configure env, run `paca doctor`, troubleshoot | [docs/operations.md](./docs/operations.md) |
| Deploy in containers (Docker Compose, cloud LLM) | [docs/containerized-deployment.md](./docs/containerized-deployment.md) |
| Go deep on one area | [docs/modules/](./docs/modules/): [core](./docs/modules/core.md) · [knowledge](./docs/modules/knowledge.md) · [info_filter](./docs/modules/info_filter.md) · [dashboard](./docs/modules/dashboard.md) |
| Read capability contracts / pending changes | [openspec/specs/](./openspec/specs/) · [openspec/changes/](./openspec/changes/) |

Active domains: `knowledge` (knowledge management) and `info_filter`
(info-radar). Domain capabilities live in `src/paca/tools/<domain>/` and
`src/paca/integrations/<domain>/`; workflows are centralized in
`src/paca/workflows/`.

### Docs are bilingual

English is canonical and lives at the paths above. The Chinese translation
mirrors it under [`docs/zh/`](./docs/zh/), plus
[`README.zh-CN.md`](./README.zh-CN.md) and
[`dashboard/README.zh-CN.md`](./dashboard/README.zh-CN.md); every page carries a
switcher link at the top. Every human-facing doc exists in both languages, and
both sides change in the same commit.

Not translated, deliberately: `CLAUDE.md` (agent instructions, Chinese-only) and
`openspec/specs/` (capability contracts, English-only). Both churn with the code,
where a second copy would drift rather than help.

## Related projects

- [`garrytan/gbrain`](https://github.com/garrytan/gbrain) — the long-term
  knowledge-base peer service: markdown-first, pgvector hybrid search,
  automatic typed-link graph, and an MCP server.
