## Context

Two mechanisms currently share one control and one line of reasoning that no
longer holds.

`core-output-language` resolves each agent's language from a declared policy.
`global` reads `~/.next-signal/language.json`; `same_as_source` takes a per-call
override the workflow stage supplies from `detect_language()`. Today info-radar's
four agents use `global`, knowledge's four use `same_as_source`.

The dashboard writes that preference file from the nav locale picker's
`onValueChange` — the same handler that sets the `paca_locale` cookie. The
archived `output-language-policy` change justified this as "the UI-chrome locale
and the content-language preference are the same control, not two independent
settings." The claim is defensible for a single-user local tool right up until the
two genuinely diverge: reading an interface in one language and wanting generated
prose in another is an ordinary preference, and today it is unexpressible.

The knowledge half has the opposite problem. Frontmatter `title`/`summary` were
put on `same_as_source` to protect the archive. But frontmatter is not archived
source text — it is generated prose that appears in the dashboard's knowledge list
and review cards, the same reader-facing surfaces the content-language setting was
built to govern. The body is the archive; the frontmatter is the index entry.

Constraints carried in from prior measured work: the `{{OUTPUT_LANGUAGE}}` rule
wording is measured and must not be reworded casually; `tags` stay lowercase
English because `_normalize_tags` drops CJK tags outright; language resolution
happens at call time, never at import.

## Goals / Non-Goals

**Goals:**

- A settings surface in the nav that owns the pipeline's content-language
  preference, distinct from the UI-chrome picker beside it.
- The locale picker stops writing the preference file. The two settings become
  independently selectable and may disagree.
- Wiki frontmatter `title`/`summary` follow the content-language setting.
- The wiki body keeps its source language, unconditionally.

**Non-Goals:**

- Reconciling the two settings, warning when they disagree, or offering a "match
  my UI language" convenience. Divergence is the feature.
- Retroactively rewriting frontmatter in already-ingested wiki files.
- Adding further settings to the new panel. It ships with one control; it exists
  as the right home for that control, not as a settings-page project.
- Changing any measured prompt wording, the `global`/`same_as_source` resolution
  code, or the preference file's format.

## Decisions

### D1. Build the panel on `@radix-ui/react-popover`, adding the dependency

A settings panel anchored to a nav button is a popover: it is non-modal, it points
at its trigger, and dismissing it is a click away. `dashboard-shell`'s own rule is
that a primitive with a Radix equivalent is built on that equivalent, and the repo
already carries six Radix packages. The new `components/ui/popover.tsx` primitive
is registered on `/design` in this same change, per the project's standing rule for
new primitives.

*Alternatives considered.* Reusing `Dialog` (already present, zero new deps) — a
modal that dims the page and traps focus is disproportionate for a two-option radio
and reads as a heavier commitment than the setting warrants; it stays the fallback
if the dependency is unwanted. Reusing `Select` the way `LanguageToggle` does —
rejected because `Select` picks one value, while the panel is a *container* whose
whole reason to exist is being the place a second control could later go. A `Sheet`
side-drawer — considered and declined during scoping.

### D2. The current value flows server → client as a layout prop

`app/layout.tsx` is already an async server component that reads the locale before
render. It reads `content_language` in the same place and passes it to `<Nav>`, so
the panel paints its active state on first render.

*Alternative:* a `getContentLanguage` server action invoked when the popover opens.
Rejected — it puts a loading state inside a control whose entire job is to display
current state, in exchange for avoiding a file read that already happens once per
request in the same handler.

### D3. The dashboard's reader tolerates a bad preference file; the pipeline stays loud

`paca.core.language` raises `RuntimeError` on a corrupt or unrecognized
`language.json`, which is correct: the pipeline must not silently generate in the
wrong language. The dashboard's new getter deliberately does *not* mirror that. The
nav renders on every page, so raising there takes the whole dashboard down over a
state file — including the very panel the user would use to rewrite it. The getter
logs the error and falls back to `DEFAULT_LOCALE`, and the panel then shows a value
the user can correct with one click.

This is a considered exception to the project's "fail loud, never silently default"
rule, not an oversight: the loud path still exists on the side that matters
(pipeline runs raise, `paca doctor` reports), and the quiet path is the one whose
only alternative is a dead UI.

### D4. Frontmatter moves to `global`; body cleaners stay `same_as_source`

The dividing line is **prose written for the reader** versus **preserved source
text**, and it now cuts through the knowledge pipeline rather than around it:

| Agent | Output | Policy |
|---|---|---|
| `knowledge_frontmatter` | `title` / `summary` — index entries | `global` |
| `knowledge_github_summary` | `summary` — index entry | `global` |
| `knowledge_artifact_editor` | the article body | `same_as_source` |
| `knowledge_github_cleaner` | the README body | `same_as_source` |

Both frontmatter agents already carry `{{OUTPUT_LANGUAGE}}` in prompts whose
sentences read correctly under either policy ("Write `title` and `summary` in
{{OUTPUT_LANGUAGE}}, regardless of the language of the article body"). **No prompt
text changes**, so no measured wording is disturbed and no re-measurement is owed —
only the YAML policy and its rationale comments change.

A consequence worth naming rather than discovering: a wiki file can now be
bilingual, an English `title`/`summary` over a Chinese body. That is intended and
already how the radar reader behaves — a translated title above a source-language
article.

`detect_language()` and `KnowledgeArtifact.detected_language` survive unchanged,
now feeding two agents instead of four. `write_frontmatter` stops passing
`language=`; `_run_editor` keeps passing it.

### D5. No retroactive rewrite, and no rewrite path at all

Existing wiki files keep the frontmatter they were written with, permanently.
Re-index (`paca run-workflow knowledge_ingest` → `reindex_wiki`) walks the wiki,
digests each markdown file, and re-embeds the changed ones into GBrain; it never
re-runs `write_frontmatter`. The only code path that writes frontmatter is a fresh
`paca knowledge ingest <source>`, so changing the setting affects future ingests
only.

This is what defuses the hazard the predecessor mechanism carried. Under the old
global-preference behavior, the documented risk was that flipping the setting and
re-indexing would rewrite every `title` — and since `persist.py` derives the wiki
filename from `title` (`_artifact_slug`), that would rename files project-wide with
no migration. Moving frontmatter back onto `global` does **not** reintroduce that,
because the rewrite step it depended on is not something re-index does. A title
only changes when its source is deliberately ingested again, one document at a time.

*Alternative:* a one-shot migration re-running the frontmatter agent across the
wiki. Rejected — one LLM call per document plus a project-wide file rename, for a
cosmetic index-language sweep.

### D6. The container-start seed hook is unchanged

`instrumentation.ts` still creates the preference file from `DEFAULT_LOCALE` when
absent. It was never coupled to the locale picker; it only shares the file.

## Risks / Trade-offs

- **A mixed-language wiki during the transition.** Docs ingested before this change
  keep source-language frontmatter; new ones follow the setting. → Named in the
  module docs so it reads as expected state; a full re-index converges it whenever
  the user wants.

- **Two readers of one file with different failure modes** (D3). → The asymmetry is
  documented in `docs/modules/core.md`, and `paca doctor` stays the single check
  that reports the file loudly.

- **A new dependency for one panel.** → `@radix-ui/react-popover` is small, matches
  six existing Radix packages, and the primitive it backs is reusable and lands in
  the `/design` catalogue rather than staying a one-off.

- **Users may not connect the settings panel to radar/knowledge output.** The old
  coupling was at least discoverable by accident. → The panel labels the control by
  what it governs (generated content, not interface), which the locale picker never
  did.

- **`detect_language`'s title-first heuristic now serves only body cleaning.** Its
  input is unchanged and it was already the value the cleaners consumed, so
  behavior for them is byte-identical; only the number of consumers drops.

## Migration Plan

No database change, no state-file format change, no CLI change.

1. `npm install` in `dashboard/` picks up `@radix-ui/react-popover`; the dashboard
   image must be rebuilt (`docker compose build dashboard`) rather than hot-reloaded.
2. Restart the stack. Existing `language.json` files are read as-is.
3. Optionally re-index the wiki to converge frontmatter language.

Rollback is a plain revert: the preference file's format is untouched in both
directions, so no state migration is needed either way.

## Open Questions

- Should the settings panel also host the UI-locale picker, retiring the separate
  nav button? Deferred — keeping both controls visible was the scoping decision,
  and collapsing them later is a smaller change than splitting them was.
- Should `paca doctor` report the UI locale alongside the content language? Out of
  scope; the cookie is browser state the CLI has no view of.
