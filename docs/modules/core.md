# Module: core (framework chassis)

> **English** · [中文](../zh/modules/core.md)

## What it solves

The infrastructure every runnable shares: the model factory and its fallback
chain, database connections, shared context, and per-provider concurrency.
Understand this layer before touching any business module — the agents, tables,
and embeddings of both product modules ([knowledge](./knowledge.md) and
[info_filter](./info_filter.md)) run on top of it.

## Where the code lives

- `src/paca/core/models.py` — model factory (profile → agno Model) + embedder +
  OMLX endpoint
- `src/paca/core/config.py` — every YAML loader (strict pydantic; unknown keys
  fail loud)
- `src/paca/core/db.py` — `database_url()` plus the `get_db()` singleton for
  agno-managed tables
- `src/paca/core/context.py` — shared-context assembly
- `src/paca/core/concurrency.py` — per-provider inference concurrency semaphores
- `src/paca/core/paths.py` / `logging.py` / `fileio.py` — path conventions /
  structlog / atomic writes

## The model system

`configs/models.yaml` is the single source of truth. Agent YAML references models
by profile name; Python never constructs `Claude(...)` or `OpenAILike(...)`
directly.

| Profile | Provider / model | Used for |
|---|---|---|
| `local` | OMLX Qwen3.5-122B (max_tokens 32768) | Default: conversation, writing, research |
| `local_structured` | Same model, **max_tokens 4096** | Structured-output (`output_schema`) agents only |
| `deepseek_smart` | deepseek-v4-flash | Fallback target for `local` (when OMLX is unreachable) |
| `deepseek_structured` | deepseek-v4-flash (max_tokens 4096) | Fallback target for `local_structured` |
| `claude_smart` | claude-sonnet | Backup cloud profile |
| `claude_fast` | claude-haiku | Lightweight cloud tasks |

- **Do not loosen the tight cap on `local_structured`.** xgrammar constrained
  decoding occasionally loops pathologically until it hits the cap; 4096 turns a
  10-minute hang into a clean ~100s failure that each pipeline's per-item error
  isolation can absorb. Loosening it was tried, did not help, and the conclusion
  is recorded in the `configs/models.yaml` comments.
- **The fallback chain:** a `RuntimeError` while building a provider (typically
  an unreachable OMLX endpoint) automatically rebuilds against
  `fallback_profile`. `KeyError` / `ValueError` are programmer errors — they
  propagate instead of falling back. The result is lru-cached, so **once OMLX is
  back you must call `paca.core.models.reset_cache()` before local is retried** —
  this matters most for long-running processes like `paca serve`.
- The OMLX endpoint is read only through `paca.core.models.omlx_endpoint()`
  (`OMLX_BASE_URL` / `OMLX_API_KEY`). Never duplicate that lookup elsewhere.
- Qwen3 specifics are pinned in `_build_omlx`: thinking disabled, sampling
  parameters, and structured output through the standard OpenAI
  `response_format` json_schema (xgrammar constrained decoding on the OMLX side).
  agno's native structured outputs stay off.
- DeepSeek goes through `_build_deepseek`: OpenAI-compatible
  (`DEEPSEEK_API_KEY` plus optional `DEEPSEEK_BASE_URL`, default
  `https://api.deepseek.com`), but it supports only `response_format`
  json_object, not json_schema — so the schema is passed through the prompt and
  `run_structured` parses, validates, and repairs the result.
- **The embedder** (`models.yaml::embedders.local`): Qwen3-Embedding-0.6B-8bit,
  **1024 dimensions**, matching the `vector(1024)` column on
  `radar_pushed_topics.embedding`. Switching to a model with different
  dimensions requires a column migration.

## Concurrency

`models.yaml::concurrency` gives each provider a ceiling (`omlx: 2` — one local
GPU; the cloud values of 64/32 only guard against runaway loops). Every model the
factory produces has its `response` / `aresponse` and both streaming entrypoints
wrapped in that provider's semaphore. Embedder calls draw on the same quota,
because the local LLM and embedding contend for one GPU. Everything built through
the factory inherits this automatically — no module manages it locally.

## Two database paths

Pick by purpose; never mix them:

- **agno-managed tables** (sessions / memory / knowledge / traces) → the
  `paca.core.db.get_db()` singleton. The URL goes through
  `database_url(for_sqlalchemy=True)`, which rewrites the scheme to
  `postgresql+psycopg://` (psycopg v3). agno provisions these tables itself —
  never redefine them.
- **Our business tables** (`radar_items` / `radar_analyses` /
  `radar_pushed_topics`) → bare short-lived synchronous connections via
  `psycopg.connect(database_url())`. DDL is centralized in
  `scripts/bootstrap_db.py`; runtime reads and writes live in the corresponding
  module's store or tool.

## Shared context

Files in `prompts/_shared/*.md` are concatenated in filename order (two-digit
prefixes control ordering: `00_house_rules.md`, `10_user_profile.md`), separated
by markdown rules, and prepended to **every agent's** instructions
(`paca.core.context.shared_context()`).

- `_*.md` prefix: **not loaded** and not committed — pure scratch.
- `99_*.md`: **loaded** (sorted last) but gitignored — a local personal layer that
  takes effect on your machine and leaves no trace in the repo.
- Read once at import and cached; the dashboard's hot-reload path calls
  `reload()`.
- An individual agent opts out with `extra: {shared_context: false}` in its YAML.
  Pure transformation and verdict agents all opt out, and also set
  `extra: {db: false}` so no session store is created.

## Invariants

- `core` imports nothing from a layer above it (tools / integrations / workflows
  / agents).
- Env is always read at call time, never at import time — a missing key must not
  block startup.
- Failures are loud: missing config or a broken endpoint raises `RuntimeError`
  rather than silently defaulting.
- Telemetry is fully off: `AgentOS(telemetry=False)`, and a directly constructed
  `Agent` needs `telemetry=False` too.

A full inventory of agents and tools is deliberately not maintained in the docs:
`uv run paca list` lists the runnables, and `src/paca/registry.py` plus each
`tools/<domain>/register()` is the source of truth for the tool surface.

## Specs

[`openspec/specs/core-models/`](../../openspec/specs/core-models/),
`core-database`, `core-agents`, `core-tools`, `core-integrations`,
`core-agent-os`, `core-cli`.

State directories and log locations are covered in the
[operations guide](../operations.md#where-state-lives).
