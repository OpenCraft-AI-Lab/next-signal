# core-cli

The `next-signal` CLI is the operator entry point. All commands run via `uv run next-signal …`.

## Purpose

Operator tasks (listing components, starting the server, running an agent once, self-checking) must be reachable without scripting against the AgentOS HTTP API.
## Requirements

### Requirement: `next-signal list` enumerates configured runnables

`next-signal list` SHALL print configured agents, workflows, and teams by name.

#### Scenario: operator audits available runnables

- **WHEN** the operator runs `next-signal list`
- **THEN** the output includes `Agents:`, `Workflows:`, and `Teams:` sections with one line per configured runnable

### Requirement: `next-signal serve` starts AgentOS

`next-signal serve` SHALL launch the FastAPI AgentOS app on port 7777.

#### Scenario: server is reachable after start

- **WHEN** the operator runs `next-signal serve`
- **THEN** `http://localhost:7777/docs` returns the OpenAPI page

### Requirement: `next-signal run-agent` executes a single prompt

`next-signal run-agent <name> "<prompt>"` SHALL build the named agent (without starting AgentOS) and stream the response to stdout.

#### Scenario: one-shot invocation

- **WHEN** the operator runs `next-signal run-agent echo "hello"`
- **THEN** the CLI prints the agent's response and exits 0 without binding port 7777

### Requirement: `next-signal doctor` self-checks the environment

`next-signal doctor` SHALL verify `.env` system connection configuration, the
presence of each required credential in the credential store, **which engine
production stage jobs will resolve**, the local model endpoints recorded in
user state (checking that they are configured, not that they are reachable),
Postgres reachability, the presence of every registered tool, the GBrain CLI /
service health **and whether GBrain is initialised and able to embed**, and
the folocli authentication (`FOLO_TOKEN` present in the store and `folocli
whoami` returns `ok: true`), reporting each check as ✓ or ✗.

The engine check SHALL report an unselected engine distinctly from a selected
one, and its message SHALL state the consequence — every production stage job
(info-radar analyze, info-radar recap, knowledge ingest) will fail to start —
rather than describing it only as an error in the system.

`OMLX_BASE_URL` SHALL NOT be checked, because no part of the system reads it.
The local chat endpoint SHALL be reported from engine preferences and the
embedding endpoint from embedding preferences, since they are separately
configured.

GBrain readiness SHALL be reported as three distinct states, because collapsing
them hides a deployment that cannot search:

- **not initialised** — a failed check naming knowledge search as unavailable
  and naming the command that initialises GBrain. This is the expected state of
  a first-time stack, because bootstrap deliberately leaves GBrain
  uninitialised; it is reported so that it is visible rather than discovered
  when a search returns nothing.
- **initialised but not ready** — the selected embedding provider's credential
  is absent, so the brain exists but cannot embed. A failed check naming that
  provider's credential.
- **ready** — initialised with a model whose credential requirements are
  satisfied.

This check SHALL determine those states itself rather than delegating to the
external tool's own health command, which reports a healthy brain and exits zero
even when no brain exists.

Credential checks SHALL report presence only, never any part of a value, and
SHALL direct the operator to the dashboard settings page rather than to `.env`.
Endpoint checks SHALL do the same.

#### Scenario: missing key reported

- **WHEN** `DEEPSEEK_API_KEY` is absent from the credential store
- **THEN** `next-signal doctor` reports a ✗ for the corresponding check, points
  at the settings page, and exits non-zero

#### Scenario: no engine selected is reported

- **WHEN** `engine.json` records no primary engine
- **THEN** `next-signal doctor` reports a ✗ stating that production stage jobs
  cannot run, points at the settings page, and exits non-zero

#### Scenario: a selected engine is reported without a request

- **WHEN** `engine.json` records a primary engine
- **THEN** `next-signal doctor` reports it and its fallback, performing no
  provider call

#### Scenario: endpoints are read from user state

- **WHEN** the local chat and embedding endpoints are recorded in user state
- **THEN** `next-signal doctor` reports each from its own state file and reads
  no endpoint from the process environment

#### Scenario: environment does not satisfy an endpoint check

- **WHEN** `OMLX_BASE_URL` is set in the process environment but no endpoint is
  recorded in user state
- **THEN** `next-signal doctor` reports the endpoint as unconfigured

#### Scenario: an uninitialised GBrain is reported

- **WHEN** the GBrain CLI is reachable but no brain has been initialised
- **THEN** `next-signal doctor` reports a ✗ stating that knowledge search is
  unavailable and naming the command that initialises GBrain

#### Scenario: an initialised GBrain missing its provider credential is reported

- **WHEN** GBrain is initialised with an embedding model whose provider
  credential is absent from the store
- **THEN** `next-signal doctor` reports a ✗ naming that provider's credential,
  distinctly from the uninitialised state

#### Scenario: environment does not satisfy a credential check

- **WHEN** a credential is set in the process environment but absent from the
  credential store
- **THEN** `next-signal doctor` reports a ✗ for that credential

#### Scenario: GBrain CLI absent

- **WHEN** the `gbrain` CLI is not on PATH
- **THEN** `next-signal doctor` reports a ✗ for the GBrain check and explains how to install it

#### Scenario: folocli not authenticated

- **WHEN** `FOLO_TOKEN` is absent from the credential store
- **THEN** `next-signal doctor` reports a ✗ for the folocli check and points to
  the settings page, without suggesting `folo login`

### Requirement: `next-signal info-radar pull` invokes the collector

`next-signal info-radar pull [--source NAME]` SHALL load `configs/info_radar/sources.yaml`, run every enabled source (or only the named one), persist results to `radar_items`, and print a per-source summary. Exit code is zero unless every enabled source fails.

#### Scenario: operator pulls all sources

- **WHEN** the operator runs `next-signal info-radar pull`
- **THEN** the CLI invokes each enabled source's CLI, writes new items, and prints one line per source with the count written

#### Scenario: operator pulls one source

- **WHEN** the operator runs `next-signal info-radar pull --source folo_articles_ai`
- **THEN** the CLI invokes only that source and ignores others

### Requirement: `next-signal info-radar sweep` deletes expired rows

`next-signal info-radar sweep` SHALL run the 30-day retention `DELETE` against `radar_items` and report the number of rows removed.

#### Scenario: standalone sweep

- **WHEN** the operator runs `next-signal info-radar sweep`
- **THEN** the CLI prints the rows-removed count and exits zero, even if no rows were eligible

### Requirement: `next-signal info-radar analyze` runs the analysis pipeline

`next-signal info-radar analyze [--limit N] [--source NAME]` SHALL run the two-tier info-radar-analysis pipeline over unseen `radar_items`, optionally capped to `N` items and/or restricted to one collector source, and print the resulting counters.

#### Scenario: operator runs analysis with a limit

- **WHEN** the operator runs `next-signal info-radar analyze --limit 20`
- **THEN** the CLI processes at most 20 unseen items and prints `info-radar analyze: <counter>=<value> ...`

### Requirement: `next-signal info-radar subscriptions` lists Folo subscriptions

`next-signal info-radar subscriptions [--json]` SHALL list Folo subscriptions through the pinned folocli bridge, printing one line per subscription (title, category, feed URL, unread count) by default or a JSON array of normalized rows with `--json`.

#### Scenario: operator lists subscriptions as JSON

- **WHEN** the operator runs `next-signal info-radar subscriptions --json`
- **THEN** the CLI prints the subscription rows as a JSON array instead of the plain-text listing

### Requirement: `next-signal dashboard` wraps the Next.js dev/build/start commands

`next-signal dashboard [--build | --start] [--port N]` SHALL be a thin wrapper over `pnpm` in `dashboard/`: with no flags it execs `pnpm dev -p <port>`; `--build` execs `pnpm build`; `--start` execs `pnpm start -p <port>` (intended to follow a prior `--build`). `--build` and `--start` are mutually exclusive. The command SHALL fail with a clear error if `pnpm` is not on PATH or `dashboard/package.json` is missing.

#### Scenario: operator starts the dashboard dev server

- **WHEN** the operator runs `next-signal dashboard`
- **THEN** the CLI execs `pnpm dev -p 3000` from `dashboard/`, replacing the Python process so signals reach `pnpm` directly

#### Scenario: mutually exclusive flags rejected

- **WHEN** the operator runs `next-signal dashboard --build --start`
- **THEN** the CLI prints an error and exits non-zero without invoking `pnpm`

### Requirement: `next-signal run-workflow` runs a workflow's manual entrypoint

`next-signal run-workflow <name>` SHALL load `configs/workflows/<name>.yaml`, resolve its `extra.run_now` factory, call it, and print the JSON result. A workflow without `extra.run_now` set SHALL raise a clear error rather than silently no-op.

#### Scenario: dashboard triggers a manual re-index

- **WHEN** the operator (or the dashboard's re-index action) runs `next-signal run-workflow knowledge_ingest`
- **THEN** the CLI resolves and calls the workflow's `extra.run_now` entrypoint and prints its JSON result

#### Scenario: workflow has no manual entrypoint

- **WHEN** the operator runs `next-signal run-workflow <name>` for a workflow without `extra.run_now`
- **THEN** the CLI raises `RuntimeError("manual run is not implemented for workflow: <name>")`

### Requirement: `next-signal knowledge` subcommand group manages ingestion and GBrain

The `next-signal knowledge` subcommand group SHALL expose: `ingest <value>` (route a URL or staged local file through the knowledge-ingest pipeline, with `--ingest/--no-ingest` to control whether the clean markdown is imported into GBrain, `--category` to pin the destination taxonomy path and skip auto-classification, and `--progress` to emit one JSON event per pipeline step to stdout followed by the final JSON result); `gbrain-init --embedding-model <provider>:<model> [--embedding-dimensions N]` (perform GBrain's one-time initialisation with the operator's chosen embedding provider and model); `gbrain-search <query> [--limit N]` (search GBrain through the local CLI bridge and print JSON results); `gbrain-ingest <path>` (import a markdown file or directory into GBrain through the local CLI bridge and print the JSON result); `init-test-gbrain [--home PATH]` (initialize an isolated local GBrain PGLite database under `state/test-gbrain` by default, for integration tests); and `review` (reconcile the wiki against `knowledge_reviews` — enroll docs with no row, unenroll rows whose file is gone — and print the counts of docs enrolled, unenrolled, and currently due; no flags, no LLM call, since the review card reuses each doc's frontmatter summary).

`gbrain-init` SHALL require an explicit `--embedding-model` and SHALL NOT
default to one, because the choice is permanent and provider-specific. It SHALL
accept any provider GBrain supports, including local runners that require no
credential, and SHALL inject only the selected provider's credential.
`--embedding-dimensions` SHALL be optional, overriding the dimension GBrain
derives from the model; it exists because that derived value is written
permanently into the schema.

`gbrain-init` SHALL refuse to run against an already-initialised brain, naming
the embedding model already in use. It SHALL NOT offer a force or re-initialise
flag, because the embedding model sizes the schema and cannot be changed in
place.

#### Scenario: operator ingests a URL

- **WHEN** the operator runs `next-signal knowledge ingest https://example.com/article`
- **THEN** the CLI runs the knowledge-ingest pipeline and prints the JSON result, importing into GBrain unless `--no-ingest` is passed

#### Scenario: progress events stream as JSONL

- **WHEN** the operator runs `next-signal knowledge ingest <value> --progress`
- **THEN** the CLI writes one JSON event per pipeline step to stdout, followed by a final JSON result line, forming valid JSONL

#### Scenario: operator initialises GBrain with a chosen model

- **WHEN** the operator runs `next-signal knowledge gbrain-init --embedding-model <provider>:<model>` against an uninitialised GBrain
- **THEN** the brain is initialised with that model, and knowledge search becomes available once the provider's credential requirements are satisfied

#### Scenario: initialising an already-initialised brain is refused

- **WHEN** the operator runs `next-signal knowledge gbrain-init` against a brain that is already initialised
- **THEN** the command fails, names the embedding model already in use, and changes nothing

#### Scenario: a local embedding provider needs no credential

- **WHEN** the operator runs `next-signal knowledge gbrain-init --embedding-model <local-provider>:<model>` with an empty credential store
- **THEN** the initialisation succeeds

#### Scenario: operator searches GBrain from the CLI

- **WHEN** the operator runs `next-signal knowledge gbrain-search "topic" --limit 5`
- **THEN** the CLI prints the search results as indented JSON

#### Scenario: operator reconciles review enrollment

- **WHEN** the operator runs `next-signal knowledge review`
- **THEN** the CLI enrolls wiki docs that have no review row, unenrolls rows whose file is gone, and prints the enrolled, unenrolled, and due counts

### Requirement: `next-signal info-radar recap` generates a range recap

`next-signal info-radar recap --since YYYY-MM-DD --until YYYY-MM-DD [--min-score N] [--novel-only] [--regenerate]` SHALL run the info-radar-recap workflow over the requested range and quality gate, and print the resulting headline plus one line per theme with its citation count. Without `--regenerate`, a request whose recap already exists in `status='done'` SHALL print the cached recap and make no LLM call. With `--regenerate`, the recap SHALL be recomputed and the stored row replaced. Both `--since` and `--until` are required; an inverted or unparseable range SHALL exit non-zero without invoking the agent. A range in which no item clears the quality gate SHALL print an explicit empty-result message and exit zero.

#### Scenario: operator generates a weekly recap

- **WHEN** the operator runs `next-signal info-radar recap --since 2026-07-13 --until 2026-07-19`
- **THEN** the CLI selects kept analyses in that local-date range, generates the recap, persists it, and prints the headline followed by each theme title and its citation count

#### Scenario: repeat invocation is served from cache

- **WHEN** the operator re-runs the same `next-signal info-radar recap` command for a range already recapped with `status='done'`
- **THEN** the CLI prints the stored recap and makes no LLM call

#### Scenario: regeneration forces recompute

- **WHEN** the operator runs the same command with `--regenerate`
- **THEN** the recap is recomputed and the existing row for that key is replaced rather than duplicated

#### Scenario: empty range exits cleanly

- **WHEN** the operator requests a recap for a range where no item clears the quality gate
- **THEN** the CLI prints an explicit empty-result message, writes no row, and exits zero

#### Scenario: inverted range is rejected

- **WHEN** the operator runs `next-signal info-radar recap --since 2026-07-19 --until 2026-07-13`
- **THEN** the CLI exits non-zero reporting the invalid range, and no agent is invoked

### Requirement: `next-signal schedule` runs the wall-clock scheduler

`next-signal schedule` SHALL run the scheduler poll loop in the foreground until interrupted. It is the command the `scheduler` container service runs, and it takes no flags — the schedule itself lives in `~/.next-signal/schedule.json`, not in argv, so that the dashboard and the operator edit one source of truth.

The command SHALL emit structured log lines to stdout on start (naming the resolved timezone and whether a schedule is configured), when a run begins and ends, and when a run fails. Because a container operator's only window into a long-running service is its log stream, a scheduler that runs silently SHALL be considered non-conforming.

#### Scenario: operator runs the scheduler

- **WHEN** the operator runs `next-signal schedule`
- **THEN** the loop starts, logs its resolved timezone and configured state, and stays in the foreground polling until interrupted

#### Scenario: scheduler starts with no schedule configured

- **WHEN** `next-signal schedule` starts and no schedule file exists
- **THEN** it logs that no schedule is configured, keeps polling, and exits non-zero only on an unrecoverable error, not on an absent schedule

#### Scenario: a failing run does not stop the command

- **WHEN** a scheduled chain raises during a run
- **THEN** the failure is logged at error level and the command keeps polling rather than exiting

### Requirement: `next-signal coding-agent doctor` checks coding-agent prerequisites

`next-signal coding-agent doctor` SHALL validate the coding-agent configuration, resolve each enabled provider executable, run a non-model version check, and print one status line per provider. It SHALL exit non-zero when configuration is invalid or any enabled provider is unavailable or not executable, and SHALL NOT submit a model request.

#### Scenario: Both providers are available

- **WHEN** configured Codex and Claude fixture executables return versions successfully
- **THEN** doctor prints successful status lines for both providers and exits zero without starting an agent run

#### Scenario: Enabled provider is missing

- **WHEN** an enabled provider executable cannot be resolved
- **THEN** doctor names the missing provider, prints a remediation hint for its binary override, and exits non-zero

### Requirement: `next-signal coding-agent run` executes an explicit provider

`next-signal coding-agent run <provider> <prompt> --cwd <path> [--profile <name>] [--progress]` SHALL require an explicit supported provider and working directory, default to the review profile, invoke the coding-agent bridge once, and exit zero only when the terminal result has `ok: true`.

#### Scenario: Operator starts a review run

- **WHEN** the operator runs `next-signal coding-agent run codex "review this repository" --cwd .`
- **THEN** the CLI invokes Codex once with the review profile and exits according to the bridge's terminal result

#### Scenario: Unknown provider is rejected before spawn

- **WHEN** the operator names a provider other than `codex` or `claude`
- **THEN** the CLI reports the valid provider names and does not spawn a child process

#### Scenario: Unknown profile is rejected before spawn

- **WHEN** the operator names a profile absent from coding-agent configuration
- **THEN** the CLI reports the configured profile names and does not spawn a child process

### Requirement: Coding-agent progress output is valid JSONL

Without `--progress`, `next-signal coding-agent run` SHALL print only the terminal result as JSON. With `--progress`, it SHALL print one event envelope per line followed by the single terminal result envelope, with no non-JSON provider diagnostics mixed into stdout.

#### Scenario: Progress consumer receives parseable lines

- **WHEN** the operator runs a successful provider fixture with `--progress`
- **THEN** every stdout line parses as one JSON object and the final line has `type: "result"`

#### Scenario: Non-progress run prints one result

- **WHEN** the operator runs the same fixture without `--progress`
- **THEN** stdout contains only the terminal result JSON and excludes intermediate provider events

### Requirement: Internal authentication CLI surface is allowlisted

The coding-agent command group SHALL expose machine-readable provider authentication status and a PTY-backed login-session broker for Dashboard use. Both commands SHALL accept only `codex` or `claude`, map those values to fixed provider argv, and SHALL NOT accept browser-selected executable paths, provider argv, shell commands, working directories, or environment additions.

#### Scenario: Dashboard checks provider status

- **WHEN** the Dashboard invokes authentication status for a supported provider
- **THEN** the command runs only that provider's fixed status argv and emits one bounded JSON result

#### Scenario: Unsupported provider is supplied

- **WHEN** the authentication command receives any provider other than `codex` or `claude`
- **THEN** it exits non-zero before resolving or spawning an executable
