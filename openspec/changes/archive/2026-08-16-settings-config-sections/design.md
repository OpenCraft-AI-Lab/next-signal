## Context

See `proposal.md` for motivation. Current state, as traced through the code
this change touches:

- `/settings` (`dashboard-shell`) currently has an Engine section, a single
  Embedding section (radar dedup only), and one flat Credentials section
  rendering every entry in `dashboard/lib/secrets.ts::CREDENTIAL_NAMES`.
- Credentials resolve through `next_signal.core.secrets` (`secrets.json`,
  read at call time, never from the environment). Embedding resolves through
  `next_signal.core.embedding_preferences` / `next_signal.core.models.get_embedder()`.
- GBrain's embedding provider is configured entirely outside the dashboard
  today, via `next-signal knowledge gbrain-init --embedding-model
  <provider>:<model>` (`core-cli`), which refuses a second run once a brain
  exists — the schema is sized to the model permanently. Its readiness is a
  three-state check (`_check_gbrain()` in `cli.py`) currently reachable only
  through `next-signal doctor`.
- `VOYAGE_API_KEY` and `GOOGLE_GENERATIVE_AI_API_KEY` are already resolved
  server-side (`secrets.py::CREDENTIAL_NAMES`) for GBrain's non-OpenAI
  providers, but absent from `dashboard/lib/secrets.ts` and the i18n
  dictionary, so they render no control anywhere today.
- Radar Embedding currently lets an operator switch between two
  already-complete providers, gated by a `window.confirm()` warning about
  parked dedup memory — not locked.
- Engine's `configuredDefaults()` unconditionally maps `models.yaml`'s `local`
  profile to `primary: "omlx"` on a fresh install, and the OMLX card's status
  is hardcoded to "configured" regardless of whether a base URL is saved.

## Goals / Non-Goals

**Goals:**
- Reorganize `/settings` into collapsible, domain-owned sections (Engine,
  Radar Embedding, Knowledge Embedding, RSS) with credential inputs inline.
- Make Radar Embedding and the new Knowledge Embedding section lock in full
  after their first successful save.
- Wire GBrain initialization into the dashboard for the first time.
- Shrink the resolved credential set to exactly what has a real consumer with
  no graceful fallback.
- Fix the two concrete correctness gaps this work touches directly (Engine's
  false-positive OMLX status and default selection; the compatible pane's
  save-without-credential gap).

**Non-Goals:**
- Moving Codex/Claude CLI OAuth out of their provider-owned Docker volumes.
- Collapsing a locked section down to a single summary line — it stays
  visually expanded but disabled.
- An onboarding/readiness summary banner.
- Any change to `gbrain-init`'s own CLI contract (`core-cli`) — the dashboard
  only wraps the existing command.
- Any change to the Language or Schedule sections' existing behavior.
- A migration path for renamed or removed credentials — this project has none
  by design (`core-credentials`: "no migration or import path"), and this
  change does not introduce one.

## Decisions

**Full-section lock, not per-field.** `core/embedding_preferences.py`'s
existing `embedder_identity()` already draws the line between fields that
define a vector space (`model`, or `space_id` for the compatible provider) and
fields that don't (`base_url`). A per-field unlock scheme would be a strict
superset of safety over locking everything, but it costs three separate
disabled-field implementations (one per provider pane) for a convenience —
moving an already-configured server's address — with a working escape hatch
already available (state files in this project are hand-editable by design;
see `engine-preferences.ts`'s and `schedule.py`'s own comments to that effect).
Locking the whole section was chosen deliberately over the more capable
version for that reason.

**Knowledge Embedding is a new requirement inside `dashboard-shell`, not a new
capability.** Every existing `/settings` section — Schedule, Radar Embedding,
Credentials, Folo sign-in, the local chat endpoint — is already specified as a
`dashboard-shell` requirement rather than its own capability. Introducing a
`dashboard-knowledge-embedding` capability for one more section would break
that established organization for no benefit; nothing about this section is
reused outside the settings page.

**`gbrain-init`'s dashboard action needs synchronous completion, not
`spawnCliDetached`.** `dashboard-shell`'s existing "Shared `next-signal`
subprocess launcher" requirement is explicitly fire-and-forget — it returns
before the subprocess finishes and its success message is always "started,"
never "completed." The Knowledge Embedding section needs the actual exit
status before it can decide whether to lock, so this one call needs a
different, awaited invocation path rather than reusing that launcher.

**`RADAR_EMBEDDING_OPENAI_API_KEY` is a new name; GBrain's `OPENAI_API_KEY`
keeps its old one.** The two currently share one stored credential
coincidentally — both happen to be named after the same env-var convention,
not because they're the same credential. Only the radar side's name is
next-signal's own choice: it's read directly, in-process, by
`core/models.py`. GBrain's copy is dictated externally — its subprocess reads
`OPENAI_API_KEY` from its own environment, the same way it reads
`VOYAGE_API_KEY` and `GOOGLE_GENERATIVE_AI_API_KEY` — so renaming that side
would need a store-key-to-env-var-name translation layer in `gbrain_env()` for
no benefit. Only the free side moves.

**Four credentials are removed from the resolved set, not just hidden in the
UI.** `ANTHROPIC_API_KEY` and `GOOGLE_API_KEY` have zero live consumers.
`GITHUB_TOKEN` and `OMLX_API_KEY` are both read with `get_secret()` (never
`require_secret()`) at every call site, meaning their absence is already a
normal, permanent, designed-for state, not a "not configured yet" state a UI
needs to surface. Removing them from `secrets.py::CREDENTIAL_NAMES` is safe
because nothing enforces store-write membership against that enumeration
today (`save_secret()` only validates the name's character pattern) — the
removal only stops the settings page from rendering a control for them; the
underlying `get_secret("GITHUB_TOKEN")` / `get_secret("OMLX_API_KEY")` call
sites are untouched and simply always observe absence, which is the branch
they were already written for.

**`child_env()` keeps stripping the four retired names even though they leave
`CREDENTIAL_NAMES`.** Discovered during implementation, not anticipated when
this design was written: `child_env()`'s environment-copy stripping loop used
`CREDENTIAL_NAMES` as its "every known credential" set, so removing
`ANTHROPIC_API_KEY`/`GOOGLE_API_KEY`/`GITHUB_TOKEN`/`OMLX_API_KEY` from that
enumeration would have silently stopped stripping them from a copied
environment — reopening exactly the stale-`.env`-leaks-into-a-child class of
bug `core-credentials`' "Child processes receive credentials only when named"
requirement exists to close, and breaking the existing regression test written
for it. Fixed by adding a second, `child_env()`-only constant
(`_RETIRED_ENV_NAMES`) that keeps these four names in the strip set without
reintroducing a settings-page control or a resolved-credential status for any
of them. This is a pure implementation-time addition — no proposal or spec
text changes, since `core-credentials`' existing stripping requirement was
never modified by this change's deltas and this fix is what keeps it holding.

**Engine gets real parity with Radar Embedding, not a UI-only fix — resolved
during implementation.** Tracing `configuredDefaults()`'s Python counterpart
surfaced that `EnginePreferences.primary` was non-nullable and
`agents/stage.py::stage_job()` — the entry point for every production stage
job — read it unconditionally, always resolving to `"omlx"` when nothing was
saved. A UI-only fix (dashboard shows nothing selected, backend still
silently runs on OMLX) would have created a new UI/backend mismatch of the
same shape as the bug being fixed. The user directed full parity: `primary`
is now `Engine | None` on both sides, and `stage_job()` raises a distinct
`EngineNotSelected` before any provider call when unselected — mirroring
`EmbedderNotSelected`, except there is no degraded mode to catch it: a
production stage job's whole purpose is an LLM call, so this blocks the job
rather than being caught by a conservative-default consumer the way the
dedup gate handles the embedding case. `next-signal doctor` gained a matching
check. `core-models` and `core-cli` were added as modified capabilities as a
result — neither was scoped at propose time. AgentOS's interactive agents are
unaffected: they read their model from their own YAML profile directly and
never consult `engine.json`'s primary selection.

**GBrain readiness is computed dashboard-natively, not via `next-signal
doctor`.** This matches how the existing Radar Embedding section already
avoids depending on Python `doctor` output — it reads `embedding.json` and
credential presence directly. The new section reads GBrain's own
`.gbrain/config.json` (via the same helpers `_check_gbrain()` already calls:
`brain_initialised()`, `configured_embedding_model()`,
`credential_for_model()`) rather than parsing `doctor`'s text output or
shelling out to it.

## Risks / Trade-offs

- **Full-section lock removes the ability to rotate a hosted provider's
  credential once its section is locked, even though rotation doesn't change
  the vector space.** → Mitigation: `secrets.json` remains directly editable
  outside the UI, consistent with how this project already treats its other
  small state files as hand-editable; a future change can carve out
  credential-only rotation without revisiting the identity-defining fields, if
  this turns out to matter in practice.
- **Renaming the radar OpenAI credential silently breaks dedup on any existing
  install that had `OPENAI_API_KEY` set for it, until the operator notices.**
  → Mitigation: the existing `doctor` embedder check and the section's own
  missing-credential status both report the new name by its exact name
  immediately after upgrade — nothing here degrades to a silent, unreported
  failure.
- **`gbrain-init` is a real subprocess call (existing 300s timeout) invoked
  synchronously from a settings-page request, unlike every other action on
  this page.** → Mitigation: accepted directly by the synchronous-completion
  decision above; the section shows a pending state for the call's duration,
  the same shape the Schedule section already uses to report a long-running
  chain in progress.
- **Removing `OMLX_API_KEY` from the UI entirely leaves no supported path for
  an operator whose local server enforces its own token.** → Mitigation:
  raised and accepted explicitly during exploration of this change — no
  evidence this is hit in practice, and the store still accepts the value if
  hand-edited into `secrets.json`, which the untouched `get_secret()` call
  sites continue to read.

## Migration Plan

No data migration — consistent with this project's existing no-migration
stance on credentials (`core-credentials`). Deployment sequencing only:

1. Backend changes (`secrets.py` enumeration, `models.py` credential name
   lookup) ship in the same release as the dashboard changes that depend on
   them — a split release would leave the UI referencing a name the backend
   doesn't resolve, or vice versa.
2. Rollback is a normal container redeploy: `embedding.json` and
   `secrets.json`'s on-disk formats are unchanged (only which names are
   read), so reverting to the prior image continues to work off the same
   state files. The one caveat is that a `RADAR_EMBEDDING_OPENAI_API_KEY`
   saved under this change is invisible to a rolled-back image's
   `OPENAI_API_KEY` read, and vice versa, for the duration of the rollback.
