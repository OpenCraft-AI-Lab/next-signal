## Why

The dashboard settings page's Engine, Radar Embedding, and Knowledge Embedding
sections each expose more than one commit action per section (an inline
credential Save/Clear nested inside a pane, alongside a separate
"Save configuration" and/or "Apply selection" button). This is confusing on
its own, and in the Engine section it produces real bugs: "Apply selection"
can silently discard unsaved field edits, and it can promote an engine to
primary with nothing actually configured. The other two sections already
converge on a single commit per pane; Engine still runs the older,
multi-action pattern the settings redesign was supposed to replace everywhere.

## What Changes

- No section renders a *per-field* inline commit control anymore (the old
  credential Save/Clear nested inside a pane). Radar Embedding and Knowledge
  Embedding go further: each is a single fused commit per section (select +
  configure + credential + permanent lock), exactly as before this change.
- The credential field inside a locking pane (Radar Embedding's OpenAI/Custom
  endpoint, Knowledge Embedding's OpenAI/Voyage/Google, Engine's DeepSeek)
  becomes a plain masked input with no Save/Clear of its own; its value is
  folded into the pane's own draft and committed by that pane's own save. A
  shared `InlineCredential` component that still saves/clears immediately
  remains available for credentials with no section-level commit concept
  (e.g. RSS/Folo) — untouched by this change.
- Engine keeps **two** independent, section-level actions rather than one —
  unlike the other two sections, it genuinely has two independent axes of
  state (which engine is active; that engine's own configuration), and after
  shipping a version that fused them behind one button, hands-on use showed
  that read as confusing rather than clarifying. Each action now commits
  **immediately** and **fully independently** of the other:
  - **"Use as primary"**, on the open pane, writes that engine as primary the
    instant it's clicked (clearing the fallback slot if it pointed at the
    same engine). No staging, no confirm dialog — switching primary is fully
    reversible, unlike the two locking Embedding sections.
  - **"Save configuration"**, on a pane, writes only that engine's own
    fields (and DeepSeek's credential, if changed) — it never touches the
    primary/fallback pointer, and a pending primary click has no effect on
    whether it's enabled, or vice versa.
  - The **Fallback** selector commits the instant it changes too, the same
    "complete choice → commit on change" pattern the page's Segmented
    controls already use — there is no staged section state left to bundle
    it into.
- "Use as primary" is disabled while the engine it would promote is
  incomplete (no model, missing DeepSeek key, CLI not connected), evaluated
  against that engine's last-*saved* configuration — an engine can no longer
  become primary while unconfigured. "Use as primary" also renders as a
  clearly primary-styled button rather than a subtle ghost control, and
  toasts its own distinct message ("Engine selection applied") separate from
  a pane's own save ("Engine settings saved") — the two are genuinely
  different decisions and now look, behave, and report like it.
- The selected/checkmark indicator and `aria-pressed` on Engine's cards track
  "which engine is actually saved as primary," matching how Radar Embedding
  and Knowledge Embedding already behave. The dead `set-engineopen` CSS hook
  (referenced in Radar/Knowledge Embedding's JSX with no matching rule) gets
  real styling, shared by all three sections' cards for the "open but not
  the committed choice" state.
- `saveCredential`/`deleteCredential` gain a server-side check rejecting a
  write to a credential name whose owning section (Radar Embedding, Knowledge
  Embedding) is already locked — defense in depth behind the disabled UI,
  matching the check `setEmbeddingPreferences` already has for the
  provider/model half of the same lock.

## Capabilities

### New Capabilities
- `dashboard-settings-commit`: the settings page's per-section commit
  pattern — a section that fuses selection and configuration into one
  permanent commit (Radar Embedding, Knowledge Embedding), or a section where
  configuring an option and activating it are two independent, immediately-
  committing actions with no shared draft between them (Engine) — either way
  a completed section's selection indicator reflects only the actually-saved
  choice, never merely the option currently open for viewing.

### Modified Capabilities
- `core-credentials`: `saveCredential`/`deleteCredential` reject a write to a
  credential name belonging to an already-locked section (Radar Embedding,
  Knowledge Embedding), rather than relying solely on the client to withhold
  the request.

## Impact

- `dashboard/components/settings/engine-section.tsx` — primary rework: an
  immediate `activatePrimary(engine)` action and an immediate Fallback-change
  action, both independent of each pane's own field/credential save;
  completeness gate on the primary action alone, evaluated against last-
  saved state; checkmark/aria-pressed keyed off `saved.primary`.
- `dashboard/components/settings/embedding-section.tsx`,
  `dashboard/components/settings/knowledge-embedding-section.tsx` — fold the
  credential field into the existing single-save pane instead of using
  `InlineCredential`.
- `dashboard/components/settings/inline-credential.tsx` — split into a
  presentational `CredentialField` (input + status, no buttons) and the
  existing self-saving `InlineCredential` built on top of it, so RSS/Folo and
  any other genuinely independent credential keeps today's behavior unchanged.
- `dashboard/lib/actions/secrets.ts` — `saveCredential`/`deleteCredential`
  gain a lock check for the credential names owned by Radar Embedding and
  Knowledge Embedding.
- `dashboard/app/globals.css` — real styling for the "open, not yet
  committed" card state, shared by all three sections.
- `dashboard/lib/i18n/dictionaries.ts` (both locales) — button copy where a
  label's meaning changes, including restoring a distinct "Engine selection
  applied" toast for the primary action.
- No change to `next_signal` (Python), to `configs/`, or to any state file's
  on-disk schema — `engine.json`, `embedding.json`, and `secrets.json` keep
  their existing shape and validation.
