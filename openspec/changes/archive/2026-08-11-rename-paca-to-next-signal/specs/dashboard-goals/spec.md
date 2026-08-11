## MODIFIED Requirements

### Requirement: Goals schema preservation

The dashboard SHALL preserve the same schema contract enforced by `next_signal.workflows.info_radar_analysis.goals.load_goals`: top-level `goals` list, entry fields `name`, `description`, `topics`, `keywords`, unique names, and no unknown keys.

#### Scenario: duplicate name is rejected

- **WHEN** a save would produce two goals with the same `name`
- **THEN** the dashboard rejects the save, does not write `goals.yaml`, and shows a validation error

#### Scenario: unknown field is rejected

- **WHEN** submitted goal data includes a key outside `name`, `description`, `topics`, and `keywords`
- **THEN** the dashboard rejects the save, does not write `goals.yaml`, and shows a validation error

#### Scenario: empty goals list is rejected

- **WHEN** a save would produce an empty `goals` list
- **THEN** the dashboard rejects the save because `next-signal info-radar analyze` requires at least one goal

#### Scenario: name is immutable after creation

- **WHEN** the operator edits an existing goal card
- **THEN** the `name` field is displayed read-only; renaming requires deleting the old goal and adding a new one
