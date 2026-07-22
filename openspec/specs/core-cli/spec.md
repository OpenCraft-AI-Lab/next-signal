# core-cli

The `paca` CLI is the operator entry point. All commands run via `uv run paca …`.

## Purpose

Operator tasks (listing components, starting the server, running an agent once, self-checking) must be reachable without scripting against the AgentOS HTTP API.
## Requirements
### Requirement: `paca list` enumerates configured runnables

`paca list` SHALL print configured agents, workflows, and teams by name.

#### Scenario: operator audits available runnables

- **WHEN** the operator runs `paca list`
- **THEN** the output includes `Agents:`, `Workflows:`, and `Teams:` sections with one line per configured runnable

### Requirement: `paca serve` starts AgentOS

`paca serve` SHALL launch the FastAPI AgentOS app on port 7777.

#### Scenario: server is reachable after start

- **WHEN** the operator runs `paca serve`
- **THEN** `http://localhost:7777/docs` returns the OpenAPI page

### Requirement: `paca run-agent` executes a single prompt

`paca run-agent <name> "<prompt>"` SHALL build the named agent (without starting AgentOS) and stream the response to stdout.

#### Scenario: one-shot invocation

- **WHEN** the operator runs `paca run-agent echo "hello"`
- **THEN** the CLI prints the agent's response and exits 0 without binding port 7777

### Requirement: `paca doctor` self-checks the environment

`paca doctor` SHALL verify `.env` configuration (including whether `OMLX_BASE_URL` is set — this checks the env var is configured, not that the endpoint is reachable), Postgres reachability, the presence of every registered tool, the GBrain CLI / service health, and the folocli authentication (`FOLO_TOKEN` set and `folocli whoami` returns `ok: true`), reporting each check as ✓ or ✗.

#### Scenario: missing key reported

- **WHEN** `ANTHROPIC_API_KEY` is unset
- **THEN** `paca doctor` reports a ✗ for the corresponding check and exits non-zero

#### Scenario: GBrain CLI absent

- **WHEN** the `gbrain` CLI is not on PATH
- **THEN** `paca doctor` reports a ✗ for the GBrain check and explains how to install it

#### Scenario: folocli not authenticated

- **WHEN** `FOLO_TOKEN` is unset and `folocli whoami` returns `ok: false`
- **THEN** `paca doctor` reports a ✗ for the folocli check and points to `folo login` or `FOLO_TOKEN`

### Requirement: `paca info-radar pull` invokes the collector

`paca info-radar pull [--source NAME]` SHALL load `configs/info_radar/sources.yaml`, run every enabled source (or only the named one), persist results to `radar_items`, and print a per-source summary. Exit code is zero unless every enabled source fails.

#### Scenario: operator pulls all sources

- **WHEN** the operator runs `paca info-radar pull`
- **THEN** the CLI invokes each enabled source's CLI, writes new items, and prints one line per source with the count written

#### Scenario: operator pulls one source

- **WHEN** the operator runs `paca info-radar pull --source folo_articles_ai`
- **THEN** the CLI invokes only that source and ignores others

### Requirement: `paca info-radar sweep` deletes expired rows

`paca info-radar sweep` SHALL run the 30-day retention `DELETE` against `radar_items` and report the number of rows removed.

#### Scenario: standalone sweep

- **WHEN** the operator runs `paca info-radar sweep`
- **THEN** the CLI prints the rows-removed count and exits zero, even if no rows were eligible

### Requirement: `paca info-radar analyze` runs the analysis pipeline

`paca info-radar analyze [--limit N] [--source NAME]` SHALL run the two-tier info-radar-analysis pipeline over unseen `radar_items`, optionally capped to `N` items and/or restricted to one collector source, and print the resulting counters.

#### Scenario: operator runs analysis with a limit

- **WHEN** the operator runs `paca info-radar analyze --limit 20`
- **THEN** the CLI processes at most 20 unseen items and prints `info-radar analyze: <counter>=<value> ...`

### Requirement: `paca info-radar subscriptions` lists Folo subscriptions

`paca info-radar subscriptions [--json]` SHALL list Folo subscriptions through the pinned folocli bridge, printing one line per subscription (title, category, feed URL, unread count) by default or a JSON array of normalized rows with `--json`.

#### Scenario: operator lists subscriptions as JSON

- **WHEN** the operator runs `paca info-radar subscriptions --json`
- **THEN** the CLI prints the subscription rows as a JSON array instead of the plain-text listing

### Requirement: `paca dashboard` wraps the Next.js dev/build/start commands

`paca dashboard [--build | --start] [--port N]` SHALL be a thin wrapper over `pnpm` in `dashboard/`: with no flags it execs `pnpm dev -p <port>`; `--build` execs `pnpm build`; `--start` execs `pnpm start -p <port>` (intended to follow a prior `--build`). `--build` and `--start` are mutually exclusive. The command SHALL fail with a clear error if `pnpm` is not on PATH or `dashboard/package.json` is missing.

#### Scenario: operator starts the dashboard dev server

- **WHEN** the operator runs `paca dashboard`
- **THEN** the CLI execs `pnpm dev -p 3000` from `dashboard/`, replacing the Python process so signals reach `pnpm` directly

#### Scenario: mutually exclusive flags rejected

- **WHEN** the operator runs `paca dashboard --build --start`
- **THEN** the CLI prints an error and exits non-zero without invoking `pnpm`

### Requirement: `paca run-workflow` runs a workflow's manual entrypoint

`paca run-workflow <name>` SHALL load `configs/workflows/<name>.yaml`, resolve its `extra.run_now` factory, call it, and print the JSON result. A workflow without `extra.run_now` set SHALL raise a clear error rather than silently no-op.

#### Scenario: dashboard triggers a manual re-index

- **WHEN** the operator (or the dashboard's re-index action) runs `paca run-workflow knowledge_ingest`
- **THEN** the CLI resolves and calls the workflow's `extra.run_now` entrypoint and prints its JSON result

#### Scenario: workflow has no manual entrypoint

- **WHEN** the operator runs `paca run-workflow <name>` for a workflow without `extra.run_now`
- **THEN** the CLI raises `RuntimeError("manual run is not implemented for workflow: <name>")`

### Requirement: `paca knowledge` subcommand group manages ingestion and GBrain

The `paca knowledge` subcommand group SHALL expose: `ingest <value>` (route a URL or staged local file through the knowledge-ingest pipeline, with `--ingest/--no-ingest` to control whether the clean markdown is imported into GBrain, `--category` to pin the destination taxonomy path and skip auto-classification, and `--progress` to emit one JSON event per pipeline step to stdout followed by the final JSON result); `gbrain-search <query> [--limit N]` (search GBrain through the local CLI bridge and print JSON results); `gbrain-ingest <path>` (import a markdown file or directory into GBrain through the local CLI bridge and print the JSON result); `init-test-gbrain [--home PATH]` (initialize an isolated local GBrain PGLite database under `state/test-gbrain` by default, for integration tests); and `review` (reconcile the wiki against `knowledge_reviews` — enroll docs with no row, unenroll rows whose file is gone — and print the counts of docs enrolled, unenrolled, and currently due; no flags, no LLM call, since the review card reuses each doc's frontmatter summary).

#### Scenario: operator ingests a URL

- **WHEN** the operator runs `paca knowledge ingest https://example.com/article`
- **THEN** the CLI runs the knowledge-ingest pipeline and prints the JSON result, importing into GBrain unless `--no-ingest` is passed

#### Scenario: progress events stream as JSONL

- **WHEN** the operator runs `paca knowledge ingest <value> --progress`
- **THEN** the CLI writes one JSON event per pipeline step to stdout, followed by a final JSON result line, forming valid JSONL

#### Scenario: operator searches GBrain from the CLI

- **WHEN** the operator runs `paca knowledge gbrain-search "topic" --limit 5`
- **THEN** the CLI prints the search results as indented JSON

#### Scenario: operator reconciles review enrollment

- **WHEN** the operator runs `paca knowledge review`
- **THEN** the CLI enrolls wiki docs that have no review row, unenrolls rows whose file is gone, and prints the enrolled, unenrolled, and due counts

### Requirement: `paca info-radar recap` generates a range recap

`paca info-radar recap --since YYYY-MM-DD --until YYYY-MM-DD [--min-score N] [--novel-only] [--regenerate]` SHALL run the info-radar-recap workflow over the requested range and quality gate, and print the resulting headline plus one line per theme with its citation count. Without `--regenerate`, a request whose recap already exists in `status='done'` SHALL print the cached recap and make no LLM call. With `--regenerate`, the recap SHALL be recomputed and the stored row replaced. Both `--since` and `--until` are required; an inverted or unparseable range SHALL exit non-zero without invoking the agent. A range in which no item clears the quality gate SHALL print an explicit empty-result message and exit zero.

#### Scenario: operator generates a weekly recap

- **WHEN** the operator runs `paca info-radar recap --since 2026-07-13 --until 2026-07-19`
- **THEN** the CLI selects kept analyses in that local-date range, generates the recap, persists it, and prints the headline followed by each theme title and its citation count

#### Scenario: repeat invocation is served from cache

- **WHEN** the operator re-runs the same `paca info-radar recap` command for a range already recapped with `status='done'`
- **THEN** the CLI prints the stored recap and makes no LLM call

#### Scenario: regeneration forces recompute

- **WHEN** the operator runs the same command with `--regenerate`
- **THEN** the recap is recomputed and the existing row for that key is replaced rather than duplicated

#### Scenario: empty range exits cleanly

- **WHEN** the operator requests a recap for a range where no item clears the quality gate
- **THEN** the CLI prints an explicit empty-result message, writes no row, and exits zero

#### Scenario: inverted range is rejected

- **WHEN** the operator runs `paca info-radar recap --since 2026-07-19 --until 2026-07-13`
- **THEN** the CLI exits non-zero reporting the invalid range, and no agent is invoked

