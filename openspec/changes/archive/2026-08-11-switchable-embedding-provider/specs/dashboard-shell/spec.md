## ADDED Requirements

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

The section SHALL report credential presence using server-computed booleans. It
SHALL accept only the compatible provider's environment-variable *name*, never a
key value, and no credential SHALL reach the browser. Compatible URL controls
SHALL reject userinfo, query, and fragment components rather than permitting a
secret to be persisted inside the URL.

The section SHALL display the exact active vector-space identity. For compatible
state it SHALL explain that `space_id` identifies vector-producing behavior and
must change when weights, tokenizer, pooling, quantization, or similar behavior
changes; moving the same service to a new base URL does not require a new id.

The section SHALL state all material consequences before selection:

- switching parks dedup memory under the previous identity and switching back
  restores post-migration rows;
- pre-change `legacy:unknown` rows remain parked unless explicitly relabelled;
- hosted embedding sends tier-2 summaries off-machine and may incur per-item
  cost, including unattended scheduler runs;
- after editing `.env`, a host process must restart or a Compose service must be
  recreated before the new credential appears in its environment.

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

- **WHEN** the selected provider's environment variable is absent
- **THEN** the section shows missing status and renders no credential value

#### Scenario: hosted data egress is visible

- **WHEN** the operator views a hosted provider
- **THEN** the pane states that summaries leave the machine and calls may cost money

#### Scenario: sections remain independent

- **WHEN** embedding settings are saved
- **THEN** `engine.json`, `coding-agents.json`, `schedule.json`, and
  `language.json` remain unchanged

#### Scenario: corrupt state does not break repair UI

- **WHEN** `embedding.json` is corrupt and `/settings` renders
- **THEN** the section falls back to configured OMLX/OpenAI baselines, logs the
  error, and renders without a client-side default flash
