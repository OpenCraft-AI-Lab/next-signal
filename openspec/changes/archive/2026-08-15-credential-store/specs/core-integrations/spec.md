## MODIFIED Requirements

### Requirement: API keys read at call time

Each integration SHALL read its API key from the credential store inside the
tool function body, not at module import. `next_signal.integrations._helpers.env(NAME)`
remains the reader for non-credential configuration — executable paths, argv
overrides, and similar deployment settings — and SHALL NOT be used to obtain a
credential.

#### Scenario: missing key does not block startup

- **WHEN** the credential store holds no `EXAMPLE_API_KEY`
- **THEN** `next-signal serve` still starts; the missing credential only surfaces
  when an agent actually calls a tool from that integration

#### Scenario: missing key fails loud at call time

- **WHEN** an agent invokes a tool whose credential is unset
- **THEN** the tool raises `RuntimeError` naming the credential and pointing at
  the settings page

#### Scenario: deployment configuration still comes from the environment

- **WHEN** an integration needs a binary path or argv override
- **THEN** it reads it with `env(NAME)` from the process environment, unchanged

## ADDED Requirements

### Requirement: The credential store is folocli's only authentication source

Every `folocli` invocation SHALL require `FOLO_TOKEN` from the credential store
and SHALL raise `RuntimeError` naming the credential and pointing at the settings
page *before* spawning the subprocess when it is absent.

folocli's own cached session file SHALL NOT be treated as a supported
authentication path. It is unreachable in the supported container deployment: no
volume backs its home directory, and the command that populates it completes over
a loopback callback bound inside the container, which a browser on the host
cannot reach. Leaving it as an implicit fallback would also give the system two
sources of truth for one credential, only one of which has a UI.

#### Scenario: absent token fails before the subprocess runs

- **WHEN** a folocli-backed command runs and the store holds no `FOLO_TOKEN`
- **THEN** it raises naming the credential, and no subprocess is spawned

#### Scenario: a cached session does not substitute for the store

- **WHEN** the store holds no `FOLO_TOKEN` but a folocli session file exists
- **THEN** the command still fails, and the session file is not consulted
