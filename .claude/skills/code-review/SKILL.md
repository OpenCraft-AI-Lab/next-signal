---
name: code-review
description: Code review for the next-signal (paca) project. Two modes — light (review the current diff and flag docs that need syncing) and full (audit the whole project for bugs, convention violations, and docs/code drift). Use this skill whenever the user asks to review code, review changes, review a diff / branch / PR, check work before committing or merging, audit the project, verify the code follows project conventions, or check whether docs and code are still consistent — even if they do not say the word "review" explicitly.
license: MIT
metadata:
  author: paca
  version: "1.0"
---

# Code review (paca)

Review code against `next-signal`'s own conventions, not generic
best practice. The value of this skill is that it knows *this* project: the
layering rules, the config-driven design, and which docs must move when code
moves. A review that just says "looks fine" is a failed review — find the real
problems or confirm specifically why there are none.

Write the final report in the language the user is using (this project's
maintainer works in Chinese; match that unless they switched to English).

## Pick the mode

- **light** — review only the current change (uncommitted edits, or the branch
  diff vs `main`). Fast. Catches problems in the diff and flags every doc that
  the change made stale. This is the default.
- **full** — audit the whole project: obvious bugs, convention adherence across
  all of `src/`, docs/code consistency, and orphaned files/modules.

Decide from the request and the skill args:
- args or request mention `light` / `轻` / "just my changes" / "before commit" → light
- args or request mention `full` / `完整` / "whole project" / "audit" → full
- nothing specified and there is a non-empty diff → light
- nothing specified and the working tree is clean → ask which mode they want

---

## Mode: light

Scope is the current change. Do not review unrelated code — if you spot
something off outside the diff, mention it in one line under "Out of scope",
do not fix it (surgical-edit rule).

1. **Establish the diff.** Run `git status`, `git diff HEAD`, and
   `git diff main...HEAD` (if on a feature branch). Decide what set of changes
   is under review and state it.
2. **Read every changed file in full** — not just the hunks. A diff hunk hides
   the surrounding function; orphaned imports, broken invariants, and
   inconsistent neighbors only show up with the whole file in view.
3. **Run the change against the [convention checklist](#convention-checklist).**
   Every line of the diff should trace to the user's intent — flag anything that
   looks like scope creep, drive-by reformatting, or speculative abstraction.
   If the diff touches `integrations/` — or adds `subprocess`, SQL, or
   file-path handling anywhere — the [Security](#security) group is mandatory,
   not optional. That is where a quiet mistake turns into an exploit.
4. **Doc sync.** For each changed area, walk the [doc-sync map](#doc-sync-map)
   and check whether the matching human/agent doc still describes reality. This
   is the part that gets forgotten — be thorough here.
5. **Verify.** If code changed, run `uv run pytest -q` (and `uv run ruff check
   src` if ruff is configured). If `openspec/` changed, run `uv run openspec
   validate --all`. Report pass/fail with numbers.
6. **Report** using the [output format](#output-format).

Use a subagent only if the diff is large (say >15 files): spawn one `Explore`
agent for the doc-sync sweep while you read the code. For a small diff, inline
is faster and higher quality.

---

## Mode: full

Audit the whole project. This is broad — parallelize with subagents so each
gets a focused remit and a clean context window, then synthesize yourself.
Spawn these in one batch (use `Explore` or `general-purpose`):

- **Architecture agent** — verify the dependency direction holds (`interfaces /
  api → orchestrator / workflows / teams / agents → tools →
  integrations → core`, no reverse imports), that every module sits in the
  right layer, and that `tools` vs `integrations` vs `core` placement follows
  responsibility, not call-convenience.
- **Docs agent** — check `docs/` (architecture, development, operations, the
  `docs/modules/*.md`) and `CLAUDE.md` against the actual code: stale paths,
  wrong tool/agent names, drifted counts, instructions that no longer match.
- **OpenSpec agent** — check `openspec/specs/`, `openspec/changes/`, and
  `openspec/project.md`: do specs reference paths that still exist, do change
  deltas map to real capabilities, are spec names internally consistent.
- **Orphan agent** — find dead files (committed artifacts, stale progress
  notes), modules nothing imports, configs with no matching prompt/factory, and
  stale references to moved/deleted code.
- **Security agent** — apply the [Security](#security) checklist group to every
  file under `integrations/` and `tools/`, plus `scripts/bootstrap_db.py` and
  any `subprocess` use. This is the project's attack surface — give it a
  dedicated pass, do not let it ride along inside the architecture review.
- **Code-quality agent** — read `src/paca/` for obvious bugs plus the
  Concurrency & async, Database, Tests, and Encoding & i18n checklist groups:
  unbounded LLM fan-out, blocking calls on async paths, DB access that bypasses
  the right connection path, business-table changes the bootstrap DDL never
  tracked, happy-path-only tests, non-ASCII handling that can collide or
  mojibake.
- **Config & prompt agent** — read `configs/` and `prompts/` for the Config vs
  code and Prompt & config quality groups: behavior hardcoded in Python that
  should be YAML, a `tools:` list that disagrees with the prompt, a wrong model
  profile, prompts that contradict the shared context.

Brief each agent with the relevant parts of the [convention
checklist](#convention-checklist) and tell it to report a punch list of
`path → problem`, not a vague essay.

Then yourself:
- Run `uv run pytest -q`, `uv run ruff check src`, `uv run openspec validate
  --all`. Report the numbers.
- Synthesize the agent reports — dedupe, drop false positives by checking the
  actual files, and rank by severity.
- Report using the [output format](#output-format).

Trust but verify: an agent's summary is what it *intended* to find. Spot-check
its claims against the real files before putting them in the report.

---

## Convention checklist

This is the bar. Each item is a rule from `CLAUDE.md` / `docs/`; a review
checks the code against it. When something violates a rule, cite the rule.

### Layering & placement
- Dependency direction is strictly downward; no reverse imports. `core` imports
  nothing from upper layers. `integrations` never imports `tools` / agents.
- `integrations/` = low-level external adapters (HTTP/CLI/auth, provider
  response → stable dict), not directly agent-facing. `tools/` = agent-facing
  business actions. `core/` = system-wide infrastructure only — a domain-local
  helper does not belong in `core`.
- Domain code groups under `tools/<domain>/` and `integrations/<domain>/`;
  cross-cutting code sits flat. Workflows live in `workflows/`, never inside a
  domain tool folder; workflow-private stages go in `workflows/stages/<wf>/`.
- Placement is by responsibility, not by what is convenient to import.

### Config vs code
- Agent / workflow / team tunables (model profile, instructions, tool list,
  temperature) live in `configs/*.yaml`. Python only defines the *shape*
  (loaders, factories, schema). No hardcoded model IDs, instructions, or tool
  lists in Python — including throwaway `Agent(...)` inside a tool/workflow.
- Every `configs/{agents,workflows,teams}/<name>.yaml` has `name:` equal to its
  file stem (snake_case). Prompts live in `prompts/<kind>/<name>.md`, not inline
  in YAML (unless very short).

### Prompt & config quality

In a config-driven project the YAML + `prompts/*.md` *are* the behavior —
review them as carefully as code.

- The `tools:` list in an agent YAML matches what its prompt actually asks the
  agent to do — no tool the prompt never mentions, no action the prompt demands
  without a tool to do it.
- The `model_profile` fits the job: a local profile for routine / transform
  work, cloud only where it is justified. A DB-free transform or verifier agent
  sets `extra: {db: false}`; one that should not inherit house rules sets
  `extra: {shared_context: false}`.
- Prompt instructions are unambiguous and do not contradict the shared context
  in `prompts/_shared/`.
- A new agent followed the full flow — YAML + prompt file + registered tools —
  not a throwaway `Agent(...)` hardcoded somewhere in Python.

### Integrations & tools
- API keys are read at *call time* via `env(NAME)`, never at import time —
  a missing key must not block startup.
- HTTP goes through `http_client()` (30s timeout built in), not raw
  `requests` / `httpx`. Return values pass through `to_jsonable()`; long text
  through `truncate()`.
- No side effects or network calls at module import time.
- Tool functions use a full `<integration>_<verb>` / `<domain>_<verb>` name
  (`finnhub_fetch_news`, not `fetch_news`) so the LLM does not misroute.
- A new tool is registered explicitly — in `registry.py::_IN_TREE_TOOLS`
  (cross-cutting) or a `tools/<domain>/register()` hook (domain).

### Security

`integrations/` is the attack surface: it makes outbound HTTP / CLI calls,
often with agent- or user-supplied input (URLs to ingest, search queries,
tickers, file paths). Scrutinize every change here — and any `subprocess`,
SQL, or path handling elsewhere — against:

- **Secrets** — API keys read via `env()` at call time; never interpolated
  into a URL path/query, never logged, never placed in an error message or a
  returned dict. Auth belongs in a header, not the URL.
- **Command injection** — `subprocess` calls (GBrain bridge, bilibili
  transcription) pass args as a list and never use `shell=True` with
  interpolated input. External / agent input is never concatenated into a
  shell string.
- **SSRF & URL building** — when a URL or host originates from agent/user
  input, it is validated against the expected provider, not blindly fetched.
  Provider base URLs stay constants; only documented path/params are templated.
- **Path traversal** — file paths derived from titles, slugs, or wiki-relative
  paths cannot escape the intended directory (`../`, absolute paths). The
  knowledge slug logic must stay collision-safe for non-ASCII input.
- **Untrusted content** — provider responses and fetched article/file content
  are data, not instructions. Run them through `to_jsonable()` / `truncate()`;
  fetched text must not silently become part of a tool's control flow.
- **Unsafe parsing** — external data is parsed with `yaml.safe_load` / `json`,
  never `yaml.load`, `eval`, `exec`, or `pickle`.
- **SQL** — business-table queries (raw `psycopg`) are parameterized; no
  f-string or `%`-formatted SQL containing external values.
- **Transport** — all HTTP goes through `http_client()` so the timeout is
  enforced; no raw `requests` / `httpx` that skips it.
- **New dependency** — a new `pyproject.toml` entry is justified, reputable,
  and added via `uv add` (supply-chain surface).

### Concurrency & async
- LLM calls respect the per-provider concurrency caps in `configs/models.yaml`
  (`paca.core.concurrency`); OMLX is capped low because it is a single local
  box. No unbounded fan-out — a loop issuing one LLM call per item must go
  through the concurrency limiter.
- `async` code does not block the event loop with sync I/O (raw `requests`,
  blocking DB calls, `time.sleep`).
- After OMLX recovers, the model cache needs `paca.core.models.reset_cache()`
  to retry it — a long-lived process that pinned the cloud fallback must not
  stay stuck there.

### Database
- agno-managed tables (sessions / memory / knowledge / traces) go through the
  `paca.core.db.get_db()` singleton — never a hand-rolled `PostgresDb(...)`,
  and never redefine tables agno provisions itself.
- Business tables (`radar_items`, `radar_analyses`, `radar_pushed_topics`) use
  short-lived `psycopg.connect(database_url())`. If their shape changes, the DDL
  in `scripts/bootstrap_db.py` changes with it.

### Encoding & i18n
- This project ingests Chinese content (WeChat, Bilibili) and writes a wiki
  tree with non-ASCII paths. JSON that a human or a non-ASCII pipeline reads is
  dumped with `ensure_ascii=False`; files are read/written as UTF-8 explicitly.
- A slug derived from a non-ASCII title or path carries a stable hash suffix so
  two different titles cannot collide onto one GBrain page.

### Error handling
- Fail loud. Missing config / broken OMLX endpoint → `RuntimeError`. No silent
  defaults, no "defensive" code for scenarios that cannot happen.
- Isolation where it is intended: one bad agent YAML / one bad integration
  module must not take down the rest (the loaders already try/except — do not
  remove that).

### Tests
- No mock-heavy unit tests; prefer `tmp_path` + `monkeypatch` + real function
  calls. Tests must not touch the production DB / external APIs / real browser
  login state.
- Tests needing OMLX or an external API are `@pytest.mark.integration` and skip
  by default.
- A new tool / integration ships with at least a smoke test.
- A test earns its place by exercising real risk, not just the happy path —
  edge cases, malformed input, the failure mode the code claims to handle.
  `tests/test_json_extract.py` (12 cases reverse-engineered from production
  failures) is the bar to aim for.
- When a change fixes a bug, there is a test that fails without the fix.

### Surgical change discipline
- Every diff line traces to the stated task. No drive-by reformatting of
  neighboring code, no refactoring code that is not broken, no speculative
  abstraction or half-finished features.
- Unrelated dead code is *flagged*, not deleted. Orphans the change itself
  created (unused imports / vars / functions) *are* cleaned up.

### Misc
- agno telemetry is off — `AgentOS(telemetry=False)` and every directly
  constructed `Agent(..., telemetry=False)`.
- Docstrings are one line. No multi-paragraph docstrings or comment blocks.
- Comments explain *why* only when non-obvious; no what-comments, no
  task/PR/caller references in comments.
- Never log a whole dict (token-leak risk). Never commit `.env` / `state/` /
  `chrome-profile/`.
- Python always via `uv` (`uv run ...`). `uv.lock` is never hand-edited.

---

## Doc-sync map

When the change touches the left column, check the right column is still
accurate. This is the core of light mode — code and docs drift silently.

| Changed in the diff | Docs / specs to check |
|---|---|
| Added/removed/renamed a tool or integration | `CLAUDE.md` tool lists, `docs/modules/<domain>.md` tool tables, the relevant `register()` |
| New module, moved file, new directory under `src/paca/` | `docs/architecture.md` code-layer diagram, `CLAUDE.md` 代码组织铁律 |
| `configs/agents|workflows|teams/*.yaml` added/changed | `docs/modules/*.md` agent tables, `docs/development.md` runnable section |
| New/removed capability, or a behavior change that makes an existing `openspec/specs/` description stale | a matching delta under `openspec/changes/`. If the change was made directly (not via opsx), the diff/PR needs a one-line justification for why it was trivial enough to skip a change — a bare "no delta" is not enough. See CLAUDE.md's OpenSpec slash aliases section for the trivial/non-trivial line. |
| New/changed CLI subcommand | `docs/operations.md` 常用命令, `CLAUDE.md` CLI 子命令 list |
| Test count changed materially | `CLAUDE.md` "当前 N 个 test 全过" |
| New env var / external service | `.env.example`, `docs/operations.md` 环境变量 table |
| New dependency | `pyproject.toml` (via `uv add`) — confirm it was not hand-edited |

A doc-sync finding is not optional cleanup — list it as a required follow-up.

---

## Output format

Keep it scannable. Lead with the verdict, then concrete findings with file
references (`path:line`), then doc sync, then verification results.

```
## Code review — <light: current diff | full: project audit>

<one-sentence verdict: is this good to commit/merge, or are there blockers>

### Blockers
<things that must change — bugs, convention violations that break a 铁律.
 each: path:line — what is wrong — which rule. omit the section if none.>

### Suggestions
<non-blocking improvements. omit if none.>

### Doc sync
<docs/specs the change made stale, with the exact edit needed.
 omit if nothing drifted.>

### Verification
<pytest / ruff / openspec validate results with numbers.>

### Out of scope
<one line each for unrelated issues noticed but deliberately not touched.
 omit if none.>
```

Rules for the report:
- Distinguish **blocker** (must fix) from **suggestion** (judgment call) — do
  not inflate nits into blockers.
- Every finding cites a file location and, for a convention violation, the rule
  it breaks. "This feels off" is not a finding.
- If the change is genuinely clean, say so plainly and show the verification
  numbers — do not invent problems to look thorough.
- Do not fix anything in this skill's flow unless the user explicitly asked for
  "review and fix". Review reports; fixing is a separate, confirmed step.
