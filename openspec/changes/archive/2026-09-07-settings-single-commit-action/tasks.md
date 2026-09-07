## 1. Shared credential component

- [x] 1.1 Extract `CredentialField` from `inline-credential.tsx`: masked
      input + presence status badge, controlled `value`/`onChange`, no
      buttons.
- [x] 1.2 Rebuild `InlineCredential` on top of `CredentialField`, adding its
      own immediate Save/Clear — behavior unchanged for existing callers
      (Engine's fallback UI if any, RSS/Folo).
- [x] 1.3 Confirm RSS/Folo's credential usage is untouched (still uses
      `InlineCredential`, still self-saves immediately).

## 2. Radar Embedding section

- [x] 2.1 Replace `InlineCredential` with `CredentialField` in the OpenAI and
      Custom-endpoint panes; fold the typed value into each pane's own draft
      state alongside its other fields.
- [x] 2.2 Update each pane's dirty/`canSave` computation to include the
      credential input (empty + already-present credential = keep existing;
      non-empty = replace).
- [x] 2.3 Update `saveAndSelect` to write the credential (if changed) before
      writing/locking the embedding preferences, so a mid-flight failure
      after the credential write is safely retryable (retry sees the
      credential as already present).
- [x] 2.4 Update Reset to also discard an unsaved, not-yet-committed
      credential input.
- [x] 2.5 Verify the OMLX pane (no credential) is unaffected.

## 3. Knowledge Embedding section

- [x] 3.1 Replace `InlineCredential` with `CredentialField` in the OpenAI,
      Voyage, and Google panes; fold the typed value into the pane's draft.
- [x] 3.2 Update `canSave`/dirty logic the same way as task 2.2.
- [x] 3.3 Update `initializeAndLock` to save the credential (if changed)
      before invoking `gbrain-init`, so the CLI's own credential resolution
      at call time sees the new value.
- [x] 3.4 Update Reset the same way as task 2.4.
- [x] 3.5 Verify Ollama/LM Studio/llama-server panes (no credential) are
      unaffected.

## 4. Credential store defense in depth

- [x] 4.1 Add a lock check to `saveCredential`/`deleteCredential` (or a thin
      wrapper they delegate to) for `RADAR_EMBEDDING_OPENAI_API_KEY`,
      `EMBEDDING_API_KEY`, `OPENAI_API_KEY`, `VOYAGE_API_KEY`, and
      `GOOGLE_GENERATIVE_AI_API_KEY`, reading each credential's owning
      section's lock state before allowing the write.
- [x] 4.2 Confirm `DEEPSEEK_API_KEY` and `FOLO_TOKEN` remain writable at any
      time (no lock concept for their owning sections).
- [x] 4.3 Add coverage for: locked section rejects credential save; locked
      section rejects credential delete; unlocked section's credential still
      writes normally.

## 5. Engine section rework

**Revised**: the first implementation staged the primary/fallback pointer
into the same draft as the open pane's fields and only wrote it when "Save
configuration" was clicked. Hands-on testing showed that reads as one commit
serving two decisions and makes "Use as primary" look inert on its own click.
Tasks below now build two fully independent, immediately-committing actions
instead — no shared draft, no staging for the pointer at all.

- [x] 5.1 *(superseded by 5.1b)* ~~Replace the separate `selected` / per-pane
      `saved`+`value` / `pendingFallback` state with one draft per
      currently-open option, including the candidate primary/fallback
      pointer.~~
- [x] 5.1b Remove the staging machinery entirely: no `proposedPrimary`,
      `proposedFallback`, `sectionDirty`, `willBePrimary`, `effectiveFallback`,
      or `resetSection`. `EngineSection` keeps only `saved` (persisted state)
      and `open` (which pane is showing — pure navigation, changed only by
      clicking a card).
- [x] 5.2 Replace `InlineCredential` with `CredentialField` in the DeepSeek
      pane; fold its value into that pane's own draft (task 1 dependency).
      Unaffected by this revision — DeepSeek's credential stays part of its
      pane's own save, not the primary action.
- [x] 5.3 Add one immediate `activatePrimary(engine)` handler on `EngineSection`:
      writes `{...saved, primary: engine, fallback: <"none" if saved.fallback
      was pointing at engine, else saved.fallback>}` via
      `setEnginePreferences`, updates local `saved`, toasts
      `enginePrimarySaved` on success / `saveFailed` on error. Wire it to a
      button on the open pane's detail head, styled as a clear primary/solid
      button (not the previous ghost variant) — visible only when
      `saved.primary !== open`; render a "Primary" badge in its place when it
      already is. (Named `activatePrimary`, not `usePrimary` — the latter
      trips `react-hooks/rules-of-hooks` since ESLint pattern-matches the
      `use`-prefix as a hook name.)
- [x] 5.4 Add an immediate fallback-change handler: on the Fallback
      `<select>`'s `onChange`, write `{...saved, fallback: <value>}`
      straight away (same pattern as 5.3, no staging), update `saved`, toast.
      Options list still excludes whichever engine is `saved.primary` right
      now (no more `proposedPrimary`).
- [x] 5.5 Revert each pane's own `onSave` to write only that engine's own
      fields (and, for DeepSeek, its credential) — never `primary`/
      `fallback`. Revert `dirty`/`canSave` in all four panes to depend only
      on that pane's own fields/credential input, dropping the
      `sectionDirty`/`willBePrimary` parameters added in the prior revision.
- [x] 5.6 Move the completeness gate onto `activatePrimary`/the primary button's
      `disabled` state, evaluated against `saved.omlx`/`saved.deepseek`/
      `codex`/`claude` + `auth.codex.connected`/`auth.claude.connected` (last
      *saved* state, not any pane's current unsaved draft) — implement as a
      small `engineReady(engine): boolean` on `EngineSection`, one case per
      engine.
- [x] 5.7 Confirm Codex/Claude's OAuth connect/disconnect stays an immediate
      action, independent of both the primary action and each pane's own
      save. Unaffected by this revision.
- [x] 5.8 Revert Reset to discard only the open pane's own draft (fields +
      unsaved credential input) — no more `onResetSection` call, since there
      is no section-level staged state left to discard.

## 6. Selection indicator (shared across sections)

- [x] 6.1 Change Engine's card checkmark and `aria-pressed` to key off the
      committed primary (`saved.primary === engine`), not the open/staged
      card — matching Radar/Knowledge Embedding's existing `active` pattern.
- [x] 6.2 Add real CSS for the "open, not committed" card state
      (`set-engineopen`, currently referenced with no matching rule) and
      apply it consistently to all three sections' cards.

## 7. Copy

- [x] 7.1 **Revised**: restore a distinct `enginePrimarySaved` string
      ("Engine selection applied" / 引擎选择已应用) for `activatePrimary`'s own
      toast, separate from `engineSaved` ("Engine settings saved") — the two
      are independent actions again, not one commit. Keep
      `engineUsePrimary`/`enginePrimaryBadge` (still accurate: the button
      really does immediately apply now, no rename needed). Fix
      `engineHint`/`engineUnselectedHint` (both locales), which currently
      read "mark it primary and save to apply it" — no longer true, applying
      primary needs no separate save. Fix the `save:` dictionary comment
      (`dashboard/lib/i18n/dictionaries.ts` ~line 31), which currently
      justifies "Save configuration" by saying every section commits its
      whole draft through it — no longer true for Engine, which has two
      independent actions. Re-sync `dashboard/README.md` +
      `dashboard/README.zh-CN.md`'s Engine section and the settings-commit
      table to describe two independent, immediately-committing actions
      (Use as primary / Fallback vs. Save configuration) instead of one
      fused commit; Radar/Knowledge Embedding's doc sections are unaffected.

## 8. Verification

**Reset**: the Engine section is changing again (tasks 5.1b–5.8), so its
verification needs redoing; the Radar/Knowledge Embedding and credential-lock
results from the first pass are unaffected but re-run for a clean overall
check.

- [x] 8.1 `uv run pytest -q` (no Python changes expected, but confirm nothing
      else broke). 638 passed, 68 skipped.
- [x] 8.2 Dashboard type-check / lint for the touched components. `tsc
      --noEmit` clean; `eslint .` clean on touched files (caught and fixed a
      real issue: naming the primary handler `usePrimary` tripped
      `react-hooks/rules-of-hooks` since ESLint pattern-matches the `use`
      prefix — renamed to `activatePrimary`). Dashboard unit tests: 128
      passed, 2 skipped (Windows-only, unrelated).
- [x] 8.3 Verify in Docker per `.claude/skills/docker-verify`: rebuilt,
      recreated, confirmed the running image ID matches the build, polled
      `/settings` to 200, swept all seven routes (`/` 307, rest 200).
      Confirmed on `/settings`'s real HTML: old copy
      ("Apply selection"/"应用选择") absent; "Save configuration" present;
      the "Primary" badge (not "Use as primary") renders for the initially-
      open pane, matching this stack's real saved primary (`claude_cli`, via
      `next-signal doctor`) — the same cross-check used in the first pass,
      now re-confirmed against the reverted code. Interactive click-through
      (clicking "Use as primary", confirming it commits immediately and
      Save configuration doesn't move the pointer) was **not** performed in
      a live browser — no browser-automation tool was available in this
      session, same limitation as the first pass. Confidence instead comes
      from: full-repo `tsc` (would catch prop/signature mismatches),
      `eslint` (caught the hooks-naming bug above), and a direct code read
      of `activatePrimary`/`changeFallback`/`engineReady` against every
      scenario in the revised spec.
- [x] 8.4 Confirm `openspec/changes/settings-single-commit-action/specs/`
      deltas match the shipped behavior before archiving, including the
      revised "switchable section" and "cannot become active while
      incomplete" requirements. Walked each: activation and configuration
      commit independently (5.3/5.5); activation is immediate with no draft
      (5.3/5.4); the gate reads `saved`/`codex`/`claude`/`auth`, never a
      pane's unsaved `value` (5.6); neither action's availability depends on
      the other's pending state (`PaneActions`' `dirty`/`canSave` no longer
      take any section-level input) — all satisfied.
