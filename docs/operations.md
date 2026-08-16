# Operations & Troubleshooting

> **English** · [中文](./zh/operations.md)

## Installation

> **Containers are the recommended path** — see
> [`containerized-deployment.md`](./containerized-deployment.md), or the
> [README quick start](../README.md#quick-start). What follows is
> the host-native alternative, which is what you want if you need the local OMLX
> model in-process.

```bash
brew install uv
brew install --cask postgres-app          # or brew install postgresql@16
uv sync
cp .env.example .env && $EDITOR .env       # host-native: DATABASE_URL. Keys go in the dashboard
createdb next_signal
uv run python scripts/bootstrap_db.py
uv run next-signal doctor
uv run next-signal serve                          # → http://localhost:7777
uv run next-signal dashboard                      # → http://localhost:3000
```

## Required and optional services

Required for a minimal working setup: Postgres 16+ with pgvector, an
OpenAI-compatible OMLX endpoint, and the GBrain CLI (required for knowledge
search).

Optional: folocli auth (the info-radar collector), a GitHub token (knowledge's
GitHub bookmarking — anonymous access is capped at 60 req/h), and OpenCLI
(WeChat article ingest), plus locally installed Codex / Claude Code CLIs for
explicit repository-task delegation.

The Dashboard is a separate Next.js process and does not require `next-signal serve` to
be running alongside it: its server actions spawn one-shot `next-signal` CLI children,
and data pages read Postgres directly.

## Credentials

Every provider API key and token is entered on the dashboard settings page
(**Settings → Credentials**) and stored in one file,
`~/.next-signal/secrets.json` (`/state/secrets.json` in a container): a flat
`NAME → value` object, written atomically at mode `0600`.

Eight credentials: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`,
`DEEPSEEK_API_KEY`, `OMLX_API_KEY`, `EMBEDDING_API_KEY`, `GITHUB_TOKEN`,
`FOLO_TOKEN`. The set is closed — every credential the system can require has a
control on that page, `EMBEDDING_API_KEY` being the one an OpenAI-compatible
embedding endpoint uses.

Three properties worth knowing:

- **Saving takes effect immediately, everywhere.** Credentials resolve at call
  time from the shared state volume, so a key saved in the browser is used by the
  next scheduler job — no restart, no `docker compose up --force-recreate`.
- **Nothing reads a credential from the environment.** No fallback, no import. A
  key left in `.env` is inert, and a value set in the environment does not
  satisfy a check.
- **A value never comes back out.** The page reports only whether each credential
  is set; no value, and no masked fragment of one, is returned to the browser or
  written to a log.

The store is plaintext, deliberately: it is the same threat model as the `.env`
it replaces — an unencrypted file readable by the host user — and a Docker named
volume is not a vault. Keeping every secret in one module means a later move to a
real secret manager touches one file.

### Getting a Folo token

Folo issues no API key: its token is a session value, so there is no page that
mints one. **Settings → Credentials → Sign in to Folo** opens Folo in a new tab,
receives the returned one-time token on a dashboard callback route, exchanges it
for a session token, and stores it. Pasting a token manually works too and is the
fallback if the sign-in fails.

`folocli`'s own `~/.folo/config.json` session is **not** consulted. It cannot be
produced in the container — no volume backs it, and `folocli login` completes
over a loopback callback bound inside the container that a host browser cannot
reach — and accepting it would give one credential two sources of truth.

## Environment variables

No credential belongs here, and neither does a local model endpoint — those are
entered on the settings page (**Settings → Engine** for the chat model,
**Settings → Embedding** for the embedder). Key values in the repo-local `.env`:

- `DATABASE_URL`
- `GBRAIN_BIN` (when `gbrain` is not on `PATH`; the dashboard and backend resolve
  it the same way)
- `WIKI_DIR` / `WIKI_RAW_DIR` (**required by the code**, no default — when missing,
  the knowledge pipeline and the dashboard wiki view fail loud. Under Docker
  Compose you can leave them blank: Compose mounts `./state/wiki` and
  `./state/wiki-raw` and sets the in-container values itself, so the variables
  are always present where the code reads them)
- `NEXT_SIGNAL_STATE_DIR` / `NEXT_SIGNAL_AGENT_TMP_DIR` (optional, for tests or alternate paths)

The content language — what radar analyses and wiki frontmatter are written in —
is **not** an env var. It's the `global` language policy's live preference file,
`~/.next-signal/language.json` (`content_language: zh | en`), written by the
dashboard's **settings page** (`/settings`, via the gear in the nav) and falling back to a
hardcoded default when absent. The nav's language picker beside it is a separate
setting that only changes the dashboard's own UI text; the two are independent and
may differ. See [modules/core.md](./modules/core.md#output-language).

Never read these directly from an arbitrary module — go through the corresponding
core/helper function. The complete list is in `.env.example`; credentials are not
among them.

| Integration | Env var |
|---|---|
| LLM: Anthropic / OpenAI / Google / DeepSeek | **Settings → Credentials** (optional `DEEPSEEK_BASE_URL` stays in `.env`, default `https://api.deepseek.com`) |
| Folo (info-radar) | **Settings → Credentials** — required; use "Sign in to Folo" or paste a token. `~/.folo/config.json` is no longer consulted. Optional `FOLO_CLI_ARGV` stays in `.env` |
| GBrain / OpenCLI (knowledge) | `GBRAIN_BIN` (when `gbrain` is not on `PATH`) / `OPENCLI_BIN` (WeChat download — path to `main.js` or a wrapper) |
| Coding agents | `CODEX_BIN` / `CLAUDE_BIN` (optional executable overrides; saved CLI login remains provider-owned) |
| GitHub (knowledge bookmarking) | **Settings → Credentials** (optional; anonymous is 60 req/h) |
| Embedder (info-radar analysis dedup) | Depends on the provider selected in **Settings → Embedding** — see below |

Every cloud integration reads its credential from the store at call time. A
missing credential fails only the corresponding tool — it never blocks startup —
and a credential saved in the dashboard applies to the next call in every
process, with no restart and no `docker compose up --force-recreate`.

**No credential is ever read from the environment.** There is no fallback and no
import: a key left in `.env` is inert.

### Choosing an embedder

The dedup gate's embedder is selected independently of the LLM engine, on
`/settings`, and stored in `~/.next-signal/embedding.json`.

**A fresh install has no embedder selected.** There is no provider next-signal
could honestly pick for you — the local one needs an address only you know, the
hosted ones need a key and spend money — so nothing is chosen until you choose
it, and **deduplication is off until then**. The radar still pulls, scores, and
displays everything; you will simply see the same story more than once.
`next-signal doctor` reports the unselected state, and the settings page says so
above the cards.

Three providers:

| Provider | Configuration | Notes |
|---|---|---|
| `omlx` | Its own API root (**Settings → Embedding**), plus a model the server has loaded; `configs/models.yaml::embedders.local.model_id` prefills `Qwen3-Embedding-0.6B-8bit` | Separate endpoint from **Settings → Engine**: one mlx-lm process serves one model, so chat and embedding are two ports. `OMLX_API_KEY` stays optional. Nothing leaves the machine |
| `openai` | `OPENAI_API_KEY` in **Settings → Credentials**; model prefilled from `embedders.openai` (`text-embedding-3-small`) | Billed per item; summaries leave the machine |
| `openai_compatible` | An API **root** (e.g. `https://host.example/v1` — the client appends `/embeddings`), a model, and a vector-space id, plus `EMBEDDING_API_KEY` in **Settings → Credentials** | No shipped default; all three fields must be saved before it can be selected |

Values from `configs/models.yaml` are **form prefill, not defaults** — they fill
an empty pane and nothing more. Only what you save runs.

Three properties are worth internalising before switching:

- **Every embedder must return exactly 1024 finite values.** The hosted paths
  request `dimensions: 1024`; anything else raises at call time rather than
  being reshaped. `text-embedding-ada-002` and other fixed-width models that
  cannot produce 1024 are therefore unusable.
- **The state file never holds a key, or even names one.** Each provider's
  credential has a fixed name in the store. Credentials in the base URL
  (userinfo, query, fragment) are rejected outright.
- **Nothing here needs a restart.** Both the state file and the credential store
  are read when an item resolves its embedder, so a change to either steers the
  next item — no host-process restart and no `--force-recreate`.

`space_id` is your own label for the vectors a generic endpoint produces. Change
it whenever weights, tokenizer, pooling, quantization, or dimension behaviour
change; moving the same service to a new URL does **not** need a new id. It is
separate from the model name because two endpoints can advertise the same name
while producing incomparable vectors, and a false match suppresses a genuinely
novel item.

### Switching embedder, and the `legacy:unknown` rows

Each stored vector records the identity that produced it in
`radar_pushed_topics.embedder` (`omlx:<model>`, `openai:<model>`, or
`openai_compatible:<space_id>`), and the dedup search only ever compares within
one identity. So switching provider **parks** the previous identity's memory
rather than translating it: expect already-seen topics to be reported as novel
until memory rebuilds under the new identity. Switching back restores the earlier
rows exactly, with no re-embedding — nothing is deleted at any point.

Rows written before the column existed are labelled `legacy:unknown` and stay
parked permanently. Bootstrap does not guess their provenance:
`embedders.local.model_id` has always been operator-editable, so assuming the
shipped default would mislabel a customized install and produce exactly the
cross-space comparison the identity exists to prevent.

If you independently know which model wrote them — for example you never changed
`embedders.local.model_id` — you can relabel them yourself. This is deliberately
manual, has no UI, and is unsafe to run on a guess:

```sql
-- Only if you are certain every pre-migration row came from this model.
UPDATE radar_pushed_topics
   SET embedder = 'omlx:Qwen3-Embedding-0.6B-8bit'
 WHERE embedder = 'legacy:unknown';
```

Check what you would be relabelling first:

```sql
SELECT embedder, count(*), min(first_seen_at), max(last_seen_at)
  FROM radar_pushed_topics GROUP BY embedder ORDER BY 2 DESC;
```

### Migrating from the `paca` names

Releases before the `next-signal` rename used a `PACA_` prefix, a `paca` CLI, and
a `paca` Postgres role. Three steps are not covered by any script in the repo:

1. **Rename the keys in your `.env`** — it is git-ignored, so nothing rewrote it:

   | Old | New |
   |---|---|
   | `PACA_WIKI_DIR` / `PACA_WIKI_RAW_DIR` | `WIKI_DIR` / `WIKI_RAW_DIR` |
   | `PACA_GBRAIN_HOME` / `PACA_GBRAIN_DATABASE_URL` | `GBRAIN_HOME` / `GBRAIN_DATABASE_URL` |
   | `PACA_WHISPER_MODEL` / `PACA_YOUTUBE_TRANSCRIPT_LANGS` | `WHISPER_MODEL` / `YOUTUBE_TRANSCRIPT_LANGS` |
   | `PACA_STATE_DIR` / `PACA_AGENT_TMP_DIR` | `NEXT_SIGNAL_STATE_DIR` / `NEXT_SIGNAL_AGENT_TMP_DIR` |
   | `PACA_LOG_LEVEL` / `PACA_DATABASE_URL` | `NEXT_SIGNAL_LOG_LEVEL` / `NEXT_SIGNAL_DATABASE_URL` |

   Leaving `WIKI_DIR` unset fails loud (`RuntimeError`) rather than defaulting —
   that is intended, not a regression.

2. **Rename the Postgres role** if you are reusing an existing `pgdata` volume.
   `POSTGRES_USER` is only honoured by `initdb` on an empty data directory, so
   the compose default alone will not migrate a volume that already exists — see
   [containerized-deployment.md](./containerized-deployment.md).

3. **Expect the dashboard UI to reset once.** The locale and recap-panel cookies
   were renamed (`paca_locale` → `ns_locale`, `paca_recap_collapsed` →
   `ns_recap_collapsed`), so the old ones are ignored: the UI comes back in its
   default language with the recap panel expanded. Both are one click to restore.

## Where state lives

- Project repo: configs, prompts, code, tests, OpenSpec specs.
- User state (`~/.next-signal/`): `knowledge_ingest_manifest.json`, `language.json`
  (the content-language preference), `engine.json` (production LLM selection),
  `embedding.json` (dedup embedder selection), `coding-agents.json` (explicit
  Codex and Claude CLI settings), `goals.yaml` (info-radar goal descriptors),
  `agent-tmp/`.

  `goals.yaml` lives here rather than under `configs/` because the dashboard
  writes it and the scheduler reads it: `configs/` is baked into the image, so a
  write there would land in one container's writable layer, stay invisible to the
  other, and be discarded by the next rebuild. Container bootstrap copies
  `configs/info_radar/goals.example.yaml` here on a fresh install. It is a no-op
  once the file exists, including when the file holds a deliberately empty
  `goals:` list, so clearing your goals survives a restart.

  There is no automatic migration from the older `configs/info_radar/goals.yaml`,
  which is deleted: `configs/` is image-baked and bind-mounted by nothing, so such
  a step could never run. **Upgrading from a revision that still had that file?**
  Copy it to `~/.next-signal/goals.yaml` — or `docker compose cp` it to
  `/state/goals.yaml` — before you upgrade, or recover it from git history
  afterwards. Otherwise the first bootstrap seeds the examples instead.
- Knowledge base: `~/Projects/digitalpaca-wiki/` (clean) and
  `~/Projects/digitalpaca-wiki-raw/` (raw) — these paths come from
  `WIKI_DIR` / `WIKI_RAW_DIR`, they are not hardcoded defaults.
- agno-managed tables (sessions / memory / knowledge / traces): local Postgres +
  pgvector.
- Logs: stdout only (structlog — console rendering on a TTY, JSON otherwise).
  `~/Library/Logs/next-signal/` is created, but nothing currently writes files
  there.

Under Docker Compose these map to the `pstate` volume and the wiki bind mounts
instead — see [`containerized-deployment.md`](./containerized-deployment.md).

## Health check

```bash
uv run next-signal doctor                            # host-native
docker compose exec dashboard next-signal doctor     # in the container
```

It checks `DATABASE_URL`, the local chat endpoint recorded in `engine.json`
(configured, not reachable), the presence of `ANTHROPIC_API_KEY`
and `DEEPSEEK_API_KEY` **in the credential store**, the resolved content language (reports the `global` policy's
value and whether it came from the preference file or the hardcoded default,
or flags a corrupt/unrecognized preference-file value), the resolved embedder
(prints the active vector-space identity and whether its required configuration
is present, or reports that none is selected and deduplication is inactive — no
embedding request is made, and unusable `embedding.json` is
reported as a failed check rather than crashing doctor),
Postgres reachability, configured agents, registered tools, the
GBrain CLI/service (`gbrain doctor --fast`), folocli auth (`FOLO_TOKEN` present in the store, then
`folocli whoami`; a cached folocli session no longer counts), and that info-radar's
runtime goals file exists, parses, and declares at least one goal. The goals
check reports three failures distinctly — no file at all, a configured-but-empty
`goals:` list, and a parse error — because they call for different fixes; in
every case `next-signal info-radar analyze` raises a loud `RuntimeError`.

The code does **not** distinguish "required" from "optional" checks — **any**
failure exits non-zero, including the folocli auth listed as optional above. The
required/optional split above only means "if this machine will not use that
feature, you can ignore its ✗".

A missing `DEEPSEEK_API_KEY` counts as a failure — the default fallback profile
for `local*` uses DeepSeek when OMLX is unreachable. A missing
`ANTHROPIC_API_KEY` counts too, since the `claude_*` profiles need it. Both are
read from the credential store; setting them in the environment does not satisfy
the check. Credential checks report presence only and never print a value. If you
deliberately run local-only, understand that those cloud fallbacks will fail.

In a cloud-only container, OMLX (and Anthropic, if unset) showing ✗ is expected —
confirm Postgres, agents, and tools are ✔ and treat the rest as informational.

## Optional coding-agent CLIs

`next-signal coding-agent` invokes installed command-line executables. It does
not control the Codex or Claude desktop applications, and it does not register
either worker as an agno model or agent tool. Install and log in to the provider
CLI normally, then check only these optional prerequisites:

```bash
uv run next-signal coding-agent doctor
```

`doctor` resolves `codex` / `claude` from `PATH` (or `CODEX_BIN` /
`CLAUDE_BIN`), runs `--version`, and makes no model request. A run requires an
explicit working directory:

```bash
uv run next-signal coding-agent run codex "review this repository" --cwd .
uv run next-signal coding-agent run claude "fix the failing tests" --cwd . --profile edit
uv run next-signal coding-agent run codex "summarize the change" --cwd . --progress
```

`review` is the default profile: Codex uses its read-only sandbox and Claude
uses `dontAsk` with read-only tools. `edit` must be selected explicitly: Codex
uses `workspace-write`, while Claude receives only the file tools and command
patterns listed in `configs/coding_agents.yaml`. The shipped configuration
cannot select Codex `danger-full-access` or Claude `bypassPermissions`.

The same YAML confines resolved working directories to this project, sets
timeouts and output limits, and lists any extra environment-variable *names*
that a provider child may inherit. The runner always passes a small OS baseline
needed for the CLI and saved login, but it does not copy the rest of
next-signal's environment. Add an API-key variable name only when the child
must receive that secret; repository code executed by the agent may be able to
read it.

The Dashboard settings page can override the Codex model, reasoning effort,
and Standard/Fast speed, plus the Claude model and thinking effort, for
subsequent next-signal runs. It writes `~/.next-signal/coding-agents.json`;
Neither CLI has an inherit or hardcoded default: model and effort must be saved
explicitly for both, and Codex also requires speed, before a run can spawn. The
runner reads and validates the file for every provider invocation and fails
before spawn if required state is absent or malformed. Claude model and effort
use the per-session `--model` and `--effort`
flags; supported effort values are `low`, `medium`, `high`, `xhigh`, and `max`,
with actual availability determined by the selected model. Codex Fast mode is
available only when the active model/account supports it and consumes credits
faster. next-signal never edits `~/.codex/config.toml` or
`~/.claude/settings.json`.

The same settings page writes the production engine choice to
`~/.next-signal/engine.json`. Info-radar analysis/recap and knowledge-ingest LLM
stages read it once per top-level job and use that one engine throughout. A
configured fallback is eligible only if the primary fails before its first
successful response; a schema error is repaired on the same pinned engine, and
a later provider failure never mixes engines within the job. OMLX constrained
decoding, DeepSeek JSON-object output, Claude `--json-schema`, and Codex's
prompt-delivered schema all end in the same local Pydantic/JSON5 validation and
single repair pass. Fetching, embeddings, ANN, persistence, and GBrain are not
rerouted.

Production CLI stages use a dedicated no-tools `stage` profile, not the direct
repository `review` profile. Each invocation gets a fresh empty directory as its
only allowed root. Codex ignores user/repository instructions and disables tool
features; Claude uses safe mode, disables slash commands, and receives an empty
built-in tool set. The article/news prompt is therefore not authorized to read
the repository, `.env`, hooks, plugins, MCP servers, or run commands.

Codex and Claude use their existing saved CLI authentication; next-signal does
not copy `~/.codex`, `~/.claude`, or keychain credentials into its state. On a
host install, install and log in to the CLIs yourself. The official Docker
image instead contains pinned versions of both CLIs, and the Dashboard engine
pane can start their fixed login flows. Those logins remain in separate
provider-owned Docker volumes mounted at `/root/.codex` and `/root/.claude`.
The browser cannot supply a command, argv, executable path, working directory,
or environment variable.

For direct operator `coding-agent run` commands, Claude inherits the normal
local hooks, plugins, MCP servers, auto memory, and `CLAUDE.md` by default.
Set `providers.claude.bare: true` only for controlled API-key
automation: bare mode skips that inherited context and does not use Claude
subscription OAuth. See [containerized deployment](./containerized-deployment.md#coding-agent-cli-login)
for UI login, terminal fallback, version upgrades, and auth-volume lifecycle.

`--progress` changes stdout to JSONL: provider event envelopes first and one
terminal result envelope last. This direct repository-task command is one-shot
and non-persistent; it has no implicit resume, provider fallback, Dashboard
execution surface, or background job. Production workflow fallback is owned by
the stage adapter described above, not by this direct command.

## Common commands

```bash
uv run next-signal list                                     # list agents / workflows
uv run next-signal doctor                                   # self-check
uv run next-signal run-agent <name> "<prompt>"              # one-shot agent call
uv run next-signal coding-agent doctor                       # check optional coding-agent CLIs
uv run next-signal coding-agent run codex "review this repo" --cwd . [--profile edit] [--progress]
uv run next-signal serve [--port 7777]                       # start AgentOS
uv run next-signal schedule                                  # run the wall-clock scheduler (foreground)
                                                      # reads ~/.next-signal/schedule.json every 30s;
                                                      # configure it from the dashboard settings page
uv run next-signal dashboard [--port 3000]                   # start the Next.js dashboard
uv run next-signal dashboard --build                         # dashboard production build
uv run next-signal dashboard --start                         # start an already-built dashboard
uv run next-signal knowledge ingest <url|staged-file>        # ingest into the knowledge base
#   --category <taxonomy-path>   pick the destination folder, skipping auto-classification
#   --progress                   emit one JSON event per step (used by the dashboard progress panel)
uv run next-signal knowledge gbrain-search "query"           # search the local GBrain
uv run next-signal knowledge gbrain-ingest <file|dir>        # import markdown into GBrain
uv run next-signal knowledge review                          # reconcile the wiki against knowledge_reviews
                                                      # (enroll new docs, unenroll gone ones; fixed Ebbinghaus curve)
uv run next-signal info-radar pull [--source NAME]           # run each source CLI, write radar_items
uv run next-signal info-radar sweep                          # delete radar_items rows older than 30 days
uv run next-signal info-radar analyze [--limit N] [--source NAME]
                                                      # run the two-tier analysis pipeline → radar_analyses
                                                      # triggered from the CLI, the dashboard, or the scheduler
                                                      # `seen_at` keeps reruns idempotent at any cadence
                                                      # prerequisite: the runtime goals file must declare >=1 goal
                                                      # (~/.next-signal/goals.yaml, seeded by bootstrap; edit on /goals)
uv run next-signal info-radar subscriptions --json           # read Folo subscriptions as stable JSON lines
                                                      # merges `unread list` for per-feed unread counts
uv run next-signal info-radar recap --since D --until D [--min-score N] [--novel-only] [--regenerate]
                                                      # synthesize a date range of kept signals into
                                                      # themed narratives (cached per range + gate)
uv run next-signal run-workflow knowledge_ingest             # manual wiki → GBrain re-ingest
```

The Dashboard UI defaults to **English** and can be switched to Chinese from the
nav bar; the choice is stored in the `ns_locale` cookie. Only interface copy is
translated — article titles, analysis summaries, tags, and YAML content render
as stored.

For a full-chain test that touches a real GBrain index, use an isolated PGLite
brain:

```bash
uv run next-signal knowledge init-test-gbrain
GBRAIN_HOME=state/test-gbrain uv run next-signal doctor
```

`GBRAIN_HOME` is the parent directory; GBrain stores its config and
`brain.pglite` under `$GBRAIN_HOME/.gbrain/`. Keep it inside the ignored
`state/` directory and leave the production `~/.gbrain` alone.

## Unattended runs

The radar chain — `info-radar pull` then `info-radar analyze` — can run on a
wall clock instead of by hand. The `scheduler` service in `docker-compose.yml`
runs `next-signal schedule`, a poll loop that fires the chain at each configured
local time. Configure it from the **dashboard settings page** (the gear in the
nav): on/off, the times, and what to do about a missed run.

The schedule is stored in `~/.next-signal/schedule.json` and re-read on every
poll, so a change from the dashboard takes effect within 30 seconds with no
restart. Hand-editing works too:

```json
{ "enabled": true, "at": ["08:00", "13:00", "20:00"], "catch_up": false }
```

`at` is a list of 24-hour local times in `INFO_RADAR_TIMEZONE` — the same
timezone the dashboard uses for the radar's day boundary. **Every listed time
fires every day**, so the example above runs the chain three times daily. The
list is deduplicated and sorted on write; a bare string is still accepted and
read as a single time, since that is what the field held before multiple daily
runs existed. An absent file means no schedule has been configured, which reads
as disabled; that is why the service is safe to leave running on a stack nobody
has configured.

`enabled` and `catch_up` must be **real JSON booleans**. `"enabled": "false"` —
quoted — is rejected with an error naming the field, rather than read as `true`,
which is what a plain string-to-boolean conversion would do and is the opposite
of what someone typing it means. Omitting either field is fine and reads as
false. A malformed file stops the scheduler with a loud error and restarts it
into the same error, which is deliberate: the dashboard stays up throughout, so
the panel that fixes the file is always reachable.

**`catch_up` covers exactly one case: a slot nobody was watching when it came
round.** With it off (the default), such a slot is skipped. With it on, the
scheduler runs the chain **once** — once, no matter how many slots went by,
which with several daily times means one run rather than one per missed time.
It does *not* fire because you changed the schedule, added a time, or just
switched it on; a time that has already gone by today never triggers a run.

"Nobody was watching" is judged from the clock, not from how the scheduler came
to be away: a stopped container, a host that slept through the slot without ever
restarting the process, and a previous run that overran into the next time are
one case and get one answer. That last one is why a long run never stacks a
second run onto its own tail with catch-up off.

Nothing fires while the container host is not running Docker. Nothing inside a
container can start Docker, so a laptop that was closed overnight simply misses
the window — `catch_up` is the mitigation, not a fix.

The settings page reports where the last run stands — never run, running (with
how long it has been going), succeeded, or failed. A run interrupted by the
container being killed reads as a failure once the scheduler starts again, not
as one still in flight. A full radar run can take tens of minutes, so the
in-progress line is the difference between "still working" and "did nothing".
The scheduler also logs each run to its container:

```bash
docker compose logs -f scheduler
```

## Troubleshooting

- **`DATABASE_URL not set`** → copy `.env.example` to `.env` and fill it in.
- **`<NAME> is not configured`** → the credential is missing from the store; set
  it in **Settings → Credentials**. Setting it in `.env` has no effect.
- **Postgres unreachable** → start Postgres.app or the Homebrew service, then
  rerun `next-signal doctor`.
- **An OMLX profile fell back to DeepSeek** → check the endpoint in
  **Settings → Engine**, the optional `OMLX_API_KEY` in Settings → Credentials,
  and the endpoint's `/v1/models`. Models are not cached, so once OMLX is back
  the next call retries local on its own. The exception is AgentOS, which builds
  its interactive agents once at startup: restart that process to pick up a new
  endpoint.
- **The radar shows the same story repeatedly** → no embedder is selected, so
  deduplication is off. Choose one in **Settings → Embedding**;
  `next-signal doctor` reports this as a failed embedder check.
- **GBrain search / re-index fails** → run `next-signal doctor` and
  `gbrain doctor --fast`. When embedding fails, ingest should fail loud *after*
  writing the wiki artifact, leaving the manifest un-advanced; fix the cause and
  rerun `next-signal run-workflow knowledge_ingest`.
- **Dashboard won't start** → confirm `pnpm` is on `PATH`, then use
  `uv run next-signal dashboard --build` to surface Next.js compile errors. The
  dashboard does not need `next-signal serve`, but `/radar` needs Postgres,
  `/knowledge` needs the GBrain CLI, and `/subscriptions` needs Folo auth.
- **knowledge ingest rejects a local file** → local file input must be staged
  under `NEXT_SIGNAL_AGENT_TMP_DIR`. The dashboard's `/radar` Folo ingest stages the
  full text from `folocli entry get` into `NEXT_SIGNAL_AGENT_TMP_DIR/radar-ingest/`
  automatically; non-Folo radar items still require a valid `radar_items.url`.
- **An agent can't see a tool** → check that the tool is registered
  (`_IN_TREE_TOOLS`, `tools/<domain>.register()`, workflow tool exposure, or
  integration registration), that the agent YAML uses the exact registered name,
  and run `tests/test_registry.py`.
- **Container-specific issues** (build failures, volume mapping, the cloud-only
  embedder gap) → see
  [`containerized-deployment.md`](./containerized-deployment.md) §7–§8.
