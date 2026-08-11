## Context

next-signal currently invokes ordinary agno models through `core.models` and several bounded external CLIs through integration adapters. Codex CLI and Claude Code CLI are different from ordinary chat-model providers: each owns an agent loop, repository context, file editing, shell execution, permissions, and session metadata. Treating either CLI as an agno `Model` would nest two agent runtimes and blur which layer controls tools and safety.

The first execution consumer is the local operator CLI. The Dashboard may configure call-time Codex and Claude defaults and establish the provider-owned login used by the Docker services, but adding a Dashboard repository-task execution surface would also require durable jobs, cancellation, and an approval UX, so execution remains a separate concern. Both provider binaries and their authentication are optional local prerequisites on a host install; their absence must not affect unrelated next-signal startup or workflows. The official Docker image includes pinned binaries so a deployed stack has a reproducible execution surface.

## Goals / Non-Goals

**Goals:**

- Invoke locally installed Codex and Claude Code CLIs as explicit external repository-task workers.
- Provide one-shot, streaming, machine-readable execution with a stable next-signal result contract.
- Make the working directory, permissions, environment, timeout, and output bounds explicit and testable.
- Reuse existing local CLI authentication without copying provider credential files into next-signal state.
- Make the official Docker deployment self-contained by installing exact CLI versions and persisting each provider's own authentication directory outside the image.
- Let a local Dashboard operator establish, inspect, cancel, and remove container CLI authentication without exposing a general-purpose command runner.
- Let an operator change the Codex model, reasoning effort, and Standard/Fast tier, plus the Claude model and thinking effort, from the Dashboard without editing provider-owned settings or restarting next-signal.
- Fit the repository's `interfaces -> integrations -> core` dependency direction and fail loudly on provider or protocol errors.

**Non-Goals:**

- Implement an agno model provider, register an agent-facing tool, or allow recursive agent-to-coding-agent delegation.
- Add a Dashboard coding-job UI, background job database, multi-user authorization, or remote repository-task execution.
- Implement persistent/resumable conversations, Codex app-server, Claude Agent SDK, or interactive approval callbacks.
- Enable Codex `danger-full-access` or Claude `bypassPermissions` on the host.
- Automatically update either CLI, copy host credentials, persist credentials in next-signal state, or expose raw credential material to the browser.

## Decisions

### 1. Use a dedicated integration, not the model or tool layers

The implementation will live under `src/next_signal/integrations/coding_agents/`. The Typer interface calls it directly. No entry is added to `core.models`, `registry.py`, or an agent YAML tool list.

This preserves the distinction between a model completion and an autonomous repository worker. A future workflow or tool can wrap the integration in a separate change once its authorization and recursion rules are known.

### 2. Use each provider's supported one-shot CLI mode

Codex runs through `codex exec --json --ephemeral -`; the selected profile supplies `--sandbox read-only` or `--sandbox workspace-write`. Claude runs through `claude -p --output-format stream-json --verbose --include-partial-messages --no-session-persistence`; the selected profile supplies `--permission-mode dontAsk` and explicit allowed tools.

Codex app-server is rejected for this phase because its thread/turn JSON-RPC protocol, approvals, and long-lived lifecycle solve a richer embedded-client problem. Provider SDKs are also rejected because the requested capability is local CLI reuse, next-signal is Python-first, and the one-shot CLI protocols already provide JSONL.

### 3. Keep provider authentication and context provider-owned

The bridge resolves `CODEX_BIN` or `CLAUDE_BIN` at call time, falling back to `PATH`, and runs under the current OS user so the CLI can use its existing saved login. It will not copy `~/.codex`, `~/.claude`, keychain data, or auth files into next-signal state.

On host installs, login remains an operator prerequisite. In Docker, the image uses `HOME=/root`, mounts `/root/.codex` and `/root/.claude` as distinct named volumes, and lets the provider CLIs create and own their normal files there. The Dashboard and scheduler mount the same volumes so an authenticated login is available to subsequent bridge calls. Image rebuilds therefore preserve login, while explicit volume removal intentionally removes it.

Claude's inherited local context remains enabled by default so subscription login and repository `CLAUDE.md` behavior match a manual CLI run. A configuration flag may add `--bare` for API-key automation, but next-signal will document that bare mode does not use Claude subscription OAuth. Codex user config inheritance is likewise explicit in configuration rather than silently replaced.

### 4. Put tunable execution policy in strict YAML

`configs/coding_agents.yaml` will define allowed working roots, provider enablement, timeouts, output limits, inherited environment-variable names, provider context flags, and named `review`/`edit` profiles. A strict Pydantic schema and loader will be added to `core.config`; unknown keys fail when coding-agent configuration is loaded.

Relative allowed roots resolve from `PROJECT_ROOT`. The shipped configuration allows only `PROJECT_ROOT`. Provider binaries remain optional: configuration can load and the rest of next-signal can start when they are absent.

The default profile is `review`. The shipped edit profile permits Codex `workspace-write`; Claude stays in `dontAsk` and receives only the configured file and command allowlist. Unsafe provider modes are not representable by the shipped schema in this change.

### 5. Supervise the process asynchronously without a shell

The common runner will use `asyncio.create_subprocess_exec`, an argv array, stdin for the prompt, and pipes for stdout/stderr. It will never construct a shell command. Stdout and stderr are drained concurrently so a verbose provider cannot deadlock the child.

The runner starts a separate process group on supported POSIX systems. On timeout or cancellation it sends a graceful termination, waits for a short fixed grace period, then kills the process group. The primary supported host is the project's existing macOS environment; other platforms receive best-effort direct child termination without broadening this change into a portability project.

The subprocess environment is built from an explicit safe baseline plus provider-specific environment names listed in YAML. Arbitrary next-signal secrets are not inherited. The list contains names, never secret values; values are read at call time.

### 6. Validate the resolved workspace before spawning

The requested `--cwd` is mandatory. The bridge resolves symlinks, requires an existing directory, and verifies that the resolved path equals or is below one configured allowed root. Validation happens before binary resolution or process creation. This prevents `..` and symlink traversal from expanding the coding agent's intended scope.

### 7. Expose a small stable envelope and retain raw provider events

Provider adapters parse their JSONL and extract the session/thread ID, final assistant text, usage, and terminal status. Progress output uses two stable envelope types:

```json
{"type":"event","provider":"codex","session_id":"...","event":{}}
{"type":"result","ok":true,"provider":"codex","session_id":"...","text":"...","usage":{}}
```

The raw provider object stays under `event`; the bridge will not invent a lossy cross-provider command/file-change taxonomy in the MVP. The final result also carries return code, duration, timeout status, and a bounded stderr tail. Invalid JSONL, an oversized event, missing terminal output, or an unsupported provider event sequence fails loudly as a protocol error.

Without `--progress`, the CLI suppresses intermediate envelopes and prints only the final result as JSON. With `--progress`, every stdout line is one JSON object and the final line is always the result envelope. Provider diagnostics go to captured stderr, not mixed into JSONL stdout.

### 8. Do not retry, fall back, or resume implicitly

The bridge performs one provider invocation. A Codex failure never falls back to Claude, and vice versa. Both commands disable session persistence, and this change exposes no `resume` or `--last` behavior. This avoids cross-job session confusion and makes cost, permissions, and failure ownership explicit.

### 9. Test against fixture executables

Unit tests create temporary executable fixtures that emit representative Codex and Claude JSONL, malformed output, large lines, stderr, non-zero exits, and hangs. Tests call the real runner with those executables and temporary workspaces rather than mocking `asyncio` subprocess APIs. No ordinary test invokes a real provider or requires provider authentication.

### 10. Keep live coding-agent defaults in next-signal runtime state

Static safety policy stays in strict `configs/coding_agents.yaml`; operator-tunable selections live in `~/.next-signal/coding-agents.json`, the same runtime-state pattern used by content language and scheduling. A configured Codex section must contain all three fields (`model`, `model_reasoning_effort`, and `service_tier`); next-signal deliberately supplies no model or effort default because provider defaults change over time. Until the operator explicitly saves all three, Codex invocation fails before spawn. The Claude section has two optional fields (`model` and `effort`); missing Claude fields preserve the CLI's own configuration and defaults, and Claude runs remain independent of Codex configuration.

The backend reads and validates this file at each provider invocation. For a configured Codex run it always passes `model` with `--model`, reasoning effort through an explicit `--config` override, and service tier through an explicit override; Fast also enables the stable `fast_mode` feature. For Claude it passes model and effort through the documented per-session `--model` and `--effort` flags when selected. Codex effort values are `minimal`, `low`, `medium`, `high`, and `xhigh`; Claude effort values are `low`, `medium`, `high`, `xhigh`, and `max`; Codex service tier is `default` or `fast`. The Dashboard writes atomically and renders a malformed file as unconfigured Codex plus inherited Claude values with a logged error so the settings page remains available to repair it, while the invocation path fails loudly rather than silently using different next-signal settings.

The Dashboard setting does not edit `~/.codex/config.toml` or `~/.claude/settings.json`. This avoids corrupting provider-owned state, keeps next-signal preferences portable inside its own state root, and makes removal a single-file rollback.

### 11. Install pinned CLIs in the official image

The Dockerfile installs exact build-argument versions of `@openai/codex` and `@anthropic-ai/claude-code` in a Node build stage, then copies only their package directories and launchers into the runtime image. Defaults are the versions verified by this change, and Compose exposes explicit build arguments so upgrades are deliberate. The runtime disables Claude Code's auto-updater; image rebuilds, not in-container mutation, own upgrades. Host installations remain unchanged and optional.

The runtime also includes the small command-line prerequisites expected by repository agents (`bash`, `git`, and `ripgrep`). The build verifies both version commands, and runtime verification uses `next-signal coding-agent doctor` without making a model request.

### 12. Put an allowlisted authentication broker behind the Dashboard

The browser never supplies a command, executable path, argv, working directory, or environment. It selects only `codex` or `claude`; a server-side broker maps that enum to fixed commands: Codex device login/status/logout and Claude subscription login/status/logout. The broker launches without a shell, allocates a pseudo-terminal for interactive provider behavior, bounds output and wall-clock duration, permits at most one active login per provider, and terminates the child process group on cancellation or timeout.

The broker emits an in-memory, normalized event stream for the current login only. It strips terminal control sequences, recognizes only HTTPS login URLs on an explicit provider-domain allowlist, accepts a single bounded line of interactive input when Claude requests the browser authorization code, and never writes the transcript, URL, code, token, or credentials to application logs or persistent state. Provider files remain in their named volumes.

Dashboard endpoints are same-origin only and the Compose Dashboard port binds to loopback by default. A deployment that intentionally publishes the Dashboard beyond the host must add its own authenticated reverse proxy before exposing these state-changing endpoints. The settings UI opens the provider URL when the browser permits it, always shows a copyable fallback link, polls the bounded session state, and provides cancel/disconnect controls.

## Risks / Trade-offs

- **Provider JSONL changes across CLI releases** -> Keep parsing provider-specific, retain raw events, fail on incompatible terminal sequences, and report the detected CLI version in `coding-agent doctor`.
- **Inherited Claude hooks, plugins, or repository instructions change behavior** -> Document inherited mode, keep `--bare` opt-in for API-key automation, and never claim the bridge itself creates a hermetic Claude environment.
- **A coding agent can execute untrusted repository code** -> Default to review, require an explicit edit profile, restrict working roots and environment inheritance, and exclude unrestricted permission modes.
- **Timeout leaves descendants running** -> Use a process group, graceful termination, and forced kill after a bounded grace period.
- **Large event streams consume memory or flood Dashboard consumers** -> Stream events instead of collecting them all, bound individual events and retained diagnostics, and abort on configured limits.
- **Saved user authentication is unavailable in containers** -> Fail at run time with provider stderr and document explicit login/API-key provisioning; do not silently switch credentials.
- **A remote browser could trigger container login/logout** -> Bind the Dashboard to loopback by default, require same-origin state-changing requests, and document that remote publication requires an authenticated reverse proxy.
- **An authentication prompt leaks a token through logs or state** -> Keep its normalized transcript in process memory only, redact control sequences, never log browser input, and leave credentials exclusively in provider-owned volumes.
- **Provider login prompts change across CLI releases** -> Pin image versions, use a PTY rather than prompt-text automation, retain a fallback URL/input UI, and fail closed when a discovered URL is outside the provider allowlist.
- **A selected model does not support a chosen effort or Fast tier** -> Pass the explicit settings once and surface provider behavior; next-signal does not reinterpret the selection. Claude Code may cap an unsupported effort to the nearest supported level according to its own model compatibility rules.

## Migration Plan

1. Add the strict configuration with safe shipped defaults and optional providers.
2. Add the integration and fixture tests without exposing it to agents or the Dashboard.
3. Add the CLI group and doctor checks.
4. Update English and Chinese documentation, then validate the OpenSpec change and test suite.
5. Add the optional runtime preference file and Dashboard controls; existing installs with no file must explicitly configure Codex before using it and continue inheriting Claude user configuration.
6. Add pinned provider CLIs, separate auth volumes, the bounded authentication broker, and bilingual Dashboard connection controls; rebuild the image and log in once per provider volume.

There is no data migration and no existing command changes. Rollback removes the new command group, integration package, configuration file, and documentation; unrelated startup remains unaffected because provider discovery occurs only in coding-agent commands.

## Open Questions

None blocking. Dashboard repository-task execution jobs, explicit session resume, isolated Git worktrees, and agent-facing tool exposure require separate proposals because each changes the authorization and lifecycle model.

## Implementation Notes

The non-model smoke check used Codex CLI `0.145.0` and Claude Code `2.1.220`.
Both installed versions expose every flag used by the adapters. The bridge does
not enforce those exact versions: `coding-agent doctor` reports the installed
version, fixture tests pin the JSONL contract, and an incompatible event stream
fails loudly instead of being accepted or routed to the other provider.
