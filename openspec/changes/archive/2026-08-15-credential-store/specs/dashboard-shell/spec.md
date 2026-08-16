## ADDED Requirements

### Requirement: The settings page owns provider credentials

The settings page SHALL provide a single Credentials section that is the only
place a credential is entered, covering every credential the system uses. Each
credential SHALL have its own control, and saving one SHALL NOT read, write, or
invalidate any other settings state.

Inputs SHALL be write-only. The server SHALL send the client a presence boolean
per credential and never a credential value, in whole or in part — no masked
rendering and no last-four preview. A saved credential SHALL be replaceable and
removable.

Each control SHALL name what breaks while the credential is unset, so the
consequence of an empty field is visible before a feature fails.

The section SHALL NOT tell the operator to edit `.env`, restart a host process,
or recreate a Compose service: credentials resolve at call time, so a save takes
effect on the next use.

Failed writes SHALL roll the control back and surface the failure; successful
writes SHALL show a toast, matching the commit-acknowledgement contract the other
settings sections already follow. The section SHALL reuse existing UI primitives
and add no `/design` entry.

#### Scenario: operator sets a credential

- **WHEN** a credential is entered and saved
- **THEN** only the credential store changes, the control reports it as present,
  and a toast acknowledges the write

#### Scenario: a saved credential is never rendered back

- **WHEN** the settings page is loaded with credentials already saved
- **THEN** each control shows presence only, and no credential value or fragment
  appears in the page payload

#### Scenario: operator removes a credential

- **WHEN** a saved credential is cleared
- **THEN** it is removed from the store and the control reports it as absent

#### Scenario: saving needs no lifecycle action

- **WHEN** a credential is saved while the scheduler container is running
- **THEN** the section instructs no restart or recreation, and the next run uses
  the new value

### Requirement: The Folo credential can be obtained by browser sign-in

The Credentials section SHALL offer an assisted sign-in for the Folo credential
in addition to its input, because Folo issues no user-facing API token: its
credential is a session value, so without assistance the only routes are copying
a browser cookie or reading a local CLI config file.

The dashboard SHALL host the sign-in callback itself. It SHALL start a sign-in by
directing the operator to Folo's web sign-in with a callback address pointing at
its own route, receive the returned one-time token there, exchange it for a
session token, and write only that session token to the credential store.

The dashboard hosts the callback rather than delegating to `folocli login`
because that command completes over a loopback callback on an ephemeral port
bound inside whichever process runs it; in the container deployment no browser on
the host can reach that address, and the port cannot be published because it is
chosen at runtime.

A sign-in SHALL be startable only by a same-origin request. Each attempt SHALL be
bounded in time and SHALL be cancellable. Only one sign-in SHALL be in flight at
a time. The operator-facing sign-in target SHALL be an HTTPS URL on an explicit
Folo domain allowlist, and an unapproved URL SHALL NOT be rendered as a
navigation target. No token, one-time or session, SHALL be rendered in the page,
returned to the client, or written to a log.

Sign-in SHALL be an assistance, not a requirement: the credential's manual input
SHALL remain available and SHALL produce the same stored result, so a deployment
whose browser cannot reach the dashboard, or whose sign-in fails, is not blocked.

#### Scenario: Operator signs in through the browser

- **WHEN** the operator starts Folo sign-in and completes it in the browser
- **THEN** the callback exchanges the returned token, the session token is
  written to the credential store, and the control reports the credential as
  present

#### Scenario: Token never reaches the page

- **WHEN** a sign-in completes
- **THEN** neither the one-time token nor the session token appears in any
  response body, page payload, or log

#### Scenario: Sign-in failure leaves manual entry available

- **WHEN** a sign-in is cancelled, times out, or fails its exchange
- **THEN** the credential store is unchanged, the failure is reported, and the
  operator can still paste a token into the input

#### Scenario: Only allowlisted sign-in targets are offered

- **WHEN** a sign-in target is not an HTTPS URL on the Folo domain allowlist
- **THEN** the UI does not offer it as a navigation target

## MODIFIED Requirements

### Requirement: The settings page owns the embedding provider selection

The settings page SHALL carry an **Embedding** section that writes only
`~/.next-signal/embedding.json`. Changing it SHALL NOT read, write, or invalidate
language, schedule, engine, or coding-agent state.

OMLX and OpenAI have complete baselines, so selecting either provider is a
discrete choice that SHALL commit on click against its last saved parameters.
OpenAI-compatible has no fabricated baseline: clicking its card before complete
settings exist SHALL only open its pane and SHALL NOT write an invalid selection.
Saving a complete compatible pane SHALL atomically store its `base_url`, `model`,
`api_key_env`, and `space_id` and select it. Later switches to that saved provider
SHALL commit on click. Failed writes SHALL roll controls back; successful writes
SHALL show a toast.

The section SHALL report credential presence using server-computed booleans read
from the credential store, and SHALL point to the Credentials section for
entering one. It SHALL accept only the compatible provider's credential *name*,
never a key value, and no credential SHALL reach the browser. Compatible URL
controls SHALL reject userinfo, query, and fragment components rather than
permitting a secret to be persisted inside the URL.

The section SHALL display the exact active vector-space identity. For compatible
state it SHALL explain that `space_id` identifies vector-producing behavior and
must change when weights, tokenizer, pooling, quantization, or similar behavior
changes; moving the same service to a new base URL does not require a new id.

The section SHALL state all material consequences before selection:

- switching parks dedup memory under the previous identity and switching back
  restores post-migration rows;
- pre-change `legacy:unknown` rows remain parked unless explicitly relabelled;
- hosted embedding sends tier-2 summaries off-machine and may incur per-item
  cost, including unattended scheduler runs.

Values SHALL resolve server-side so controls paint their real state on first
render. A missing or unreadable state file SHALL render the real OMLX/OpenAI
baseline and log the problem rather than failing the repair page. The pipeline
continues to reject unusable present state loudly.

The section SHALL reuse existing UI primitives and add no `/design` entry.

#### Scenario: operator switches to OpenAI

- **WHEN** the operator clicks the configured OpenAI card
- **THEN** only `embedding.json` changes and the next item resolves OpenAI

#### Scenario: first generic selection requires complete settings

- **WHEN** no compatible section exists and the operator clicks its card
- **THEN** its pane opens without changing the active provider; Save becomes the
  commit only after all four fields validate

#### Scenario: compatible vector space is explicit

- **WHEN** compatible settings are saved
- **THEN** state contains `space_id` and the active identity displays as
  `openai_compatible:<space_id>`

#### Scenario: missing credential is visible without exposing it

- **WHEN** the selected provider's credential is absent from the store
- **THEN** the section shows missing status, renders no credential value, and
  links to the Credentials section

#### Scenario: hosted data egress is visible

- **WHEN** the operator views a hosted provider
- **THEN** the pane states that summaries leave the machine and calls may cost money

#### Scenario: sections remain independent

- **WHEN** embedding settings are saved
- **THEN** `engine.json`, `coding-agents.json`, `schedule.json`,
  `language.json`, and `secrets.json` remain unchanged

#### Scenario: corrupt state does not break repair UI

- **WHEN** `embedding.json` is corrupt and `/settings` renders
- **THEN** the section falls back to configured OMLX/OpenAI baselines, logs the
  error, and renders without a client-side default flash
