## REMOVED Requirements

### Requirement: The settings page owns provider credentials

**Reason**: A single shared Credentials section rendering every credential the
system resolves gave the operator no link between a credential and the feature
it powers, and buried the two credentials (`VOYAGE_API_KEY`,
`GOOGLE_GENERATIVE_AI_API_KEY`) that had no control at all. Credential entry
moves into the functional section that consumes each credential; see the
per-section requirements below (Engine, Radar Embedding, Knowledge Embedding,
RSS) and the new read-only summary requirement that replaces this section's
former role as the credential list.

**Migration**: No data migration — credentials remain in the same
`secrets.json` store under the same names (except the radar OpenAI credential,
which is renamed; see `core-credentials`). An operator looking for where to
enter a credential now opens the section that uses it instead of a shared
Credentials section.

## ADDED Requirements

### Requirement: Each settings section owns entry of the credentials it consumes

A functional section that depends on a credential SHALL render that
credential's input inline, inside the section, rather than in a shared
location. Saving a credential through one section SHALL NOT read, write, or
invalidate any other section's state, matching the independence every other
settings section already keeps.

Inputs SHALL remain write-only, exactly as before centralization: the server
SHALL send the client a presence boolean per credential and never a value, in
whole or in part; a saved credential SHALL be replaceable and removable from
the section that owns it; and a control SHALL name what breaks while its
credential is unset.

The settings page SHALL additionally render a single read-only summary,
positioned after every functional section, listing every credential the system
resolves and whether it is present. The summary SHALL display presence only —
no value, no masked preview — and SHALL offer no way to set or clear a
credential; it exists so an operator can see the whole configured surface at a
glance without hunting through sections, not as an alternate entry point.

#### Scenario: a credential is entered where it is used

- **WHEN** the operator opens the Radar Embedding section and saves its OpenAI
  pane
- **THEN** `RADAR_EMBEDDING_OPENAI_API_KEY` is written to the credential store,
  the pane reports it as present, and no other section's state changes

#### Scenario: the summary is read-only

- **WHEN** the operator views the end-of-page credential summary
- **THEN** every resolved credential is listed with a present/absent indicator
  and no value, and no control on that summary can set or clear a credential

#### Scenario: the summary reflects a section's save

- **WHEN** a credential is saved inside its owning section
- **THEN** the end-of-page summary reports it as present without a page reload

## MODIFIED Requirements

### Requirement: The Folo credential can be obtained by browser sign-in

The RSS section SHALL offer an assisted sign-in for the Folo credential in
addition to its input, because Folo issues no user-facing API token: its
credential is a session value, so without assistance the only routes are
copying a browser cookie or reading a local CLI config file.

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

- **WHEN** the operator starts Folo sign-in from the RSS section and completes
  it in the browser
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
  operator can still paste a token into the input within the RSS section

#### Scenario: Only allowlisted sign-in targets are offered

- **WHEN** a sign-in target is not an HTTPS URL on the Folo domain allowlist
- **THEN** the UI does not offer it as a navigation target

### Requirement: The settings page owns the embedding provider selection

The settings page SHALL carry a **Radar Embedding** section, collapsible, that
writes only `~/.next-signal/embedding.json`. Changing it SHALL NOT read, write,
or invalidate language, schedule, engine, or coding-agent state. Collapsed, the
section SHALL show its selected provider and model (or that none is selected);
expanding it is required to change anything.

No provider SHALL be selected on a fresh install, and the section SHALL present
that as a state to resolve rather than as an error. Every provider card SHALL
behave identically: clicking a card whose settings are incomplete SHALL only
open its pane and SHALL NOT write a selection, and saving a complete pane SHALL
atomically store its fields and select that provider.

Once a pane has been saved and a provider selected, the section SHALL lock in
full: every card and pane SHALL render read-only, no further save is offered,
and no field — including one that would not itself change the vector-space
identity — is editable through this section. A changed embedding model breaks
comparability with vectors already produced under the previous model, so this
is a one-time choice for the life of the install, not a switchable preference.

Each card's status, while the section is unlocked, SHALL be computed from what
is actually saved and present — whether its section is complete and its
credential (where the provider has one) is in the store. No card SHALL report a
fixed status.

Panes SHALL prefill unsaved fields from the values in `configs/models.yaml`,
presented as suggestions. Prefilled values SHALL NOT be written or treated as
selected until the operator saves.

The OMLX pane SHALL carry the embedding API root alongside the model, and the
section SHALL state that this endpoint is separate from the engine section's
local endpoint because one local model server hosts one model. The OMLX pane
SHALL NOT offer a credential field.

The OpenAI and OpenAI-compatible panes SHALL each render their credential's
input inline (`RADAR_EMBEDDING_OPENAI_API_KEY` and `EMBEDDING_API_KEY`
respectively), using server-computed presence booleans read from the credential
store. Saving either pane SHALL require its credential to already be present in
the store, in addition to its other fields; the pane SHALL NOT save, and
therefore SHALL NOT lock the section, while its credential is absent — a hosted
provider cannot be selected in a state guaranteed to fail on first use. Base-URL
controls SHALL reject userinfo, query, and fragment components rather than
permitting a secret to be persisted inside the URL.

The section SHALL display the exact active vector-space identity once selected,
or state that none is active while unselected. For compatible state it SHALL
explain that `space_id` identifies vector-producing behavior and must change
when weights, tokenizer, pooling, quantization, or similar behavior changes;
moving the same service to a new base URL does not require a new id — this
explanation exists to justify why `space_id`, not `model`, is what a locked
compatible section commits to.

Before the first save that selects a provider, the section SHALL present an
explicit warning that the choice is permanent for the life of this install and
cannot be changed or reconfigured afterward, and require the operator to
confirm it before the write proceeds. Hosted providers' warnings SHALL also
state that summaries leave the machine and calls may cost money, including
during unattended scheduler runs.

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
- **THEN** its pane opens without changing the active provider, and Save
  becomes available only after its fields (and, for a hosted provider, its
  credential) are all present

#### Scenario: card status reflects real state

- **WHEN** the section is unlocked and a provider's section is incomplete or
  its credential is absent
- **THEN** its card reports that, rather than a fixed configured status

#### Scenario: first save is confirmed as permanent

- **WHEN** the operator saves a complete pane for the first time
- **THEN** a warning stating the choice is permanent is presented, and the
  write proceeds only after the operator confirms it

#### Scenario: switching provider is confirmed

- **WHEN** the section is not yet locked and the operator has more than one
  complete, credentialed pane available
- **THEN** confirming and saving either one locks the section to that provider,
  so a provider switch is only ever possible before the section's first save —
  never between two already-saved providers, since no second save exists

#### Scenario: the section locks after its first save

- **WHEN** a provider has been selected and saved
- **THEN** every card and pane in the section renders read-only, no Save
  control is offered anywhere in the section, and no field of any provider —
  including the locked provider's own base URL — can be changed through it

#### Scenario: operator switches to OpenAI

- **WHEN** the operator confirms and saves the completed, credentialed OpenAI
  pane on an unselected section
- **THEN** only `embedding.json` changes, the section locks to OpenAI, and the
  next item resolves OpenAI

#### Scenario: a hosted pane cannot save without its credential

- **WHEN** the operator fills a hosted provider's fields but has not saved its
  credential
- **THEN** Save is unavailable, and the section remains unlocked and
  unselected

#### Scenario: first generic selection requires complete settings

- **WHEN** no compatible section has been saved yet and the operator clicks its
  card
- **THEN** its pane opens without changing the active provider; Save becomes
  available only once its fields and its `EMBEDDING_API_KEY` credential are all
  present

#### Scenario: missing credential is visible without exposing it

- **WHEN** the operator opens a hosted provider's pane whose credential is
  absent from the store
- **THEN** the pane shows missing status, renders no credential value, names
  the fixed credential it needs, and Save remains unavailable until it is saved

#### Scenario: hosted data egress is visible

- **WHEN** the operator views a hosted provider's pane before its first save
- **THEN** the pane states that summaries leave the machine and calls may cost
  money, including during unattended scheduler runs

#### Scenario: embedding endpoint is separate from the engine endpoint

- **WHEN** the operator sets the OMLX embedding API root
- **THEN** only `embedding.json` changes, the engine section's local endpoint is
  untouched, and the section explains why they are separate

#### Scenario: compatible vector space is explicit

- **WHEN** compatible settings are saved
- **THEN** state contains `space_id` and the active identity displays as
  `openai_compatible:<space_id>`

#### Scenario: sections remain independent

- **WHEN** embedding settings are saved
- **THEN** `engine.json`, `coding-agents.json`, `schedule.json`,
  `language.json`, and `secrets.json` remain unchanged except for the
  credential the operator explicitly saved

#### Scenario: corrupt state does not break repair UI

- **WHEN** `embedding.json` is corrupt and `/settings` renders
- **THEN** the section renders as unselected with prefilled suggestions, logs the
  error, and renders without a client-side default flash

### Requirement: The settings page owns the local chat endpoint and says when it applies

The engine section SHALL own the local chat endpoint entirely, reading and
writing it in `~/.next-signal/engine.json`. It SHALL NOT display, inherit, or
fall back to a value from the process environment, and an endpoint that has
never been saved SHALL render as unset rather than as an environment value. The
OMLX pane SHALL NOT offer a credential field.

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

## ADDED Requirements

### Requirement: The settings page owns engine selection and starts with nothing chosen

The settings page SHALL carry an **Engine** section, collapsible, choosing which
backend next-signal calls for chat: `omlx`, `deepseek`, `codex_cli`, or
`claude_cli`. Collapsed, the section SHALL show the selected engine and its
fallback (or that none is selected); expanding it is required to change
anything.

No engine SHALL be selected as primary on a fresh install. A section whose
stored preference file does not exist, or whose `primary` has never been
explicitly saved by an operator, SHALL render with no card marked selected —
`configs/models.yaml`'s shipped profiles MAY still supply prefilled suggested
values into an engine's own pane, exactly as `models.yaml::embedders` does for
Radar Embedding, but SHALL NOT cause any engine to be treated as chosen.

Selecting which engine is primary — including switching from one
already-configured engine to another — SHALL commit only through an explicit
save action, not on the click that selects a card. This applies to the
primary/fallback selection itself; an engine's own pane fields (model,
parallelism, reasoning effort, and similar) continue to commit through that
pane's own explicit Save, as already specified for the interdependent-group
controls this page uses elsewhere.

The OMLX card's status SHALL be computed from whether a base URL has actually
been saved for it, exactly as every Radar Embedding card's status is computed
from its own saved completeness. It SHALL NOT report a fixed "configured"
status irrespective of whether an endpoint is present.

The DeepSeek pane SHALL render its `DEEPSEEK_API_KEY` credential input inline,
using a server-computed presence boolean read from the credential store, in the
same shape Radar Embedding's hosted panes use for their own credentials. The
OMLX pane SHALL NOT offer a credential field.

This section is unlocked and remains changeable for the life of the install —
unlike Radar Embedding and Knowledge Embedding, a chat engine choice carries no
vector-space consequence, so there is nothing here that switching would
invalidate.

#### Scenario: fresh install selects no engine

- **WHEN** the operator opens `/settings` on an install where no engine
  preference has ever been saved
- **THEN** no card reads as selected, and the OMLX pane's prefilled model
  suggestion is shown unsaved

#### Scenario: OMLX status reflects a saved endpoint

- **WHEN** no OMLX base URL has been saved
- **THEN** the OMLX card does not report a configured status, regardless of
  what model string is prefilled

#### Scenario: selecting a different primary requires an explicit commit

- **WHEN** the operator clicks a different, already-configured engine's card
- **THEN** no write occurs on that click alone, and the new selection is
  written only after the operator takes an explicit save action

#### Scenario: DeepSeek credential is entered inline

- **WHEN** the operator opens the DeepSeek pane and saves an API key
- **THEN** `DEEPSEEK_API_KEY` is written to the credential store and the pane
  reports it as present

### Requirement: The settings page owns an RSS section for the Folo credential

The settings page SHALL carry an **RSS** section, collapsible, that owns entry
of `FOLO_TOKEN` — the credential info-radar's Folo source and the
Subscriptions page depend on — including the assisted browser sign-in
specified separately. Collapsed, the section SHALL show whether the credential
is present; expanding it is required to enter, replace, or clear it, or to
start an assisted sign-in.

Saving or clearing `FOLO_TOKEN` from this section SHALL NOT read, write, or
invalidate any other section's state.

#### Scenario: RSS section reflects Folo credential state

- **WHEN** `FOLO_TOKEN` is present in the credential store
- **THEN** the collapsed RSS section shows it as connected, and expanding it
  offers to replace or clear it

### Requirement: The settings page owns the knowledge-base embedding provider

The settings page SHALL carry a **Knowledge Embedding** section, collapsible,
that configures and initializes GBrain's embedding provider — the knowledge
base's vector search, distinct from and independent of the Radar Embedding
section's dedup embedder. Collapsed, the section SHALL show the configured
provider and model, or that GBrain is not yet initialized; expanding it is
required to change anything while it is still unlocked.

No provider SHALL be selected on a fresh install. The section SHALL present a
pane per GBrain-supported provider (`openai`, `voyage`, `google`, `ollama`,
`lmstudio`, `llama-server`), each accepting the model identifier GBrain expects
and, for the four hosted providers, an inline credential input
(`OPENAI_API_KEY`, `VOYAGE_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`
respectively for `openai`, `voyage`, `google`) using a server-computed presence
boolean; `ollama`, `lmstudio`, and `llama-server` SHALL offer no credential
field, matching that they require none. The `openai` credential is the one
GBrain's own subprocess reads from its environment, independent of the Radar
Embedding section's `RADAR_EMBEDDING_OPENAI_API_KEY`.

Saving a pane whose provider needs a credential SHALL require that credential
to already be present in the store, matching the rule Radar Embedding's hosted
panes follow, so GBrain initialization is never attempted in a state guaranteed
to fail.

Before the save that initializes GBrain, the section SHALL present an explicit
warning stating that the embedding model is permanent for the life of this
GBrain instance, cannot be changed afterward without a destructive migration
outside this dashboard, and require the operator to confirm it before the
initialization call proceeds.

Confirming SHALL invoke `next-signal knowledge gbrain-init --embedding-model
<provider>:<model>` and wait for its result — this action needs the command's
outcome before it can decide whether to lock the section, so it SHALL NOT use
the page's fire-and-forget detached-subprocess launcher. A successful result
SHALL lock the section (no further pane, credential, or provider change offered
through it) and record the configured provider and model for the collapsed
summary. A failed result (including "already initialized", which SHALL NOT be
treated as success) SHALL leave the section unlocked, report the command's
error, and change no stored selection.

The section SHALL report GBrain's readiness as one of three distinct states,
computed by the dashboard itself rather than by shelling out to `next-signal
doctor`: **not initialized** (no brain exists yet — the expected state before
this section's first successful save), **initialized but credential missing**
(a brain exists with a recorded provider that needs a credential currently
absent from the store), and **ready**. An indeterminate read of GBrain's own
config SHALL be reported distinctly from both "not initialized" and "ready"
rather than guessed as either.

#### Scenario: fresh install shows GBrain uninitialized

- **WHEN** the operator opens `/settings` before GBrain has ever been
  initialized
- **THEN** the section reports "not initialized", no provider card reads as
  selected, and the panes show prefilled suggestions that have not been saved

#### Scenario: a hosted pane cannot initialize without its credential

- **WHEN** the operator fills the OpenAI pane's model field but has not saved
  `OPENAI_API_KEY`
- **THEN** the initializing save is unavailable and no `gbrain-init` call is
  made

#### Scenario: initialization is confirmed as permanent

- **WHEN** the operator triggers the save for a complete, credentialed pane
- **THEN** a warning stating the model choice is permanent for this GBrain
  instance is presented, and `gbrain-init` runs only after the operator
  confirms it

#### Scenario: successful initialization locks the section

- **WHEN** `next-signal knowledge gbrain-init --embedding-model
  <provider>:<model>` succeeds
- **THEN** the section locks, the collapsed summary shows the configured
  provider and model, and readiness reports "ready" once the credential is
  present (or immediately, for a local provider that needs none)

#### Scenario: an already-initialized brain does not lock as new state

- **WHEN** `gbrain-init` fails because a brain already exists
- **THEN** the error is reported, no card is marked freshly selected by this
  attempt, and the section's lock state instead reflects whatever GBrain's own
  config already records

#### Scenario: initialized but missing credential is reported distinctly

- **WHEN** GBrain's config records a provider whose credential is currently
  absent from the store
- **THEN** readiness reports "initialized but credential missing", distinct
  from both "not initialized" and "ready"

#### Scenario: a local provider needs no credential to be ready

- **WHEN** GBrain is initialized with `ollama`, `lmstudio`, or `llama-server`
- **THEN** readiness reports "ready" with no credential check performed
