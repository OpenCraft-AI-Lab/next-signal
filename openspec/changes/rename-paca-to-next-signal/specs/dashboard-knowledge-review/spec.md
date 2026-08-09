## MODIFIED Requirements

### Requirement: Refresh spawns reconciliation detached

The section SHALL offer a refresh control that spawns `next-signal knowledge review` through the shared `spawnCliDetached` launcher and returns immediately. The dashboard MUST NOT write review state during page render — enrollment happens only through this spawned command.

#### Scenario: refresh returns without waiting

- **WHEN** the reader triggers refresh
- **THEN** the server action spawns the CLI detached and returns a started response rather than waiting for reconciliation to finish

#### Scenario: rendering the page enrolls nothing

- **WHEN** the `/knowledge` page is rendered while the wiki contains docs with no review row
- **THEN** no rows are inserted as a side effect of rendering
