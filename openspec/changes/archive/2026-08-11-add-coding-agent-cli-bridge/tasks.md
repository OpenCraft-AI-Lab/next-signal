## 1. Configuration and contracts

- [x] 1.1 Add failing config tests for strict coding-agent YAML validation, default profile resolution, relative allowed-root resolution, and invalid profile references.
- [x] 1.2 Add coding-agent Pydantic schemas and `load_coding_agents()` to `core.config`, keeping provider discovery lazy.
- [x] 1.3 Add `configs/coding_agents.yaml` with `PROJECT_ROOT` confinement, bounded runtime/output settings, safe environment names, and shipped `review`/`edit` profiles that cannot select unrestricted provider modes.
- [x] 1.4 Add internal typed event, terminal result, provider, and run-request contracts for the integration.

## 2. Provider adapters

- [x] 2.1 Add temporary executable fixtures for Codex and Claude success streams that record argv, cwd, stdin, and inherited environment for real subprocess assertions.
- [x] 2.2 Implement call-time `CODEX_BIN`/`CLAUDE_BIN` resolution with `PATH` fallback and clear missing-binary errors.
- [x] 2.3 Implement and test the Codex argv builder and JSONL parser for `exec --json --ephemeral -`, review/edit sandboxes, thread ID, final text, usage, and terminal status.
- [x] 2.4 Implement and test the Claude argv builder and JSONL parser for `-p` stream-json, `dontAsk` allowed tools, no session persistence, session ID, final text, usage, and terminal status.
- [x] 2.5 Add provider parser tests for malformed JSON, oversized events, missing terminal events, stderr diagnostics, and non-zero exits.

## 3. Safe subprocess runner

- [x] 3.1 Add failing tests for resolved working-root confinement, `..` traversal, symlink escape, prompt metacharacters on stdin, and exclusion of unlisted parent secrets.
- [x] 3.2 Implement workspace validation and a minimal child environment assembled from the safe baseline plus configured provider environment names.
- [x] 3.3 Implement the shared `asyncio.create_subprocess_exec` runner with concurrent stdout/stderr draining, event streaming, bounded retained diagnostics, duration, and exactly one terminal result.
- [x] 3.4 Implement and test wall-clock timeout and cancellation cleanup using process-group termination followed by bounded forced kill.
- [x] 3.5 Verify provider failures do not retry, cross-provider fallback, persist sessions, or create session mappings.

## 4. Operator CLI

- [x] 4.1 Add CLI tests for `coding-agent doctor` covering valid fixture versions, missing enabled binaries, invalid configuration, status output, and exit codes without model requests.
- [x] 4.2 Add the `coding-agent` Typer group and implement `doctor` using only lazy configuration, executable resolution, and version checks.
- [x] 4.3 Add CLI tests for explicit provider/cwd validation, review default, edit selection, unknown provider/profile rejection, and success/failure exit codes.
- [x] 4.4 Implement `coding-agent run <provider> <prompt> --cwd <path> [--profile <name>] [--progress]`, printing one final JSON result normally or valid event-plus-result JSONL with progress enabled.

## 5. Documentation and verification

- [x] 5.1 Document CLI installation prerequisites, saved-login behavior, Claude inherited versus bare context, permission profiles, environment isolation, and command examples in the relevant English README/docs pages.
- [x] 5.2 Apply the same documentation changes to the corresponding Chinese README/docs pages in the same change.
- [x] 5.3 Run the targeted config, integration, and CLI tests with `uv run pytest`, then run the full test suite and relevant Ruff checks.
- [x] 5.4 Run `openspec validate --all`, confirm `openspec status --change add-coding-agent-cli-bridge` is complete, and record any external CLI version assumptions discovered during implementation.

## 6. Configurable Codex defaults

- [x] 6.1 Add failing backend tests for absent, valid, and malformed runtime preferences plus exact Codex model, effort, and service-tier argv overrides.
- [x] 6.2 Implement strict call-time Codex preference loading from next-signal state and apply the selected values without changing provider-owned config.
- [x] 6.3 Add Dashboard preference read/write actions and bilingual model, effort, and Standard/Fast controls to the existing settings page.
- [x] 6.4 Add focused frontend/backend tests and update the corresponding English and Chinese operator documentation.
- [x] 6.5 Run focused tests, full Python and Dashboard checks, containerized UI/runtime verification, Ruff, and OpenSpec validation.

## 7. Configurable Claude defaults

- [x] 7.1 Extend the runtime preference and adapter tests for absent, valid, and malformed Claude model/effort values plus exact `--model` and `--effort` argv injection.
- [x] 7.2 Load Claude preferences at call time and apply them without changing Claude-owned settings or authentication.
- [x] 7.3 Add bilingual Claude model and thinking-effort controls, make Codex selections explicit without inherit choices, and preserve the other provider on independent saves.
- [x] 7.4 Update the English and Chinese Dashboard/operator documentation and focused frontend tests.
- [x] 7.5 Run focused and full Python/Dashboard checks, Docker runtime verification, Ruff, and OpenSpec validation.

## 8. Containerized CLIs and provider login

- [x] 8.1 Extend the proposal, design, and capability deltas for pinned container CLIs, provider-owned auth volumes, and the allowlisted Dashboard authentication boundary.
- [x] 8.2 Add failing authentication-broker tests with fixture executables for fixed argv, status, interactive input, URL allowlisting, timeout/cancellation, and bounded output.
- [x] 8.3 Implement the PTY-backed authentication broker and narrow CLI status/session commands without a shell, arbitrary browser argv, persistent transcripts, or credential copying.
- [x] 8.4 Install exact Codex CLI and Claude Code CLI versions plus repository-agent prerequisites in the Docker image, disable in-container auto-update, and mount separate persistent auth volumes in Dashboard and scheduler.
- [x] 8.5 Add same-origin Dashboard auth endpoints and bilingual connection/status/cancel/disconnect controls with browser-open plus copy-link fallbacks.
- [x] 8.6 Document image upgrades, one-time UI and terminal login, auth-volume lifecycle, loopback binding, remote reverse-proxy requirements, and recovery in English and Chinese.
- [x] 8.7 Run focused Python/Dashboard tests, full suites, typecheck/lint/build, strict OpenSpec validation, Compose config validation, image build, CLI version checks, and a fixture-backed container login smoke test without contacting provider services.
