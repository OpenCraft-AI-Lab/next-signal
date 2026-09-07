## Purpose

Defines how an operator commits a choice in a dashboard settings section —
one action per independent decision the section contains, with the recorded
selection always reflecting what was actually committed rather than whatever
is merely being viewed.

## ADDED Requirements

### Requirement: Each independent decision in a section commits through exactly one action

A settings section SHALL NOT require more than one action to finish
committing any single decision an operator makes in it. Where a section
contains only one such decision (an option's selection, its own parameters,
and any credential it needs, treated as one decision), it SHALL expose
exactly one control for the whole section. Where a section genuinely contains
more than one independent decision, each SHALL still commit through exactly
one control of its own — no decision SHALL be split across two actions, and
no single action SHALL silently bundle a decision the operator did not
trigger.

#### Scenario: one action persists a fused decision

- **WHEN** an operator fills in an option's parameters and its credential, in
  a section where selecting and configuring are one decision, and triggers
  that section's one commit action
- **THEN** the parameters and the credential are both persisted, with no
  further action required to finish the commit

#### Scenario: a partially entered value is never written on its own

- **WHEN** an operator types into a field or credential input but has not yet
  triggered the action that commits it
- **THEN** nothing is written to persistent state as a result of the typing
  alone

#### Scenario: an independent decision commits without needing a different one

- **WHEN** a section contains two independent decisions, and an operator
  triggers only one of them
- **THEN** that decision is committed, and the other decision's own state is
  unaffected and requires its own separate action to change

### Requirement: An irreversible section fuses selection and configuration

In a section where committing an option locks it in permanently (Radar
Embedding, Knowledge Embedding), selecting the option and completing its
configuration SHALL happen as a single commit. No section of this kind SHALL
offer a way to select an option before its configuration is complete, or to
complete a configuration without that action also selecting it.

#### Scenario: completing configuration also selects the option

- **WHEN** an operator finishes an option's required fields and credential and
  commits
- **THEN** that option becomes the section's selection in the same action,
  with no separate selection step before or after

#### Scenario: the section is read-only after its one commit

- **WHEN** a section of this kind has been committed
- **THEN** every field belonging to that section, including its credential,
  is presented read-only, and no further commit is possible through the
  section

### Requirement: A switchable section separates configuring an option from activating it

In a section where an operator can change which option is active over time
(Engine), configuring an option's own parameters and credential, and
activating an option (making it the active choice), SHALL be two independent
decisions, each committing through its own action with no shared draft
between them. Activating an option SHALL commit immediately when triggered.
Configuring an option's own parameters and credential SHALL commit
immediately when triggered and SHALL NOT alter which option is active.
Neither action's availability SHALL depend on whether the other has unsaved
or uncommitted input pending.

#### Scenario: configuring a non-active option does not activate it

- **WHEN** an operator edits a non-active option's own parameters or
  credential and commits that edit
- **THEN** those edits are saved and the previously active option remains
  active

#### Scenario: activating an option does not require saving its fields first

- **WHEN** an operator triggers the activation action for an option whose own
  parameters have not been separately saved in this visit
- **THEN** the option becomes active using its already-saved configuration,
  and the activation action is not blocked by, and does not perform, a save
  of any pane's own fields

#### Scenario: configuring the active option never uses a stale value for its own fields

- **WHEN** an operator edits the currently active option's own parameters and
  triggers that option's own commit action
- **THEN** the edited parameters are the ones persisted — the commit SHALL NOT
  fall back to a previously saved value for a field the operator just changed,
  and which option is active is unaffected by this commit

#### Scenario: an unsaved field edit does not block or enable activation, and vice versa

- **WHEN** an operator has an unsaved edit to an option's own parameters
  pending, or has just activated a different option
- **THEN** whether the parameters can be saved, and whether an option can be
  activated, are each governed only by that action's own conditions — neither
  action's availability changes because of the other's pending or completed
  state

### Requirement: An option cannot become active while incomplete

Before an activation action would make an option active, or would leave an
already-active option active, the section SHALL verify that option's
required configuration — including any required credential — is present,
evaluated against that option's last-saved state, not any unsaved input
pending in its own pane. An incomplete option SHALL NOT become active.

#### Scenario: activating an incomplete option is refused

- **WHEN** an operator triggers the activation action for an option that is
  missing a required field or credential in its last-saved configuration
- **THEN** the action is refused and nothing about the active option changes

#### Scenario: a fully configured option can be activated

- **WHEN** an operator triggers the activation action for an option whose
  last-saved required fields and credential are all present
- **THEN** the option becomes active

#### Scenario: an unsaved completing edit does not unlock activation

- **WHEN** an operator types a value into an option's own field that would
  make it complete, but has not yet saved that field
- **THEN** the activation action remains refused until the field is actually
  saved, because the gate reads saved state, not the pane's current draft

### Requirement: The recorded selection reflects only what was committed

Any indicator of "which option is selected or active" SHALL reflect the last
committed choice. It SHALL NOT reflect which option's configuration is
currently open for viewing or editing when that differs from the committed
choice.

#### Scenario: viewing an option does not mark it selected

- **WHEN** an operator opens a different option's configuration to look at or
  edit it, without committing
- **THEN** no indicator shows that option as selected or active

#### Scenario: the indicator matches the committed choice after commit

- **WHEN** a section has committed a selection or activation
- **THEN** exactly the committed option's indicator shows it as selected or
  active, regardless of which option's configuration is currently open
