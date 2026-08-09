# Module: core (framework chassis)

> **English** · [中文](../zh/modules/core.md)

## What it solves

The infrastructure every runnable shares: the model factory and its fallback
chain, database connections, shared context, and per-provider concurrency.
Understand this layer before touching any business module — the agents, tables,
and embeddings of both product modules ([knowledge](./knowledge.md) and
[info_filter](./info_filter.md)) run on top of it.

## Where the code lives

- `src/next_signal/core/models.py` — model factory (profile → agno Model) + embedder +
  OMLX endpoint
- `src/next_signal/core/config.py` — every YAML loader (strict pydantic; unknown keys
  fail loud)
- `src/next_signal/core/db.py` — `database_url()` plus the `get_db()` singleton for
  agno-managed tables
- `src/next_signal/core/context.py` — shared-context assembly
- `src/next_signal/core/concurrency.py` — per-provider inference concurrency semaphores
- `src/next_signal/core/paths.py` / `logging.py` / `fileio.py` — path conventions /
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
  back you must call `next_signal.core.models.reset_cache()` before local is retried** —
  this matters most for long-running processes like `next-signal serve`.
- The OMLX endpoint is read only through `next_signal.core.models.omlx_endpoint()`
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
- **DeepSeek thinking mode defaults to on (effort "high")** as of the
  deepseek-v4-flash/-pro API — reasoning tokens bill as normal output tokens,
  so leaving it unset is silently slower and pricier. Tune per profile via
  `extra.reasoning_effort` (`"low"`/`"high"`/`"max"`, forwarded straight to the
  request body) or disable thinking entirely via
  `extra.extra_body.thinking.type: disabled`. `deepseek_smart` sets
  `reasoning_effort: low`; `deepseek_structured` disables thinking outright —
  with its 4096 max_tokens cap, default high-effort reasoning could exhaust the
  budget before ever emitting the JSON answer.
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
  `next_signal.core.db.get_db()` singleton. The URL goes through
  `database_url(for_sqlalchemy=True)`, which rewrites the scheme to
  `postgresql+psycopg://` (psycopg v3). agno provisions these tables itself —
  never redefine them.
- **Our business tables** (`radar_items` / `radar_analyses` /
  `radar_pushed_topics` / `radar_recaps` / `knowledge_reviews`) → bare short-lived synchronous connections via
  `psycopg.connect(database_url())`. DDL is centralized in
  `scripts/bootstrap_db.py`; runtime reads and writes live in the corresponding
  module's store or tool.

## Shared context

Files in `prompts/_shared/*.md` are concatenated in filename order (two-digit
prefixes control ordering: `00_house_rules.md`, `10_user_profile.md`), separated
by markdown rules, and **appended** to every agent's instructions
(`next_signal.core.context.shared_context()`).

- `_*.md` prefix: **not loaded** and not committed — pure scratch.
- `99_*.md`: **loaded** (sorted last) but gitignored — a local personal layer that
  takes effect on your machine and leaves no trace in the repo.
- Read once at import and cached; the dashboard's hot-reload path calls
  `reload()`.
- An individual agent opts out with `extra: {shared_context: false}` in its YAML.
  Pure transformation and verdict agents all opt out, and also set
  `extra: {db: false}` so no session store is created.

The agent's own instructions come first and the shared block trails as a
qualifier, so it cannot outrank the field contract an agent is judged against.
Note this is the opposite of where the language rule belongs — see below.

## Output language

Every agent that writes **prose** for a reader declares a language *policy*
in its own YAML (`extra.output_language`), resolved by `next_signal.core.language`:

- `off` — no language rule at all (a bare `false` still means this too, for
  back-compat). For agents that write no prose: output discarded
  (`radar_dedup_judge`), or an identifier rather than prose
  (`knowledge_classifier`, whose only output is a taxonomy path copied verbatim
  from its input). Not inert prompt cost — dropping the rule from
  `knowledge_classifier` measurably shifted borderline filing (see
  [knowledge.md](./knowledge.md#output-language)), so `off` is a behavioural
  choice, not just a saving.
- `global` — resolves from the live preference file (`~/.next-signal/language.json`,
  `content_language`), falling back to a hardcoded `"en"` if that file doesn't
  exist. Never reads `.env` — the retired `SIGNAL_OUTPUT_LANG` mechanism. The
  dashboard's **settings panel** writes this file (the nav's language picker does
  not — that one is UI chrome only); a container-start hook seeds it if missing.
  This is the policy for everything written *for the reader*: the three
  info-radar agents whose prose is displayed (`radar_tier1_filter`,
  `radar_tier2_impact`, `radar_recap` — `radar_dedup_judge` is `off`), plus the
  two frontmatter agents whose `title`/`summary` are an artifact's index entry.
- `same_as_source` — resolves from a caller-supplied `language=` override, not
  from any global setting. The caller (a workflow stage) must supply it or the
  agent build raises `RuntimeError`. Used by exactly two agents, the knowledge
  body cleaners: the target is the *article's own* language, detected once per
  item by `next_signal.core.language_detect.detect_language()` — a deterministic,
  non-LLM, Unicode-script-ratio heuristic, never an LLM call (an LLM judging
  its own target language reintroduces the exact sampling-variance failure
  this mechanism exists to prevent).
- `fixed:<lang>` — a literal, unconditional target, ignoring both the
  preference file and any override.

Mechanics that carry over unchanged from the single-env-var mechanism this
generalizes:

- Resolved at call time (never cached), so a changed preference file takes
  effect on the next agent build with no `reload()`.
- Delivery is two-way. A prompt that declares `{{OUTPUT_LANGUAGE}}` gets the
  language *name* substituted in place by `language_name()`, keeping the rule
  where its author put it so the prompt's own closers (`Return JSON`,
  `Do NOT pad`) still land last. A prompt with no token gets
  `language_rule()`'s block appended after the shared context instead.
- Appending after a prompt's closers was measured and rejected: on the 55-item
  holdout set it raised `impact` output ~31% and truncations 2/165 → 7/165
  against the `max_tokens` cap. Prefer migrating a prompt to the token.
- A prompt declaring the token while its YAML sets `output_language: off`
  raises `RuntimeError` — otherwise the literal token reaches the model.
- Gated independently of `shared_context`. Every production agent opts out of
  shared context and still needs the language rule; coupling them would force
  the house-rules block on structured-output agents.
- Identifier fields are exempt: `tags` stay lowercase English in every
  language — not via this mechanism, but via a bespoke, field-specific prompt
  instruction in the two frontmatter agents, because `_normalize_tags`
  silently drops any tag containing CJK. A field-specific *injected* clause
  was tried and measured worse (35% longer output, truncations 1/65 → 6/65),
  so this mechanism only ever expresses one target language per call — a
  field needing to diverge stays a prompt-level exception, not a policy knob.
- The line between the two policies is **what the output is**, not which module
  it belongs to. `knowledge_artifact_editor`/`knowledge_github_cleaner` emit the
  article body itself — the wiki's only copy of the source text — so they use
  `same_as_source` and are never translated, but are still targeted explicitly
  rather than left to the model's default behavior. Their frontmatter
  counterparts on the *same item* use `global`, because `title`/`summary` are
  generated prose the reader browses, not archived text. A wiki file may
  therefore be bilingual: an English index entry over a Chinese body. That is
  intended, and mirrors the radar reader, which already shows a translated
  title above a source-language article. `radar_dedup_judge` stays `off`: its
  `reason` is never stored or rendered.
- The rule is phrased unconditionally on purpose — a conditional
  ("if the goals are in Chinese…") measured 0/64 on tier-2 summaries against
  Chinese goals with English articles, while the unconditional form measured
  63/63.
- Two readers, two failure modes, on purpose: `next_signal.core.language` raises on a
  corrupt or unrecognized preference file, because a pipeline run must not
  generate in a language nobody chose. The dashboard's own reader
  (`lib/actions/language.ts::getContentLanguage`) logs and falls back to its
  default instead — the nav renders on every page, so raising there would take
  down the whole dashboard including the panel used to fix the value.
  `next-signal doctor` remains the single loud check.

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
`uv run next-signal list` lists the runnables, and `src/next_signal/registry.py` plus each
`tools/<domain>/register()` is the source of truth for the tool surface.

## Specs

[`openspec/specs/core-models/`](../../openspec/specs/core-models/),
`core-database`, `core-agents`, `core-tools`, `core-integrations`,
`core-agent-os`, `core-cli`.

State directories and log locations are covered in the
[operations guide](../operations.md#where-state-lives).
