# Module: core (framework chassis)

> **English** · [中文](../zh/modules/core.md)

## What it solves

The infrastructure every runnable shares: the model factory and its fallback
chain, database connections, shared context, and per-provider concurrency.
Understand this layer before touching any business module — the agents, tables,
and embeddings of both product modules ([knowledge](./knowledge.md) and
[info_filter](./info_filter.md)) run on top of it.

## Where the code lives

- `src/next_signal/core/models.py` — static/live-stage model construction + embedder
- `src/next_signal/core/engine_preferences.py` — strict per-job engine state
- `src/next_signal/core/embedding_preferences.py` — strict per-item embedding state
- `src/next_signal/core/omlx.py` — the only OMLX endpoint resolver
- `src/next_signal/core/secrets.py` — the credential store and `child_env`
- `src/next_signal/agents/stage.py` — provider-neutral production stages and job affinity
- `src/next_signal/core/config.py` — every YAML loader (strict pydantic; unknown keys
  fail loud)
- `src/next_signal/core/db.py` — `database_url()` plus the `get_db()` singleton for
  agno-managed tables
- `src/next_signal/core/context.py` — shared-context assembly
- `src/next_signal/core/concurrency.py` — per-provider inference concurrency semaphores
- `src/next_signal/core/paths.py` / `logging.py` / `fileio.py` — path conventions /
  structlog / atomic writes

## The model system

`configs/models.yaml` is the static profile/baseline source of truth. AgentOS
agents reference it by profile name. Production workflows call `run_stage`: one
job reads `engine.json`, uses YAML as the API-model baseline, and applies live
OMLX/DeepSeek or explicit Codex/Claude settings from `coding-agents.json`.
Business stages never construct provider models directly.

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
  propagate instead of falling back. **Models are not cached** — the endpoint and
  credentials they are built from live in user state that can change while a
  process runs, so the profile name no longer determines the result — which also
  means OMLX is retried automatically once it recovers, with no manual step.
  The caveat is a caller that *retains* a built model: `next-signal serve`
  constructs its agents once at import, so those pick up an endpoint change on
  restart. Stage models and embedders resolve per job and per item.
- `next_signal.core.omlx.resolve_omlx_endpoint()` is the only reader of the local
  chat endpoint, taking `base_url` from `engine.json` and `OMLX_API_KEY` from the
  credential store; ordinary callers use the strict public
  `next_signal.core.models.omlx_endpoint()` wrapper. Never duplicate that access,
  and never read an endpoint from the environment — the dashboard and scheduler
  are separate containers that share `/state` but not their environments. The
  embedder's OMLX endpoint is separate again, in `embedding.json`.
- Qwen3 specifics are pinned in `_build_omlx`: thinking disabled, sampling
  parameters, and structured output through the standard OpenAI
  `response_format` json_schema (xgrammar constrained decoding on the OMLX side).
  agno's native structured outputs stay off.
- DeepSeek goes through `_build_deepseek`: OpenAI-compatible
  (`DEEPSEEK_API_KEY` from the credential store, plus optional
  `DEEPSEEK_BASE_URL` in the environment, default `https://api.deepseek.com`), but it supports only `response_format`
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
- **The embedder** is provider-neutral and does not go through the profile
  factory at all. `get_embedder()` takes no arguments: it reads
  `~/.next-signal/embedding.json` plus the process environment once per item and
  returns an immutable `ResolvedEmbedder` (provider, model, vector-space
  identity, `embed()`). Three providers are supported — `omlx`, `openai`, and one
  operator-supplied `openai_compatible` API root.

  `models.yaml::embedders` is only the per-provider baseline: `local` supplies
  the OMLX model and the fresh-install selection, `openai` supplies the OpenAI
  model. The generic endpoint has no honest default and must be configured
  before it can be selected.

  **Every embedder must return exactly 1024 finite numbers.** `embed()` checks
  the full vector and raises `RuntimeError` on a wrong length, a non-numeric
  element, `NaN`, or infinity; it never truncates, pads, or normalizes. The
  hosted providers request `dimensions: 1024` (OMLX's route has no such
  parameter). That is what keeps `radar_pushed_topics.embedding` at
  `vector(1024)` across a provider switch — and it excludes fixed-width models
  that cannot produce it, such as `text-embedding-ada-002`.

  **Nothing is selected until an operator selects one.** An absent or
  provider-less `embedding.json` resolves to unselected, `get_embedder()` raises
  `EmbedderNotSelected` — a distinct type so callers can tell "not set up" from
  "broken" — and the dedup gate turns itself off while the rest of the run
  proceeds. `configs/models.yaml::embedders` is form prefill, never a default.

  **State and secrets are split.** The state file holds the selection, models,
  API roots, and vector-space id; it never holds a key, or even names one. Each
  provider's credential has a fixed name — `OMLX_API_KEY` (optional),
  `OPENAI_API_KEY`, `EMBEDDING_API_KEY` — read from the store when the snapshot
  is built.
  Both the state file and the store are read at snapshot time, so an edit to
  either steers the next item with no restart and no `--force-recreate`. There is no embedder fallback: unlike two LLMs, two embedders are not
  substitutable, so a failure raises and the dedup gate treats the item as novel.

## Concurrency

`models.yaml::concurrency` gives each API and CLI provider a ceiling (`omlx: 2` —
one local GPU; cloud/CLI values guard against runaway work). Every model the
factory produces has its `response` / `aresponse` and both streaming entrypoints
wrapped in that provider's semaphore. An embedder call draws on the quota of
*its own* resolved provider: an OMLX embedding queues behind OMLX inference
because both contend for one GPU, while a hosted embedding uses its own key and
never consumes that slot. Everything built through the factory inherits this
automatically. Production CLI stages hold the same
semaphore for the entire child process and run in an empty ephemeral directory
under the no-tools `stage` profile. Direct operator `review`/`edit` commands keep
their repository capabilities.

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
  dashboard's **settings page** writes this file (the nav's language picker does
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
- Env is always read at call time, never at import time — a missing value must
  not block startup.
- **No credential is ever read from the environment.** Every provider key and
  token comes from `core/secrets.py`, which reads
  `$NEXT_SIGNAL_STATE_DIR/secrets.json` at the point of use. There is no
  fallback and no import path, so the rule is checkable: a credential name
  appearing next to `os.environ` anywhere in `src/` is a defect.
- **Credentials reach a subprocess only per spawn.** `secrets.child_env(names)`
  builds one child's environment, stripping every known credential first and
  putting back only the named ones. Nothing writes to `os.environ`: the
  dashboard spawns CLI children with its whole environment, so materializing
  credentials there would hand every secret to every child — including the
  coding-agent CLIs, which run with `inherit_env: []` on purpose.
- **A credential value never leaves the server.** Not to a browser, not to a
  log, not into an exception message.
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
