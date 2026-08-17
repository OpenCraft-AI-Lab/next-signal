## MODIFIED Requirements

### Requirement: `next-signal doctor` self-checks the environment

`next-signal doctor` SHALL verify `.env` system connection configuration, the
presence of each required credential in the credential store, the local model
endpoints recorded in user state (checking that they are configured, not that
they are reachable), Postgres reachability, the presence of every registered
tool, the GBrain CLI / service health **and whether GBrain is initialised and
able to embed**, and the folocli authentication (`FOLO_TOKEN` present in the
store and `folocli whoami` returns `ok: true`), reporting each check as ✓ or ✗.

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

- **WHEN** `ANTHROPIC_API_KEY` is absent from the credential store
- **THEN** `next-signal doctor` reports a ✗ for the corresponding check, points
  at the settings page, and exits non-zero

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
