# dashboard-goals Specification

## Purpose
TBD - created by archiving change dashboard-goals-subscriptions. Update Purpose after archive.
## Requirements
### Requirement: Goals page

The dashboard SHALL render `/goals` as the operator UI for `configs/info_radar/goals.yaml`, matching the committed Goals mock in `dashboard/design/pages-other.jsx` and showing the number of configured goals.

#### Scenario: goals route renders current goals

- **WHEN** the operator visits `/goals`
- **THEN** the page reads `configs/info_radar/goals.yaml` and renders one card per goal with name, description, topic count, and keyword count

#### Scenario: missing goals file shows actionable empty state

- **WHEN** `configs/info_radar/goals.yaml` is missing
- **THEN** the page renders an empty/error state explaining that the runtime file is missing and that `configs/info_radar/goals.example.yaml` can be copied as a starting point

### Requirement: Goal editing

The `/goals` page SHALL allow the operator to add, edit, and delete goals through server actions that validate and persist the complete `goals.yaml` document.

#### Scenario: operator edits an existing goal

- **WHEN** the operator changes a goal description, topics, or keywords and clicks Save
- **THEN** the dashboard validates the full goals list, writes `configs/info_radar/goals.yaml` atomically, refreshes the visible list, and shows a success toast

#### Scenario: operator adds a new goal

- **WHEN** the operator creates a goal with a unique kebab-case `name`, non-empty `description`, topics, and keywords
- **THEN** the dashboard appends it to `goals.yaml`, refreshes the list, and shows a success toast

#### Scenario: operator deletes a goal

- **WHEN** the operator confirms deletion of an existing goal
- **THEN** the dashboard removes that goal from `goals.yaml`, refreshes the list, and shows a success toast

### Requirement: Goals schema preservation

The dashboard SHALL preserve the same schema contract enforced by `paca.workflows.info_radar_analysis.goals.load_goals`: top-level `goals` list, entry fields `name`, `description`, `topics`, `keywords`, unique names, and no unknown keys.

#### Scenario: duplicate name is rejected

- **WHEN** a save would produce two goals with the same `name`
- **THEN** the dashboard rejects the save, does not write `goals.yaml`, and shows a validation error

#### Scenario: unknown field is rejected

- **WHEN** submitted goal data includes a key outside `name`, `description`, `topics`, and `keywords`
- **THEN** the dashboard rejects the save, does not write `goals.yaml`, and shows a validation error

#### Scenario: empty goals list is rejected

- **WHEN** a save would produce an empty `goals` list
- **THEN** the dashboard rejects the save because `paca info-radar analyze` requires at least one goal

#### Scenario: name is immutable after creation

- **WHEN** the operator edits an existing goal card
- **THEN** the `name` field is displayed read-only; renaming requires deleting the old goal and adding a new one

### Requirement: Goals persistence

The dashboard SHALL write `configs/info_radar/goals.yaml` atomically and SHALL NOT modify `configs/info_radar/goals.example.yaml`.

#### Scenario: atomic write succeeds

- **WHEN** validated goal changes are saved
- **THEN** the dashboard writes a temporary YAML file in `configs/info_radar/` and renames it over `goals.yaml`

#### Scenario: write failure preserves old file

- **WHEN** persisting the updated goals fails
- **THEN** the dashboard reports the error and leaves the previously valid `goals.yaml` in place

