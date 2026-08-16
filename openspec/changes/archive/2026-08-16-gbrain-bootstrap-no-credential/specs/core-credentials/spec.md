## ADDED Requirements

### Requirement: Container bootstrap handles no credential

`scripts/container_bootstrap.sh` SHALL NOT read, inject, export, or otherwise
handle any provider credential. It runs before any credential can exist: the
store is written by the dashboard, and the dashboard does not start until
bootstrap has completed successfully.

A bootstrap step that would need a credential to initialise an external program
SHALL NOT perform that initialisation at all. It SHALL leave the program
uninitialised for an operator to complete later, and the dependent capability
SHALL be reported as unavailable until they do. It SHALL NOT branch on whether a
credential happens to be present, because a conditional path reintroduces
credential handling into a script that must not have any.

Bootstrap SHALL NOT substitute a reduced initialisation that avoids the
credential, where that reduced form cannot afterwards be completed. Such a form
is not a deferral but a permanent choice made before the operator can make it.

Steps that need no credential SHALL still run, so that deferral is scoped to the
initialisation itself rather than to everything near it. Maintaining an
already-initialised program — migrations and other no-credential upkeep — SHALL
continue to run on every boot.

This requirement exists because the shell script cannot use the Python
credential helpers, so a shell-side "mirror" of them drifts silently — which is
exactly how bootstrap came to inherit an environment that no longer holds the
credential it assumed. Removing the need is the durable fix; copying the
injection is not.

Bootstrap SHALL NOT later initialise a program it deferred. Doing so would
require reading a credential, which is the thing this requirement forbids.

#### Scenario: bootstrap succeeds against an empty store

- **WHEN** container bootstrap runs with no credential configured anywhere
- **THEN** every step completes and the script exits zero

#### Scenario: bootstrap does not consult the store

- **WHEN** container bootstrap runs with credentials present in the store
- **THEN** it behaves identically to a run with an empty store, and reads no
  credential

#### Scenario: an external program needing a credential is left uninitialised

- **WHEN** bootstrap reaches a step that would initialise an external program
  whose initialisation requires a credential
- **THEN** it performs no initialisation, exits zero, and the dependent
  capability is reported as unavailable rather than partially configured

#### Scenario: maintenance of an already-initialised program still runs

- **WHEN** container bootstrap runs against an external program that is already
  initialised
- **THEN** its no-credential maintenance steps run as before, unaffected by the
  deferral of first-time initialisation

### Requirement: An injected credential is scoped to the selected provider

Where a spawned external program can be pointed at any of several providers, the
credential injected into its environment SHALL be the one **the selected
provider** requires, resolved from the selection rather than hard-coded to a
single provider.

A selection naming a provider that requires no credential — a local or
self-hosted runner — SHALL be supported with no credential injected at all, and
SHALL NOT be blocked by the absence of an unrelated provider's key. This
requirement covers credential scoping only: a local provider's endpoint
(where to reach it) is separate from its credential (whether it needs one),
and configuring that endpoint is out of scope for this change — see
`proposal.md` Non-Goals.

Where the selected provider does require a credential and it is absent, the
failure SHALL name that provider's credential specifically, not a default one.

#### Scenario: the selected provider's credential is the one injected

- **WHEN** an external program is spawned for a provider whose credential
  differs from the default provider's
- **THEN** that provider's credential is injected and the default provider's is
  not

#### Scenario: a local provider needs no credential

- **WHEN** the selected provider is a local runner requiring only an endpoint
- **THEN** the spawn succeeds with no credential injected, against an empty
  credential store

#### Scenario: a missing credential names the right provider

- **WHEN** the selected provider requires a credential that is absent from the
  store
- **THEN** the error names that provider's credential and points at the
  dashboard settings page
