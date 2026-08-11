## ADDED Requirements

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
