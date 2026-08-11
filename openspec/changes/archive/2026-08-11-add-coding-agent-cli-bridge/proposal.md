## Why

next-signal can call ordinary model APIs but cannot delegate a repository task to the locally installed Codex or Claude Code agent CLIs. Adding a bounded CLI bridge lets operator workflows reuse those agents' native repository tools and existing local authentication without misrepresenting them as agno model providers.

## What Changes

- Add a configurable coding-agent integration that invokes installed `codex` and `claude` executables as child processes.
- Support one-shot, machine-readable runs through `codex exec --json` and `claude -p --output-format stream-json`, with a stable next-signal event envelope and final result.
- Add explicit review and edit execution profiles, allowed-working-root validation, bounded output, timeouts, child-process cleanup, and a minimal subprocess environment.
- Add `next-signal coding-agent doctor` and `next-signal coding-agent run` operator commands, including optional JSONL progress output.
- Add live coding-agent selections: required model, reasoning effort, and Standard/Fast service tier for Codex, plus optional model and thinking effort for Claude Code. Persist them in next-signal state and apply them at call time without modifying either provider's configuration.
- Install exact, overridable Codex CLI and Claude Code CLI versions in the official Docker image, and persist their provider-owned authentication homes in separate named volumes shared by the Dashboard and scheduler.
- Add bilingual Dashboard settings and connection controls for both providers. The connection surface starts only hard-coded provider login/status/logout commands, relays the bounded interactive login exchange, and never accepts arbitrary commands, argv, or environment variables from the browser.
- Keep Dashboard repository-task execution jobs, persistent conversations, Codex app-server, and unrestricted permission modes out of scope.

## Capabilities

### New Capabilities

- `coding-agent-cli-bridge`: Configured, safe, streaming invocation of Codex CLI and Claude Code CLI as external repository-task workers.

### Modified Capabilities

- `core-cli`: Add operator commands for checking and running configured coding-agent CLIs.

## Impact

- Adds coding-agent configuration and strict config schemas.
- Adds provider adapters and subprocess supervision under `src/next_signal/integrations/coding_agents/`.
- Extends `src/next_signal/interfaces/cli.py` with a new command group.
- Adds a small runtime preference reader plus Dashboard server action and settings-page controls backed by `~/.next-signal/coding-agents.json`.
- Adds fixture-driven bridge and authentication-broker tests with fake executables; normal unit tests will not call real provider services.
- Updates the English and Chinese operator/development documentation for installation, authentication, permissions, and command usage.
- Introduces no required third-party Python dependency. The external binaries remain optional for host installs and fail clearly at call time when absent; the official Docker image contains pinned versions.
