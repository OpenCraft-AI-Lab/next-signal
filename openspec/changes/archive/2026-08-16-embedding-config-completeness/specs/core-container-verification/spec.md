## MODIFIED Requirements

### Requirement: Health-check exit code semantics

`next-signal doctor` SHALL report per-check status independently of its exit code. A
non-zero exit MUST NOT be read as stack failure when the failing checks are
optional under the active deployment profile, or when they report configuration
an operator has not completed yet.

A freshly started stack that nobody has configured SHALL be expected to exit
non-zero. Unset model credentials and an unselected embedder are the normal
first-run state, not defects in the stack.

#### Scenario: Cloud-only profile

- **WHEN** `next-signal doctor` runs in a container with no local endpoint
  configured and no embedder selected
- **THEN** it exits non-zero because unset model keys and the unselected
  embedder report ✗
- **AND** the stack is nonetheless healthy if `DATABASE_URL`, Postgres,
  configured agents, and registered tools all report ✔

#### Scenario: An unselected embedder is a first-run state

- **WHEN** a fresh stack has never had an embedder selected
- **THEN** the embedder check reports ✗ naming the unselected state and the
  stack is still considered correctly started
