## Context

See `proposal.md` - Why. Three sections, two current shapes:

- **Radar Embedding / Knowledge Embedding** already fuse "select" and
  "configure" into one pane-level save (`saveAndSelect` /
  `initializeAndLock`). Their only leftover multi-action surface is the
  credential field, which uses `InlineCredential` — a component with its own
  immediate Save/Clear, writing straight to the credential store independent
  of the pane's own save.
- **Engine** has three independent, uncoordinated writes: each pane's own
  Save (persists that engine's params regardless of primary), DeepSeek's
  nested `InlineCredential` (immediate), and "Apply selection" (writes
  `primary`/`fallback` from `saved`, not from whatever is currently open and
  unsaved).

Engine is genuinely different from the other two, not just behind on the same
pattern: it has two independent axes of state (which engine is active; each
engine's own parameters, which can be pre-configured while inactive). The
other two sections have only one axis (an option's configuration and its
selection are the same event, since nothing can be configured without also
becoming the permanent, only choice). The design has to preserve that
difference rather than paper over it — collapsing Engine to a single
selection+configuration event the way Embedding works would remove the
ability to pre-stage a fallback engine's settings.

**Revised after shipping a first version.** That first version kept the two
axes independently *editable* but fused them behind one shared commit: opening
a pane, clicking "Use as primary," and clicking "Save configuration" all fed
one draft, and only the Save click actually wrote anything, including the
primary switch. Hands-on use showed this reads as one button doing two
different jobs — an operator watching "Use as primary" do nothing on its own
click reasonably reads that as broken, not as "staged." The two axes stay
independent; what changes here is that *committing* them independent too —
each action writes for itself, on its own click, with no shared draft. See
"The active-engine pointer commits immediately" below.

## Goals / Non-Goals

**Goals:**
- No per-field inline commit control anywhere; Radar Embedding and Knowledge
  Embedding each keep exactly one commit control for the whole section.
  Engine keeps two — because it has two genuinely independent decisions — but
  each is its own single, immediately-effective action with no shared draft.
- Fix the concrete Engine bugs (stale-value apply, no completeness gate,
  checkmark tracking the wrong state) as a side effect of the same
  restructure, not as separate patches.
- Reuse one component for "masked credential input with a status badge" so
  the three locking panes and the still-independent uses (RSS/Folo) don't
  duplicate markup.

**Non-Goals:**
- Changing what fields exist per provider/engine, or any on-disk state
  schema (`engine.json`, `embedding.json`, `secrets.json` shapes are
  untouched).
- Changing Codex/Claude's OAuth connect/disconnect flow — it stays an
  immediate action (see Decisions).
- RSS/Folo's credential handling — out of scope, keeps today's
  `InlineCredential` behavior.

## Decisions

### A pane's own draft, committed by its own save — never the pointer

Each of Radar/Knowledge Embedding's panes, and each of Engine's four panes,
holds one local "draft" object for that pane's own fields (plus a credential
input where relevant). "Save configuration" always writes from this draft,
never from a previously saved snapshot — this is what directly fixes the
"Apply selection applies stale values" bug, because there is no longer a
second, disconnected source of truth for a pane's own fields to fall out of
sync with.

For Engine, this draft is scoped to that pane's own fields and credential
only — it does **not** include the primary/fallback pointer. Saving a pane
never moves the pointer, so pre-configuring a non-active engine (or rotating
DeepSeek's key) never risks switching primary as a side effect, and there is
nothing for "Use as primary" to leave half-done if the pane itself is never
saved.

### The active-engine pointer commits immediately, with no draft

"Use as primary" and the Fallback selector write straight to `engine.json`
the instant they're used — `activatePrimary(engine)` on a click, the Fallback
`<select>` on a change — updating local `saved` state and toasting
immediately after. There is no staged `proposedPrimary`/`proposedFallback` to
reconcile, and nothing about a pane's own dirty/save state feeds into either
action or is affected by them.

**Alternative considered (shipped first, then reverted)**: stage the pointer
alongside the open pane's draft and commit both together from whichever
pane's "Save configuration" is clicked — the shape described in the previous
revision of this section. Rejected after hands-on use: it reads as one commit
action serving two decisions, and clicking "Use as primary" appearing to do
nothing on its own (by design — it only staged) reasonably reads as broken.
Decoupling the *commit*, not just the editing, of the two axes is what
actually resolves the confusion; keeping "Use as primary" near the top of the
pane and "Save configuration" at the bottom (unchanged from the first
version) is what makes the two reversible-vs-persisted mental models legible
side by side.

### The completeness gate moves onto the primary action itself

`activatePrimary(engine)` is disabled while `engine` is incomplete — no model, a
DeepSeek key missing from the credential store, or (for Codex/Claude) no
connected CLI session. This is evaluated against that engine's last **saved**
configuration (`saved.omlx`/`saved.deepseek`/`codex`/`claude` + `auth`), not
whatever is currently typed but unsaved in the pane's own draft — there is no
longer a joint commit to gate, and only a saved configuration is ever what
the pipeline actually resolves. A pane's own `canSave` (its Save
configuration gate) is unaffected and unrelated: it only asks whether that
pane's own fields are individually valid to write, the same question it
always asked, regardless of primary status.

**Alternative considered**: validate only at write time on the server.
Rejected as the sole mechanism — the client-side gate is what actually
prevents the confusing "primary switched to something that doesn't work"
outcome the operator sees; server validation is defense in depth, not the
primary UX signal (Engine's primary/fallback pointer has no server-side lock
concept the way the two Embedding sections do, since switching it is always
reversible).

### Split `InlineCredential` into a dumb field and a self-saving wrapper

`CredentialField`: masked input + presence status badge, controlled
value/onChange, no buttons. `InlineCredential` becomes a thin wrapper adding
its own immediate Save/Clear on top of `CredentialField`, kept for the one
remaining case that's genuinely independent of any section-level commit
(RSS/Folo's token today; anything else structurally similar later).

The three locking panes (Radar Embedding's OpenAI/Custom, Knowledge
Embedding's OpenAI/Voyage/Google) and Engine's DeepSeek pane all switch to
`CredentialField`, wiring its value into the pane's own draft instead of
having it self-save. Empty input with a credential already present means
"keep the existing value" (same placeholder convention `InlineCredential`
already uses); non-empty input means "replace it."

**Alternative considered**: give `InlineCredential` a `deferred` prop that
suppresses its own buttons but keeps its internal state model. Rejected —
the internal state (its own `useState` for the typed value, its own
save/clear handlers) is exactly the thing causing the fragmentation (Reset
not clearing it, dirty-tracking not seeing it); a prop flag would keep that
state machine alive and just hide its buttons, not fix the actual problem.
Splitting the component removes the duplicate state entirely.

### DeepSeek's credential folds into the same pattern

Per user direction, no section keeps a "live, independent" credential once
it has a section-level commit action available — DeepSeek's key moves into
its pane's draft like everywhere else in Engine. It's still rotatable at any
time; rotating it just means: open the DeepSeek pane, type the new value,
commit (which, per the decision above, does not require moving the active
pointer).

### Selection indicator keys off committed state, not open state

Engine's card checkmark and `aria-pressed` switch from `selected === engine`
(open) to `saved.primary === engine` (committed) — the exact pattern Radar
and Knowledge Embedding already use. The existing `set-engineopen` class
(currently dead CSS) gets real styling and Engine's cards adopt the same
three-state visual treatment (active / open-not-active / neither) all three
sections now share.

### Server-side lock check for credentials, as defense in depth

`saveCredential`/`deleteCredential` gain a check against the owning
section's lock state for the five credential names that belong to a
lockable section, mirroring `setEmbeddingPreferences`'s existing check.
Bundled into this change rather than deferred: the change is already
touching every call site of these two credential names, and the pattern to
copy already exists in the same codebase — deferring it would mean
reintroducing the exact asymmetry (model/provider protected twice,
credential protected once) this whole change is meant to remove.

### Codex/Claude OAuth stays immediate

Connect/Disconnect opens a popup and drives a live external auth flow — it
cannot be staged into a draft and committed later; "connected" is a fact
about an external session, not a value the operator typed. It remains an
immediate action outside the commit pattern. Choosing Codex or Claude as the
active engine still goes through the same commit action as any other
engine; only the auth handshake itself stays immediate.

## Risks / Trade-offs

- **[Two independent immediate actions on one pane could still read as one
  decision]** → mitigated by keeping their screen positions distinct (top vs.
  bottom of the pane, unchanged from the first version), giving "Use as
  primary" clearly primary/solid button styling instead of a subtle ghost
  control, and toasting each with its own distinct message.
- **[Server-side lock check could reject a legitimate retry]** → e.g. a
  double-submit racing the lock write. Mitigated by making the check read
  the same lock state the pane already displays; a genuine race is rare
  (requires two near-simultaneous commits) and fails safe (rejects) rather
  than silently succeeding.

## Migration Plan

No data migration — no on-disk schema changes. Deploy is a normal dashboard
rebuild. Rollback is reverting the dashboard build; no backend or state-file
compatibility concern either direction.

## Open Questions

- Exact visual treatment for the "open, not yet committed" card state
  (opacity, border, badge) — a design-system detail, not a behavioral one.
