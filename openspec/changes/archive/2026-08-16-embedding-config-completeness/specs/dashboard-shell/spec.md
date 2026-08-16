## MODIFIED Requirements

### Requirement: The settings page owns the embedding provider selection

The settings page SHALL carry an **Embedding** section that writes only
`~/.next-signal/embedding.json`. Changing it SHALL NOT read, write, or invalidate
language, schedule, engine, or coding-agent state.

No provider SHALL be selected on a fresh install, and the section SHALL present
that as a state to resolve rather than as an error. Every provider card SHALL
behave identically: clicking a card whose settings are incomplete SHALL only
open its pane and SHALL NOT write a selection, and saving a complete pane SHALL
atomically store its fields and select that provider. Later switches to an
already-complete provider SHALL commit on click. Failed writes SHALL roll
controls back; successful writes SHALL show a toast.

Each card's status SHALL be computed from what is actually saved and present —
whether its section is complete and its credential is in the store. No card
SHALL report a fixed status.

Panes SHALL prefill unsaved fields from the values in `configs/models.yaml`,
presented as suggestions. Prefilled values SHALL NOT be written or treated as
selected until the operator saves.

The OMLX pane SHALL carry the embedding API root alongside the model, and the
section SHALL state that this endpoint is separate from the engine section's
local endpoint because one local model server hosts one model.

The section SHALL report credential presence using server-computed booleans read
from the credential store, and SHALL point to the Credentials section for
entering one. It SHALL NOT accept a credential name or value; each provider's
credential is located by a fixed name. Base-URL controls SHALL reject userinfo,
query, and fragment components rather than permitting a secret to be persisted
inside the URL.

The section SHALL display the exact active vector-space identity, or state that
none is active while unselected. For compatible state it SHALL explain that
`space_id` identifies vector-producing behavior and must change when weights,
tokenizer, pooling, quantization, or similar behavior changes; moving the same
service to a new base URL does not require a new id.

Changing the selected provider SHALL require the operator to confirm a warning
presented at the moment of the change. The warning SHALL be unconditional rather
than conditioned on whether stored vectors exist, and SHALL state all material
consequences:

- switching parks dedup memory under the previous identity and switching back
  restores post-migration rows;
- pre-change `legacy:unknown` rows remain parked unless explicitly relabelled;
- hosted embedding sends tier-2 summaries off-machine and may incur per-item
  cost, including unattended scheduler runs.

The section SHALL state that while no provider is selected, deduplication is
inactive and the radar otherwise runs normally.

Values SHALL resolve server-side so controls paint their real state on first
render. A missing or unreadable state file SHALL render as unselected with
prefilled suggestions, logging the problem rather than failing the repair page.
The pipeline continues to reject unusable present state loudly.

The section SHALL reuse existing UI primitives and add no `/design` entry.

#### Scenario: fresh install shows nothing selected

- **WHEN** the operator opens `/settings` on an install where no embedder has
  been chosen
- **THEN** no card reads as selected, the section states that deduplication is
  inactive, and the panes show prefilled suggestions that have not been saved

#### Scenario: every provider requires complete settings before selection

- **WHEN** the operator clicks any card whose settings are incomplete
- **THEN** its pane opens without changing the active provider, and Save becomes
  the commit only after its fields validate

#### Scenario: card status reflects real state

- **WHEN** a provider's section is incomplete or its credential is absent
- **THEN** its card reports that, rather than a fixed configured status

#### Scenario: switching provider is confirmed

- **WHEN** the operator changes from one complete provider to another
- **THEN** a warning describing the parked-memory and egress consequences is
  presented and the change is written only after confirmation

#### Scenario: embedding endpoint is separate from the engine endpoint

- **WHEN** the operator sets the OMLX embedding API root
- **THEN** only `embedding.json` changes, the engine section's local endpoint is
  untouched, and the section explains why they are separate

#### Scenario: operator switches to OpenAI

- **WHEN** the operator confirms a switch to the configured OpenAI card
- **THEN** only `embedding.json` changes and the next item resolves OpenAI

#### Scenario: first generic selection requires complete settings

- **WHEN** no compatible section exists and the operator clicks its card
- **THEN** its pane opens without changing the active provider; Save becomes the
  commit only after all its fields validate

#### Scenario: compatible vector space is explicit

- **WHEN** compatible settings are saved
- **THEN** state contains `space_id` and the active identity displays as
  `openai_compatible:<space_id>`

#### Scenario: missing credential is visible without exposing it

- **WHEN** the selected provider's credential is absent from the store
- **THEN** the section shows missing status, renders no credential value, names
  the fixed credential it needs, and links to the Credentials section

#### Scenario: hosted data egress is visible

- **WHEN** the operator views a hosted provider
- **THEN** the pane states that summaries leave the machine and calls may cost money

#### Scenario: sections remain independent

- **WHEN** embedding settings are saved
- **THEN** `engine.json`, `coding-agents.json`, `schedule.json`,
  `language.json`, and `secrets.json` remain unchanged

#### Scenario: corrupt state does not break repair UI

- **WHEN** `embedding.json` is corrupt and `/settings` renders
- **THEN** the section renders as unselected with prefilled suggestions, logs the
  error, and renders without a client-side default flash

## ADDED Requirements

### Requirement: The settings page owns the local chat endpoint and says when it applies

The engine section SHALL own the local chat endpoint entirely, reading and
writing it in `~/.next-signal/engine.json`. It SHALL NOT display, inherit, or
fall back to a value from the process environment, and an endpoint that has
never been saved SHALL render as unset rather than as an environment value.

Because AgentOS constructs its interactive agents once at startup, the section
SHALL state that a changed endpoint applies to unattended runs and new processes
immediately, and to already-running interactive agents after a restart.

#### Scenario: unset endpoint renders as unset

- **WHEN** no local chat endpoint has been saved
- **THEN** the control renders empty rather than showing a value read from the
  environment

#### Scenario: the restart caveat is stated where the change is made

- **WHEN** the operator views or changes the local chat endpoint
- **THEN** the section states that already-running interactive agents pick the
  change up on restart, while scheduled runs and new processes use it at once
