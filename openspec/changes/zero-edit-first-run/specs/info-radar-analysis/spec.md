## ADDED Requirements

### Requirement: Runtime goals file provisioning

The runtime goals file SHALL be populated by an explicit setup step, never as a
side effect of loading it. `scripts/container_bootstrap.sh` SHALL populate it when
it is absent, before the `dashboard` and `scheduler` services start.

Population SHALL prefer an existing `configs/info_radar/goals.yaml` when one is
present — migrating a curated list exactly once — and SHALL otherwise copy
`configs/info_radar/goals.example.yaml`. `goals.example.yaml` SHALL remain a valid
runtime document and SHALL NOT be modified.

The guard SHALL be the runtime goals file's **existence**, never its goal count,
so that a deliberately emptied goals list is not repopulated on a subsequent
start. Provisioning SHALL be idempotent across repeated `docker compose up` runs.

A deployment that never runs bootstrap SHALL NOT be silently provisioned; the
loader's error and the `/goals` page are the paths by which such an operator
learns that no goals exist.

#### Scenario: fresh install is seeded from the example

- **WHEN** bootstrap runs, no runtime goals file exists in state, and no
  `configs/info_radar/goals.yaml` is present
- **THEN** `configs/info_radar/goals.example.yaml` is copied into state and loads
  successfully

#### Scenario: existing repo-path goals file migrates once

- **WHEN** bootstrap runs, no runtime goals file exists in state, and
  `configs/info_radar/goals.yaml` is present
- **THEN** that file's content is copied into state and the example is not used

#### Scenario: provisioning never overwrites an existing file

- **WHEN** bootstrap runs and a runtime goals file already exists in state
- **THEN** the file is left byte-identical, whatever it contains

#### Scenario: an emptied goals list is not repopulated

- **WHEN** the operator has saved an empty `goals:` list and the stack is started
  again
- **THEN** bootstrap leaves the empty list in place and does not restore the
  example goals

## MODIFIED Requirements

### Requirement: Goals declared in a single user-editable YAML

`next_signal/workflows/info_radar_analysis/` SHALL load goal descriptors from the
runtime goals file in user state, resolved as `STATE_ROOT / "goals.yaml"`
(`/state/goals.yaml` inside a container, `~/.next-signal/goals.yaml`
host-native). It SHALL NOT read `configs/info_radar/goals.yaml`, which is
image-baked deployment content and is not shared between the `dashboard` and
`scheduler` containers.

The file MUST contain a top-level `goals:` list. Each entry MUST declare `name`
(unique, kebab-case), `description`, `topics` (list of strings), and `keywords`
(list of strings). Unknown top-level keys or unknown per-entry keys SHALL raise
`RuntimeError` at load time.

Loading SHALL be a pure read and SHALL NOT create, modify, or repair the runtime
goals file. A missing file SHALL raise `RuntimeError` naming the resolved state
path. A `goals:` list that is present but empty SHALL raise `RuntimeError` naming
the empty list as the cause. These two failures SHALL carry distinct messages, and
both SHALL be distinct from a parse error. The workflow MUST NOT fall back to an
implicit default goal.

#### Scenario: missing goals.yaml aborts the run

- **WHEN** `next-signal info-radar analyze` runs and no runtime goals file exists
  in state
- **THEN** the workflow raises `RuntimeError` naming the resolved state path, exits
  non-zero before any LLM call, and creates no file

#### Scenario: empty goals list aborts the run

- **WHEN** `next-signal info-radar analyze` runs and the runtime goals file
  contains an empty `goals:` list
- **THEN** the workflow raises `RuntimeError` naming the empty goals list, with a
  message distinct from the missing-file error, and exits non-zero before any LLM
  call

#### Scenario: duplicate goal names fail fast

- **WHEN** the runtime goals file contains two entries with the same `name`
- **THEN** the loader raises `RuntimeError` mentioning the duplicate `name`

### Requirement: next-signal doctor checks goals.yaml

`next-signal doctor` SHALL include a goals check that reports OK with the goal
count when the runtime goals file in user state exists, parses, and declares at
least one goal. It SHALL report FAIL otherwise, and the failure message SHALL
distinguish a missing file, a configured-but-empty goals list — which an operator
can now deliberately create — and a parse error. The check SHALL report the state
path it resolved, and SHALL NOT invoke any LLM.

#### Scenario: missing goals.yaml fails the doctor check

- **WHEN** `next-signal doctor` runs and no runtime goals file exists in state
- **THEN** the doctor output includes a FAIL line naming the resolved state path

#### Scenario: empty goals list fails the doctor check

- **WHEN** `next-signal doctor` runs and the runtime goals file declares an empty
  `goals:` list
- **THEN** the doctor output includes a FAIL line stating that no goals are
  configured and directing the operator to the `/goals` page

#### Scenario: unparseable goals file fails with the loader error

- **WHEN** `next-signal doctor` runs and the runtime goals file cannot be parsed
- **THEN** the doctor output includes a FAIL line carrying the loader's error
  message, distinct from the missing-file and empty-list messages

#### Scenario: configured goals pass the check

- **WHEN** `next-signal doctor` runs and the runtime goals file declares one or
  more valid goals
- **THEN** the doctor output includes an OK line with the goal count and the
  resolved state path
