## ADDED Requirements

### Requirement: Codex invocation applies live operator defaults

The bridge SHALL require Codex `model`, `model_reasoning_effort`, and `service_tier` values in next-signal runtime state at call time and SHALL define no implicit values for them. The model SHALL be passed as an explicit model selection, reasoning effort and service tier SHALL be passed as explicit Codex configuration overrides, and Fast service tier SHALL additionally enable Fast mode.

#### Scenario: All Codex defaults are configured

- **WHEN** runtime state selects model `gpt-5.6-sol`, reasoning effort `high`, and service tier `fast`
- **THEN** the spawned Codex argv explicitly selects that model, effort, Fast tier, and Fast-mode feature

#### Scenario: Runtime preferences are absent

- **WHEN** no Codex runtime preference file exists
- **THEN** the bridge reports that explicit Codex settings are required and does not spawn Codex

### Requirement: Claude invocation applies live operator defaults

The bridge SHALL read optional Claude `model` and `effort` values from next-signal runtime state at call time. Configured values SHALL be passed through the Claude Code CLI's per-session `--model` and `--effort` flags. Missing values SHALL continue to inherit Claude Code's own configuration and model defaults.

#### Scenario: Claude model and effort are configured

- **WHEN** runtime state selects Claude model `opus` and effort `xhigh`
- **THEN** the spawned Claude argv contains `--model opus --effort xhigh`

#### Scenario: Claude defaults are inherited

- **WHEN** the Claude runtime preferences contain no model or effort
- **THEN** the bridge adds no Claude model or effort flag

### Requirement: Coding-agent runtime preferences are strict and provider-owned config is untouched

The runtime preference reader SHALL accept only bounded model identifiers, Codex reasoning effort `minimal`, `low`, `medium`, `high`, or `xhigh`, Claude effort `low`, `medium`, `high`, `xhigh`, or `max`, and Codex service tier `default` or `fast`. A malformed file or unsupported value SHALL fail the requested provider invocation before provider spawn. Saving next-signal preferences SHALL NOT edit Codex- or Claude-owned configuration or authentication files.

#### Scenario: Unsupported effort fails before spawn

- **WHEN** runtime state contains an unsupported reasoning-effort value
- **THEN** the bridge reports the invalid field and does not spawn the requested provider

### Requirement: Dashboard exposes bilingual coding-agent defaults

The Dashboard settings page SHALL show required Codex model, reasoning-effort, and speed controls plus optional Claude model and thinking-effort controls in both supported interface languages, read their initial values from next-signal runtime state, and save them atomically without replacing the other provider's saved values. Claude controls SHALL support an inherit choice; Codex controls SHALL show no inherit choice and SHALL not save until all fields are explicit. A malformed state file SHALL be logged and rendered as unconfigured Codex plus inherited Claude values so the operator can repair it from the same page.

#### Scenario: Operator saves Codex defaults

- **WHEN** the operator chooses a model, effort, and Fast speed and saves the settings
- **THEN** the Dashboard atomically writes the validated next-signal runtime preference file and subsequent Codex runs use those values

#### Scenario: Codex is not configured yet

- **WHEN** no saved Codex section exists
- **THEN** the Dashboard shows required empty controls and Codex runs fail before spawn until the operator saves explicit selections

#### Scenario: Operator saves Claude defaults

- **WHEN** the operator chooses a Claude model and thinking effort and saves the settings
- **THEN** the Dashboard atomically preserves both provider sections and subsequent Claude runs use those values

### Requirement: Coding-agent providers are optional and resolved at call time

The coding-agent bridge SHALL support the provider names `codex` and `claude`. It SHALL resolve an executable from `CODEX_BIN` or `CLAUDE_BIN` when configured in the process environment and otherwise from `PATH`; a missing executable SHALL affect only coding-agent doctor or run commands and SHALL NOT prevent unrelated next-signal imports, startup, agents, or workflows.

#### Scenario: Configured binary override is used

- **WHEN** `CODEX_BIN` points to an executable fixture and a Codex run is requested
- **THEN** the bridge invokes that exact executable instead of another `codex` found on `PATH`

#### Scenario: Missing provider does not break startup

- **WHEN** neither coding-agent executable is installed
- **THEN** unrelated next-signal commands and AgentOS startup still load successfully

### Requirement: Coding-agent configuration is strict and explicit

The bridge SHALL load `configs/coding_agents.yaml` through a strict schema defining allowed working roots, provider settings, timeouts, output bounds, inherited environment-variable names, and named execution profiles. Unknown keys or invalid profile references SHALL fail loudly when a coding-agent command loads the configuration.

#### Scenario: Unknown configuration key is rejected

- **WHEN** `configs/coding_agents.yaml` contains an unknown key
- **THEN** the coding-agent command exits with a validation error naming that key before spawning a provider

### Requirement: Working directories are confined to allowed roots

Before spawning a provider, the bridge SHALL resolve the requested working directory and configured roots, require the working directory to exist as a directory, and require it to equal or be a descendant of at least one allowed root. Symlink and `..` traversal SHALL be evaluated after resolution.

#### Scenario: Workspace below an allowed root is accepted

- **WHEN** the resolved working directory is below a configured allowed root
- **THEN** workspace validation succeeds and provider invocation may proceed

#### Scenario: Symlink escape is rejected

- **WHEN** the requested working directory is a symlink whose resolved target is outside every allowed root
- **THEN** the bridge returns a workspace validation error without spawning a provider

### Requirement: Review is the safe default execution profile

The bridge SHALL default to the named `review` profile when no profile is requested. The shipped review profile SHALL keep Codex in `read-only` sandbox mode and SHALL run Claude in `dontAsk` mode without mutation tools. The shipped `edit` profile SHALL use Codex `workspace-write` and SHALL grant Claude only its configured file tools and command patterns. The shipped configuration SHALL NOT enable Codex `danger-full-access` or Claude `bypassPermissions`.

#### Scenario: Omitted profile cannot edit

- **WHEN** the operator starts either provider without selecting a profile
- **THEN** the generated provider argv uses the shipped review restrictions

#### Scenario: Edit profile is explicit and bounded

- **WHEN** the operator selects the shipped edit profile
- **THEN** Codex receives `workspace-write` or Claude receives only the edit profile's allowed tools and commands, without an unrestricted permission flag

### Requirement: Providers use supported one-shot JSONL modes

The Codex adapter SHALL invoke non-interactive `codex exec` with JSON output, stdin prompt input, the selected sandbox, and ephemeral session storage. The Claude adapter SHALL invoke non-interactive `claude -p` with stream-JSON output, verbose streaming, partial messages, stdin prompt input, no session persistence, and the selected permission/tool policy.

#### Scenario: Codex argv selects exec JSON mode

- **WHEN** a Codex run starts under the review profile
- **THEN** the executable receives `exec`, `--json`, `--ephemeral`, stdin prompt selection, and `--sandbox read-only`

#### Scenario: Claude argv selects print stream mode

- **WHEN** a Claude run starts under the review profile
- **THEN** the executable receives `-p`, `--output-format stream-json`, `--verbose`, `--include-partial-messages`, `--no-session-persistence`, and the configured permission flags

### Requirement: Subprocess execution is bounded and does not use a shell

The bridge SHALL execute an argv array without a shell, send the prompt through stdin, drain stdout and stderr concurrently, and construct the child environment from an explicit allowlist. It SHALL enforce the configured wall-clock timeout and terminate the child process group, escalating to a forced kill after a bounded grace period when necessary.

#### Scenario: Prompt metacharacters are data

- **WHEN** a prompt contains shell metacharacters, substitutions, or quoted commands
- **THEN** those characters are delivered unchanged on provider stdin and no intermediate shell interprets them

#### Scenario: Timed-out run is terminated

- **WHEN** a fixture provider exceeds the configured timeout
- **THEN** the bridge terminates the provider process group and returns a timed-out failure result

#### Scenario: Unlisted secret is not inherited

- **WHEN** the parent process contains a secret environment variable absent from the provider environment allowlist
- **THEN** the provider child does not receive that variable

### Requirement: Provider events use a stable next-signal envelope

The bridge SHALL parse provider JSONL and emit event envelopes containing `type: "event"`, the provider name, the known session or thread ID, and the original provider event. It SHALL emit exactly one terminal result envelope containing `type: "result"`, `ok`, provider, session ID when known, final text, usage when available, return code, duration, timeout status, and a bounded stderr tail.

#### Scenario: Successful Codex stream produces a terminal result

- **WHEN** a Codex fixture emits a thread ID, agent message, usage, and successful terminal event
- **THEN** the bridge emits event envelopes followed by one successful result containing the extracted thread ID, text, and usage

#### Scenario: Successful Claude stream produces a terminal result

- **WHEN** a Claude fixture emits a session ID, streamed messages, and a successful result event
- **THEN** the bridge emits event envelopes followed by one successful result containing the extracted session ID, text, and usage

### Requirement: Protocol and provider failures fail loudly without fallback

The bridge SHALL treat malformed JSONL, oversized events, missing terminal output, timeout, executable failure, and non-zero provider exit as explicit failures. It SHALL NOT retry with or fall back to the other provider, and it SHALL retain only configured bounded diagnostics.

#### Scenario: Malformed provider output is rejected

- **WHEN** a provider writes a non-JSON line to its JSONL stdout
- **THEN** the bridge returns a protocol failure identifying the provider and does not report success

#### Scenario: Provider failure does not switch providers

- **WHEN** Codex exits non-zero
- **THEN** the result reports the Codex failure and Claude is not invoked

### Requirement: Runs do not persist or resume bridge sessions

Each bridge invocation SHALL be one-shot and SHALL disable provider session persistence where the provider supports it. The bridge SHALL NOT expose implicit last-session resume or store provider session mappings in this change.

#### Scenario: Consecutive runs are independent

- **WHEN** two runs target the same provider and workspace
- **THEN** each provider argv requests non-persistent execution and neither run resumes the other

### Requirement: The official Docker image contains pinned coding-agent CLIs

The official Docker image SHALL install exact, overridable build-argument versions of Codex CLI and Claude Code CLI, SHALL verify both launchers during the image build, and SHALL disable in-container Claude Code auto-update. Host installations SHALL continue to treat both executables as optional call-time dependencies.

#### Scenario: Default image is self-contained

- **WHEN** the official image is built with its default arguments
- **THEN** `next-signal coding-agent doctor` resolves the pinned Codex and Claude launchers without downloading packages at container startup

#### Scenario: Operator deliberately upgrades a CLI

- **WHEN** an operator rebuilds with an explicit supported CLI version build argument
- **THEN** the resulting image installs that exact requested version rather than an unbounded latest release

### Requirement: Container authentication remains provider-owned and persistent

The Docker deployment SHALL mount separate named volumes at the provider-standard Codex and Claude authentication homes for every service that invokes those CLIs. Credentials SHALL NOT be baked into the image, copied from the host, written to next-signal state, returned by Dashboard endpoints, or stored in Dashboard logs. Rebuilding or replacing a container SHALL preserve authentication while removing the corresponding named volume SHALL remove it.

#### Scenario: Login survives an image rebuild

- **WHEN** a provider login has populated its named auth volume and the Dashboard or scheduler container is recreated
- **THEN** the replacement container sees the same provider-owned login files

#### Scenario: Application state is inspected

- **WHEN** the next-signal state volume is inspected after provider login
- **THEN** it contains no copied provider credential or login transcript

### Requirement: Dashboard authentication commands are fixed and bounded

The Dashboard authentication API SHALL accept only a provider enum and bounded interactive input. Server code SHALL map the provider to fixed login, status, and logout argv, execute without a shell in a pseudo-terminal where login is interactive, allow at most one active session per provider, enforce time and output limits, and terminate the provider process group on cancellation or timeout. No request SHALL select an executable, argv, shell command, working directory, or environment variable.

#### Scenario: Operator starts Codex login

- **WHEN** a same-origin Dashboard request starts login for `codex`
- **THEN** the broker invokes only `codex login --device-auth` and returns normalized in-memory session state

#### Scenario: Operator starts Claude login

- **WHEN** a same-origin Dashboard request starts login for `claude`
- **THEN** the broker invokes only `claude auth login --claudeai` and accepts at most one bounded authorization-code line from the browser

#### Scenario: Request tries to choose a command

- **WHEN** a request includes an executable, argv, shell text, environment, or unsupported provider
- **THEN** the API rejects it before spawning any process

### Requirement: Dashboard login navigation fails closed

The broker SHALL remove terminal control sequences and expose only HTTPS login URLs whose host matches the selected provider's explicit domain allowlist. Login session state SHALL remain in memory, SHALL be bounded, and SHALL be discarded after its retention window. The UI SHALL attempt to open the accepted URL, show a copyable fallback link, display bounded progress, and allow cancellation; it SHALL never render an unapproved URL as a navigation target.

#### Scenario: Provider emits an approved login URL

- **WHEN** a fixture emits an HTTPS URL on the selected provider's allowlist
- **THEN** the session exposes it as the login URL and the UI offers it to the operator

#### Scenario: Provider emits an unapproved URL

- **WHEN** provider output contains an URL on another host or a non-HTTPS scheme
- **THEN** the text may remain in the bounded diagnostic transcript but the URL is not exposed as a clickable login target

### Requirement: Dashboard authentication mutations are local by default

The Docker Compose Dashboard port SHALL bind to loopback by default, and every state-changing authentication endpoint SHALL reject cross-origin requests. Documentation SHALL require an authenticated reverse proxy before an operator intentionally publishes the Dashboard beyond the host.

#### Scenario: Cross-origin login is attempted

- **WHEN** the request Origin does not match the Dashboard request origin
- **THEN** the endpoint rejects login, input, cancellation, or logout before invoking a provider command
