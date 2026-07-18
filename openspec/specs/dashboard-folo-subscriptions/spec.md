# dashboard-folo-subscriptions Specification

## Purpose
TBD - created by archiving change dashboard-goals-subscriptions. Update Purpose after archive.
## Requirements
### Requirement: Subscriptions page

The dashboard SHALL render `/subscriptions` as a read-only inventory of the operator's Folo subscriptions, matching the committed Subscriptions mock in `dashboard/design/pages-other.jsx`.

#### Scenario: subscriptions route renders feed rows

- **WHEN** the operator visits `/subscriptions` and Folo returns subscriptions successfully
- **THEN** the page renders a table of feeds with title, feed URL, category/view, unread count when available, and last-updated text when available

#### Scenario: page shows aggregate subtitle

- **WHEN** subscriptions load successfully
- **THEN** the page subtitle includes the number of feeds and the total unread count when unread counts are available

### Requirement: Folo subscription list integration

The system SHALL expose a stable server-side boundary for `folocli subscription list` that uses the same pinned argv/auth conventions as `paca.integrations.info_radar.folo`.

#### Scenario: CLI command returns normalized JSON

- **WHEN** `uv run paca info-radar subscriptions --json` is run with valid Folo auth
- **THEN** it invokes the pinned `folocli` subscription-list command, parses the JSON envelope, and returns a JSON-safe list of normalized subscription rows

#### Scenario: argv override is honored

- **WHEN** `FOLO_CLI_ARGV` is set
- **THEN** the subscription-list command uses that argv prefix instead of the pinned default

#### Scenario: auth failure is reported

- **WHEN** Folo returns an auth error or non-ok envelope
- **THEN** the command exits non-zero or returns an error result that the dashboard can render without treating it as an empty subscription list

### Requirement: Subscription filtering

The `/subscriptions` page SHALL provide client-side search and category/view filtering over the loaded subscription rows.

#### Scenario: search narrows rows

- **WHEN** the operator types into the feed search box
- **THEN** the table shows only rows whose title or feed URL matches the search text case-insensitively

#### Scenario: category filter narrows rows

- **WHEN** the operator selects a category/view chip
- **THEN** the table shows only rows in that category/view

#### Scenario: no matching rows shows empty state

- **WHEN** the current search and category filters match no subscriptions
- **THEN** the table body shows an empty-state row rather than disappearing

### Requirement: Subscription loading and error states

The `/subscriptions` page SHALL distinguish loading, error, and empty-success states.

#### Scenario: cold start loading state

- **WHEN** the subscription list request is still running
- **THEN** the page shows a loading row/skeleton with copy explaining that a cold `folocli` start can take time

#### Scenario: CLI error state

- **WHEN** the subscription list request fails due to missing launcher, timeout, auth failure, or malformed output
- **THEN** the page shows an error panel with the diagnostic message and does not render an empty successful table

#### Scenario: empty subscription success

- **WHEN** Folo returns a successful empty subscription list
- **THEN** the page shows a successful empty state that says no subscriptions were returned

### Requirement: Subscriptions are read-only

The `/subscriptions` page SHALL NOT create, edit, delete, or reorder Folo subscriptions.

#### Scenario: no mutation controls

- **WHEN** the operator views `/subscriptions`
- **THEN** there are no add/edit/delete subscription controls and no dashboard action mutates Folo subscription state

