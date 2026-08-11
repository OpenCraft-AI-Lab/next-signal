## MODIFIED Requirements

### Requirement: Folo subscription list integration

The system SHALL expose a stable server-side boundary that combines `folocli subscription list` with `folocli unread list`, using the same pinned argv/auth conventions as `next_signal.integrations.info_radar.folo`.

#### Scenario: CLI command returns normalized JSON

- **WHEN** `uv run next-signal info-radar subscriptions --json` is run with valid Folo auth
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
