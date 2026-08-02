## MODIFIED Requirements

### Requirement: Subscriptions page

The dashboard SHALL render `/subscriptions` as a read-only inventory of the operator's Folo subscriptions, per `dashboard/app/subscriptions/page.tsx`.

#### Scenario: subscriptions route renders feed rows

- **WHEN** the operator visits `/subscriptions` and Folo returns subscriptions successfully
- **THEN** the page renders a table of feeds with title, feed URL, category/view, and unread count

#### Scenario: table has no last-updated column

- **WHEN** the operator visits `/subscriptions`
- **THEN** the table renders no last-updated column, because Folo's subscription list carries no per-feed update timestamp and the subscription creation date is not one

#### Scenario: page shows aggregate subtitle

- **WHEN** subscriptions load successfully
- **THEN** the page subtitle includes the number of feeds and the sum of the per-feed unread counts

#### Scenario: zero unread renders as zero

- **WHEN** a subscription has no unread entries
- **THEN** its unread cell renders `0` as a genuine count, and the page never renders a placeholder count standing in for missing data

### Requirement: Folo subscription list integration

The system SHALL expose a stable server-side boundary that combines `folocli subscription list` with `folocli unread list`, using the same pinned argv/auth conventions as `paca.integrations.info_radar.folo`.

#### Scenario: CLI command returns normalized JSON

- **WHEN** `uv run paca info-radar subscriptions --json` is run with valid Folo auth
- **THEN** it invokes the pinned `folocli` subscription-list and unread-list commands, parses both JSON envelopes, and returns a JSON-safe list of normalized subscription rows

#### Scenario: unread counts are merged per feed

- **WHEN** `folocli unread list` reports an `unreadCount` for a feed
- **THEN** the subscription row whose feed id matches carries that count as its `unread` value

#### Scenario: feeds absent from the unread list count as zero

- **WHEN** a subscription does not appear in `folocli unread list`
- **THEN** its `unread` value is `0` rather than null, because the unread list enumerates every feed that has unread entries

#### Scenario: argv override is honored

- **WHEN** `FOLO_CLI_ARGV` is set
- **THEN** both the subscription-list and unread-list commands use that argv prefix instead of the pinned default

#### Scenario: auth failure is reported

- **WHEN** Folo returns an auth error or non-ok envelope for either command
- **THEN** the command exits non-zero or returns an error result that the dashboard can render without treating it as an empty subscription list

#### Scenario: unread failure does not degrade silently

- **WHEN** `folocli unread list` fails, times out, or returns a malformed envelope
- **THEN** the subscription boundary raises `RuntimeError` rather than returning rows whose unread counts are absent or defaulted to zero
