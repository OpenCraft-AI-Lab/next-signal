## MODIFIED Requirements

### Requirement: Child processes receive credentials only when named

Credentials required by an external program SHALL be supplied through an
environment built for that one subprocess, naming the credentials that program
needs. The calling process's own environment SHALL NOT be modified.

This requirement applies regardless of whether the spawning module itself
reads or names the credential in its own source. It SHALL also cover the case
where the *external program* reads a credential-shaped variable from its own
inherited environment — the spawning module may never mention that
credential's name at all, which means a grep for credential names does not
prove this requirement is met.

A subprocess spawn SHALL NOT be built by copying the calling process's whole
environment (for example Python's `os.environ.copy()` or Node's
`{...process.env}`) unmodified when the target program might read a
credential-shaped variable on its own. Omitting an explicit environment for a
spawn — letting the platform's default full inheritance apply — is conforming
only when the target program is verified to consume no credential; that
verification SHALL NOT be assumed from the spawning module's own source
containing no credential name.

A credential absent from the store SHALL be omitted from the child environment
rather than passed as an empty value, because a third-party program's handling
of an empty variable is not ours to define.

#### Scenario: only named credentials reach the child

- **WHEN** a subprocess is spawned with a child environment naming one
  credential
- **THEN** that credential is present in the child and no other credential is

#### Scenario: spawning does not leak into the parent

- **WHEN** a child environment carrying credentials is built and used
- **THEN** the parent process's own environment is unchanged afterwards

#### Scenario: a third-party program reading its own credential is still scoped

- **WHEN** a spawned external program (not our code) reads a credential-shaped
  environment variable on its own, and the spawning module never names that
  credential anywhere in its source
- **THEN** the subprocess is still built through a child environment that
  strips every known credential name before re-adding only the ones the call
  site explicitly supplies, rather than through an unmodified copy of the
  calling process's environment

#### Scenario: an unscoped environment copy is a defect regardless of grep results

- **WHEN** a subprocess spawn is built with `os.environ.copy()` or
  `{...process.env}` and handed to an external program that can read a
  credential from its environment
- **THEN** the spawn does not conform to this requirement even though no
  credential name appears anywhere in the spawning module's source
