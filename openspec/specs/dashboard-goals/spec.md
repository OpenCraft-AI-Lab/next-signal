# dashboard-goals Specification

## Purpose
TBD - created by archiving change dashboard-goals-subscriptions. Update Purpose after archive.
## Requirements
### Requirement: Goals page

The dashboard SHALL render `/goals` as the operator UI for the runtime goals file
in user state, resolved as `STATE_ROOT / "goals.yaml"`, per
`dashboard/app/goals/page.tsx` and `dashboard/components/goals/goals-editor.tsx`,
showing the number of configured goals. It SHALL NOT write
`configs/info_radar/goals.yaml`, which is image-baked and not shared between the
`dashboard` and `scheduler` containers.

Rendering the page SHALL NOT create or modify the runtime goals file. When the
file is absent or declares no goals, the page SHALL offer a **Start from example**
control that copies `configs/info_radar/goals.example.yaml` into state on an
explicit operator action.

The page SHALL additionally offer a read-only **View examples** disclosure in every
state, rendering the contents of `configs/info_radar/goals.example.yaml` without
writing anything, so that reference material is reachable without first discarding
configured goals. Merging examples into a non-empty goals list SHALL NOT be
offered, because example names can collide with configured names and duplicate
names are rejected.

#### Scenario: goals route renders current goals

- **WHEN** the operator visits `/goals`
- **THEN** the page reads the runtime goals file from state and renders one card
  per goal with name, description, topic count, and keyword count

#### Scenario: missing goals file shows actionable empty state

- **WHEN** the operator visits `/goals` and no runtime goals file exists in state
- **THEN** the page renders an empty state offering **Start from example**, and
  creates no file until that control is used

#### Scenario: empty goals list renders an actionable state

- **WHEN** the operator visits `/goals` and the runtime goals file declares an
  empty `goals:` list
- **THEN** the page explains that `next-signal info-radar analyze` will fail until
  at least one goal exists, and offers **Start from example**

#### Scenario: operator restores the example goals

- **WHEN** the operator activates **Start from example**
- **THEN** the dashboard writes the example goals into the runtime goals file,
  refreshes the list, and shows a success toast

#### Scenario: examples are readable without discarding configured goals

- **WHEN** the operator opens **View examples** while goals are configured
- **THEN** the example goals are displayed read-only and the runtime goals file is
  unchanged

### Requirement: Goal editing

The `/goals` page SHALL allow the operator to add, edit, and delete goals through
server actions that validate and persist the complete goals document to user
state. Deleting the final goal SHALL be permitted, because clearing seeded example
goals is a legitimate step toward configuring one's own.

#### Scenario: operator edits an existing goal

- **WHEN** the operator changes a goal description, topics, or keywords and clicks
  Save
- **THEN** the dashboard validates the full goals list, writes the runtime goals
  file in state atomically, refreshes the visible list, and shows a success toast

#### Scenario: operator adds a new goal

- **WHEN** the operator creates a goal with a unique kebab-case `name`, non-empty
  `description`, topics, and keywords
- **THEN** the dashboard appends it to the runtime goals file, refreshes the list,
  and shows a success toast

#### Scenario: operator deletes a goal

- **WHEN** the operator confirms deletion of an existing goal
- **THEN** the dashboard removes that goal from the runtime goals file, refreshes
  the list, and shows a success toast

#### Scenario: operator deletes the last remaining goal

- **WHEN** the operator confirms deletion of the only remaining goal
- **THEN** the dashboard persists an empty `goals:` list, does not disable or
  reject the delete control, and renders the actionable empty state

### Requirement: Goals schema validation

The dashboard SHALL preserve the same schema contract enforced by
`next_signal.workflows.info_radar_analysis.goals.load_goals`: top-level `goals`
list, entry fields `name`, `description`, `topics`, `keywords`, unique names, and
no unknown keys.

An empty `goals` list SHALL be valid to persist. Clearing the seeded example goals
is a legitimate step toward configuring one's own, and forcing an add-before-delete
order to satisfy a writer-side check serves nothing. The guarantee that analysis
refuses to run without goals is enforced by the loader at run time instead.

#### Scenario: duplicate name is rejected

- **WHEN** a save would produce two goals with the same `name`
- **THEN** the dashboard rejects the save, does not write the runtime goals file,
  and shows a validation error

#### Scenario: unknown field is rejected

- **WHEN** submitted goal data includes a key outside `name`, `description`,
  `topics`, and `keywords`
- **THEN** the dashboard rejects the save, does not write the runtime goals file,
  and shows a validation error

#### Scenario: empty goals list is accepted

- **WHEN** a save would produce an empty `goals` list
- **THEN** the dashboard writes it, and `next-signal info-radar analyze` raises
  `RuntimeError` on its next run until a goal is added

#### Scenario: name is immutable after creation

- **WHEN** the operator edits an existing goal card
- **THEN** the `name` field is displayed read-only; renaming requires deleting the
  old goal and adding a new one

### Requirement: Goals persistence

The dashboard SHALL write the runtime goals file in user state atomically and
SHALL NOT modify `configs/info_radar/goals.example.yaml`. The temporary file SHALL
be written inside the state directory so the rename never crosses a filesystem
boundary.

#### Scenario: atomic write succeeds

- **WHEN** validated goal changes are saved
- **THEN** the dashboard writes a temporary YAML file in the state directory and
  renames it over the runtime goals file

#### Scenario: write failure preserves old file

- **WHEN** persisting the updated goals fails
- **THEN** the dashboard reports the error and leaves the previously valid runtime
  goals file in place

#### Scenario: saved goals are visible to the scheduler

- **WHEN** the operator saves a goal change in the dashboard container
- **THEN** the `scheduler` container reads the same updated file, because user
  state is a shared volume rather than a per-container image layer
