# Development Guide

> **English** · [中文](./zh/development.md)

## Default workflow

Non-trivial capability work goes through OpenSpec:

1. Create or pick a change under `openspec/changes/`.
2. Write or update `proposal.md`, the delta specs, and `tasks.md`.
3. Validate with `openspec validate --all`.
4. Implement task by task, ticking each one off as you verify it.
5. When done, `openspec archive <name>` merges the deltas into `openspec/specs/`.

Slash aliases (`.claude/commands/opsx/`): `/opsx:explore`, `/opsx:propose`,
`/opsx:apply`, `/opsx:archive`.

## Toolchain

Always go through `uv` — never bare `python` / `pip` / `pytest`:

```bash
uv sync                 # sync dependencies (after editing pyproject)
uv run paca <cmd>        # run the CLI
uv run pytest -q         # tests
uv run ruff check src    # lint
uv add <pkg>             # add a dependency (writes pyproject + uv.lock)
```

Never hand-edit `uv.lock`.

## Adding an agent

1. Write `configs/agents/<name>.yaml`. The file stem **must** equal the YAML
   `name:` field (snake_case).
2. Put instruction text in `prompts/agents/<name>.md` (unless it is very short).
3. Reference models by profile name (`configs/models.yaml`) and tools by
   registered name.
4. Restart `paca serve`, or smoke-test with `paca run-agent <name> "..."`.

```yaml
name: knowledge_frontmatter
model_profile: local_structured
tools: []
instructions_file: agents/knowledge_frontmatter.md
markdown: false
add_history_to_context: false
extra: { db: false, shared_context: false }
```

Production agents never hardcode a model or instructions in Python. A pure
transformation or verifier agent can set `extra: {db: false}` (no session store)
and `extra: {shared_context: false}` (does not inherit shared context).

## Runnable configuration

Agents, workflows, and teams are all runnables, and their config is the
repo-local source of truth:

```text
configs/agents/<name>.yaml
configs/workflows/<name>.yaml
configs/teams/<name>.yaml
```

Shared rules:

- `name:` must equal the filename stem.
- `kind:` is one of `agent` / `workflow` / `team`.
- `enabled: false` keeps the config but excludes it from the runtime.
- Use only the JSON-compatible subset of YAML, so a future frontend can edit it
  as a JSON object and the backend can write YAML back.
- Store prompt *paths*, never long prompt bodies, in YAML.

Python code only defines loaders, factories, and schemas. Adding an ordinary
agent requires no Python; only workflows and complex teams need a factory.

## Adding a tool

A tool is a business action an agent can call directly.

- **Cross-cutting tool** (useful in any domain, e.g. GBrain search) →
  `src/paca/tools/`, plus one line in `paca/registry.py::_IN_TREE_TOOLS`.
- **Domain tool** → `src/paca/tools/<domain>/`, registered via
  `registry.register(...)` inside that package's `register()`.

Name tools with an `<integration>_<verb>` or `<domain>_<verb>` prefix
(`gbrain_search`). Generic names like `search` or `fetch` confuse LLM routing.
Keep the docstring to one line.

## Adding an integration

An integration is a low-level API or CLI adapter for an external provider.

- **Generic provider** (any domain might use it) → `src/paca/integrations/`,
  plus one line in `_MODULES` in `integrations/__init__.py`.
- **Domain provider** → `src/paca/integrations/<domain>/`, called by that
  domain's tools or by a workflow stage.

```python
from agno.tools import tool
from paca.integrations._helpers import env, http_client, to_jsonable

@tool(show_result=False)
def provider_action(query: str) -> dict:
    """One-line LLM-visible docstring."""
    with http_client(headers={"Authorization": f"Bearer {env('PROVIDER_API_KEY')}"}) as c:
        r = c.get("https://api.example.com/search", params={"q": query})
        r.raise_for_status()
    return to_jsonable(r.json())

def register(registry) -> None:
    registry.register("provider_action", provider_action)
```

Only implement `register()` and add to `_MODULES` when the integration is itself
an agent-facing capability. Ordinary domain adapters are not registered for
agents directly — a tool or workflow stage calls them.

Hard rules: read API keys at **call time** with `env()`, never at import time;
route HTTP through `http_client()`; pass return values through `to_jsonable()`;
pass long text through `truncate()`; no side effects at module top level.

## Adding a workflow

Multi-step, schedulable work that needs observability or resumability belongs in
a workflow. Workflows are centralized in `src/paca/workflows/` and declared by
`configs/workflows/<name>.yaml`.

```yaml
name: knowledge_ingest
kind: workflow
enabled: true
factory: paca.workflows.knowledge_ingest:build
expose:
  agent_os: true
  tool:
    enabled: true
    name: knowledge_ingest_workflow
extra:
  run_now: paca.workflows.knowledge_ingest:run
```

**Not implemented yet:** simple linear workflows that just chain agents, with no
custom artifact / retry / file-write semantics, are planned to be declarable
directly via a YAML `steps:` key. Today `WorkflowConfig` is a strict schema
(`extra="forbid"`) with no `steps` field — a YAML that writes `steps:` fails
validation. To build one, first extend the centralized loader and
`WorkflowConfig` with a `steps:` builder.

Helpers and stages private to one workflow go in
`src/paca/workflows/stages/<workflow>/`. An action reusable by several workflows
or agents gets promoted to `tools/` or `integrations/`.

A workflow has exactly one implementation; `expose` decides whether it reaches
AgentOS or the agent tool surface:

- `expose.agent_os: true` → `paca.os_app` registers it with AgentOS via the
  centralized loader.
- `expose.tool.enabled: true` → `paca.orchestrator.workflow_tools` registers a
  `WorkflowTools` toolkit; agent YAML references that tool name.
- `extra.run_now` → the function `paca run-workflow <name>` calls for a manual
  run. Not every workflow needs to support it.

Never write a second `tools/<domain>/workflow_tools.py` wrapper for a workflow
that already exists.

## Adding a team

Teams are runnables too. A simple team is just `configs/teams/<name>.yaml`; only
complex routing justifies a `src/paca/teams/<name>.py` factory. No team ships
today — `configs/teams/` is empty and `list_teams()` correctly returns an empty
list. This layer only matters once you add a team-shaped direction.

```yaml
name: <team_name>
kind: team
enabled: true
mode: route
members:
  - <agent_a>
  - <agent_b>
instructions_file: teams/<team_name>.md
factory: paca.teams.<team_name>:build
```

When starting a new product direction, prefer adding a domain directory over a
`modules/` layer: `src/paca/tools/<domain>/`,
`src/paca/integrations/<domain>/`, and where needed
`src/paca/workflows/<name>.py` plus `configs/{agents,workflows,teams}/`.

## Configuration conventions

- Every tunable parameter lives in YAML under `configs/`; Python defines only the
  schema and the loader.
- Pydantic strict models reject unknown keys, so typos fail loud.
- YAML `name:` stays aligned with the file stem.
- No secrets in YAML; no duplicated `.env` parsing across modules.

## Testing

```bash
uv run pytest -q
```

- No mock-heavy unit tests — prefer `tmp_path` + `monkeypatch` + real function
  calls.
- Unit tests never touch production local services, the DB, external APIs, or a
  real browser session.
- Integration tests that need OMLX or an external API use
  `@pytest.mark.integration` and skip by default.
- Every new tool or integration gets at least one smoke test.
- Touching the registry means running `tests/test_registry.py`; touching
  `tools/_json_extract.py` means running `tests/test_json_extract.py`.

Run any **runtime or end-to-end** verification (the CLI, the dashboard, a full
pipeline, anything touching Postgres / gbrain / folocli) through Docker rather
than bare on the host, so the verification environment matches what ships:

```bash
docker compose build
docker compose up
docker compose exec dashboard paca doctor
docker compose run --rm dashboard paca run-workflow knowledge_ingest
```

See [containerized-deployment.md](./containerized-deployment.md) for the full
design and the volume / env-var mapping.

## Documentation

Docs are bilingual, and **English is canonical**. English pages live at
`README.md`, `docs/`, and `dashboard/README.md`; the Chinese mirror lives at
`README.zh-CN.md`, `docs/zh/`, and `dashboard/README.zh-CN.md`. Every page opens
with a switcher link to its counterpart.

**Every human-facing doc exists in both languages.** When you change one, update
the other in the same change — a one-sided edit is an unfinished one.

Two things are deliberately not translated: `CLAUDE.md` (agent instructions,
Chinese-only) and `openspec/specs/` (capability contracts, English-only). Both
change with the code often enough that a second copy would drift rather than help.

## Commits

- Only commit when the user asks for it.
- Reference the OpenSpec change's task, or the spec capability name, in the message.
- Never amend; never `--no-verify`.
- Never commit `.env`, `state/`, generated caches, or secrets.
