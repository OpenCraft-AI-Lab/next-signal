## RENAMED Requirements

- FROM: `### Requirement: Shared `paca` subprocess launcher`
- TO: `### Requirement: Shared `next-signal` subprocess launcher`

## MODIFIED Requirements

### Requirement: Global app shell

The dashboard SHALL render a global app shell — top navigation bar (`Radar`, `Knowledge`, `Goals`, `Subscriptions`, `Design System` entries; `Goals` and `Subscriptions` MAY be placeholder links until their pages land), a brand block (`SignalMark` on the signal gradient tile + `next-signal` wordmark + a `localhost:host` env chip), a theme toggle, and a `sonner` `<Toaster />` root — that is shared by every page under `app/`.

The `Radar` and `Knowledge` nav entries SHALL use their brand marks at `variant="nav"`. The remaining entries have no brand mark and SHALL use lucide icons; a brand glyph in the nav signifies a product with its own identity, and SHALL NOT be introduced for sections that lack one.

#### Scenario: every page renders inside the shell

- **WHEN** the operator visits any `app/<page>` route
- **THEN** the top nav, the brand block, the theme toggle, and the toast root are present in the rendered HTML

#### Scenario: the shell carries the next-signal wordmark

- **WHEN** the operator loads any page
- **THEN** the brand block reads `next-signal` beside the signal mark, and the document title is `next-signal · local dashboard`

#### Scenario: brand glyphs are scoped to branded sections

- **WHEN** a reviewer inspects the nav entries
- **THEN** `Radar` and `Knowledge` render brand marks while `Goals`, `Subscriptions`, and `Design System` render lucide icons

#### Scenario: theme toggle persists

- **WHEN** the operator clicks the theme toggle and reloads
- **THEN** the previously selected theme (light / dark / system) is restored without a flash of incorrect theme

### Requirement: Shared `next-signal` subprocess launcher

Every dashboard server action that runs `uv run next-signal ...` SHALL go through `dashboard/lib/actions/spawn-cli.ts::spawnCliDetached`. The helper SHALL spawn detached with `unref()`, pipe stdio to `~/.next-signal/dashboard-actions.log` (creating the directory if missing), and return a result whose success message is `"<verb> started"` (never `"completed"`).

#### Scenario: detached + logged

- **WHEN** any caller invokes `spawnCliDetached(["run-workflow", "knowledge_ingest"])`
- **THEN** the action returns within the request lifecycle, the subprocess outlives the request, and a line tagged with the call's `logTag` (or default tag) is appended to `~/.next-signal/dashboard-actions.log`

#### Scenario: "started" semantics enforced

- **WHEN** any caller invokes the helper with `verb: "Re-index"`
- **THEN** the success message reads exactly `"Re-index started"` — never `"completed"` or `"finished"`

#### Scenario: synchronous spawn failure surfaces

- **WHEN** the helper cannot spawn (`uv` missing, EACCES, etc.)
- **THEN** it returns `{ ok: false, message: <error excerpt> }` and writes no further log lines for that call

### Requirement: Knowledge page (redesigned)

The dashboard SHALL render `/knowledge` (`dashboard/app/knowledge/page.tsx`) with a left sidebar wiki tree (`WIKI_DIR`-driven, categorized, collapsible), a search input wired to `gbrain search`, a result-cards column with snippet highlights, and a preview pane showing the active document's frontmatter / tags / body. The page hero SHALL render `<KnowledgeEmblem />` (from `dashboard/components/brand/knowledge-mark.tsx`) alongside the page title and subtitle, matching the `/radar` hero treatment. The `Re-index` action SHALL still invoke `uv run next-signal run-workflow knowledge_ingest` from the repo root.

#### Scenario: search still hits gbrain

- **WHEN** the operator submits a query on `/knowledge`
- **THEN** the page executes `gbrain search <query> --limit <N>` server-side and renders the results into the result-cards column

#### Scenario: re-index still works

- **WHEN** the operator clicks `Re-index`
- **THEN** the same `next-signal run-workflow knowledge_ingest` subprocess runs, with the same cwd, and a `sonner` toast confirms it

#### Scenario: wiki tree reflects WIKI_DIR

- **WHEN** `/knowledge` loads
- **THEN** the sidebar tree lists categories and documents discovered by walking `WIKI_DIR`, and clicking a doc swaps the preview pane

#### Scenario: operator creates a wiki folder

- **WHEN** the operator uses the new-folder dialog (`dashboard/components/knowledge/new-folder-dialog.tsx`) to create a folder path with a scope/freshness tier
- **THEN** `createWikiFolder` validates the path (lowercase segments, no traversal), registers the taxonomy category, creates the directory, and refreshes `/knowledge`

#### Scenario: operator deletes a wiki doc or folder

- **WHEN** the operator confirms deletion via the delete-confirm dialog (`dashboard/components/knowledge/delete-confirm-dialog.tsx`) for a doc or folder
- **THEN** `deleteWikiDoc` (removing the whole per-article directory for the `<slug>/<slug>.md` layout) or `deleteWikiFolder` (recursive, refuses the wiki root, prunes taxonomy categories) removes it from the wiki tree only — the GBrain index and raw archive are left for the next re-index — and `/knowledge` refreshes

### Requirement: Dev workflow documentation

`dashboard/README.md` SHALL document the `pnpm dev` (port 3000) + `uv run next-signal serve` (port 7777) two-process workflow and the `NEXT_PUBLIC_AGENT_OS_URL` env var (default `http://localhost:7777`). It SHALL also document the `next-signal dashboard` CLI wrapper (a thin `pnpm dev|build|start` exec, see core-cli spec) as an alternative entrypoint.

#### Scenario: README covers the two-process flow

- **WHEN** a new operator reads `dashboard/README.md`
- **THEN** they can start the dashboard and AgentOS together without referring to other docs, and they know which env var points the browser at AgentOS

#### Scenario: README documents the next-signal dashboard wrapper

- **WHEN** a new operator reads `dashboard/README.md`
- **THEN** they find `next-signal dashboard` documented as an alternative to running `pnpm dev` directly from `dashboard/`

### Requirement: UI locale via a locale cookie

The dashboard SHALL support English and Chinese UI text via `dashboard/lib/i18n/` (dictionaries + a `getDictionary(locale)` lookup), an `I18nProvider` (`dashboard/components/i18n-provider.tsx`) exposing `useI18n() -> {locale, t}` to client components, and a `LanguageToggle` component (`dashboard/components/language-toggle.tsx`) that sets the locale. The active locale SHALL be persisted in a `ns_locale` cookie (`LOCALE_COOKIE`, 1-year `max-age`, `path=/`, `samesite=lax`) and applied on the server for the initial render.

`LanguageToggle` SHALL be a picker rather than a blind toggle: its trigger SHALL show the **current** locale, and its menu SHALL list every available locale with the active one marked. Locale names in the menu SHALL be self-labelled and never translated (`English`, `中文`) — a language menu has to be readable to someone who cannot read the language the UI is currently in. It SHALL be built on the Radix Select primitive, since it picks a value rather than firing a command.

`LanguageToggle` SHALL govern **UI chrome only**. It SHALL NOT read or write the pipeline's content-language preference file (`~/.next-signal/language.json`); that preference is owned by the settings panel specified below. The two settings are independent and MAY hold different values — an operator reading the interface in one language while generating content in another is a supported state, not a drift bug, and the dashboard SHALL NOT reconcile them, warn about the difference, or offer to sync them.

#### Scenario: operator changes language

- **WHEN** the operator opens the language picker and chooses a locale different from the current one
- **THEN** the `ns_locale` cookie is set to that locale, the router refreshes, and subsequently rendered text uses the new locale's dictionary

#### Scenario: changing the UI locale leaves the content language alone

- **WHEN** the operator opens the language picker and chooses a locale different from the current one
- **THEN** no write to `~/.next-signal/language.json` occurs, and the pipeline's content language is unchanged

#### Scenario: the two settings may disagree

- **WHEN** the UI locale is `zh` and the content-language setting is `en`
- **THEN** the dashboard renders its chrome in Chinese and continues to resolve the `global` policy to English, with no warning, badge, or reconciliation prompt

#### Scenario: the picker shows current state, not a target

- **WHEN** the operator looks at the language control while the UI is in English
- **THEN** the trigger reads `EN` (the active locale) and the open menu marks `English` as selected — the control never labels itself with the locale it would switch *to*

#### Scenario: choosing the active locale is a no-op

- **WHEN** the operator opens the picker and selects the locale that is already active
- **THEN** no cookie write and no router refresh occur

#### Scenario: locale persists across reloads

- **WHEN** the operator reloads the dashboard after toggling language
- **THEN** the same locale (read from the `ns_locale` cookie) is used for the initial server render, with no flash of the other language

### Requirement: A nav settings panel owns the content-language preference

The dashboard SHALL provide a settings control in the nav tools cluster: a gear-icon trigger that opens a panel containing the pipeline's **content language** setting. The panel SHALL be built on a `Popover` primitive at `dashboard/components/ui/popover.tsx`, backed by `@radix-ui/react-popover` per the dashboard's rule that a primitive with a Radix equivalent uses it, and SHALL be added to the `/design` catalogue in the same change that introduces it.

The control SHALL be labelled by what it governs — the language of generated content (radar analyses, wiki frontmatter) — and SHALL NOT be labelled merely "language", so it is distinguishable from the adjacent UI-locale picker. Language names inside it SHALL be self-labelled and never translated, for the same reason the locale picker's are.

Selecting a value SHALL write it as `content_language` into `~/.next-signal/language.json` via the `setContentLanguage` server action, the file `core-output-language`'s `global` policy reads. The write SHALL be atomic (temp file + rename) so a concurrent pipeline read never observes a torn file.

The panel's current value SHALL be resolved on the server and passed into the nav for the initial render, so the panel shows its active state on first paint with no loading state. The reader SHALL tolerate a missing or unreadable preference file by falling back to `DEFAULT_LOCALE` and logging, rather than raising: the nav renders on every page, so raising would take down the whole dashboard — including the panel the operator would use to correct the value. This is a deliberate asymmetry with `next_signal.core.language`, which SHALL continue to raise on the pipeline side.

Once per dashboard container start, a startup hook SHALL create the preference file — seeded with `DEFAULT_LOCALE` — if it does not already exist, so a freshly started dashboard with no prior preference still leaves the pipeline in a defined state. It SHALL NOT overwrite an existing file, and SHALL NOT re-run per request.

#### Scenario: operator changes the content language

- **WHEN** the operator opens the settings panel and selects a content language different from the current one
- **THEN** `~/.next-signal/language.json`'s `content_language` is written to that value, and the next agent build resolving the `global` policy observes it

#### Scenario: panel shows current state on first paint

- **WHEN** the operator opens the settings panel
- **THEN** the currently configured content language is already marked as selected, with no spinner or flash of a default value

#### Scenario: unreadable preference file does not break the nav

- **WHEN** `~/.next-signal/language.json` is missing, corrupt, or holds an unrecognized value, and any dashboard page is rendered
- **THEN** the nav and settings panel render normally showing `DEFAULT_LOCALE`, the error is logged, and no page render fails

#### Scenario: the setting is independent of the UI locale

- **WHEN** the operator changes the content language in the settings panel
- **THEN** the `ns_locale` cookie is unchanged and the UI chrome stays in its current language

#### Scenario: first launch with no preference file

- **WHEN** the dashboard container starts and `~/.next-signal/language.json` does not exist
- **THEN** the startup hook creates it, seeded with `DEFAULT_LOCALE`, before any request is served

#### Scenario: preference file untouched by ordinary page loads

- **WHEN** the operator navigates between pages without opening the settings panel
- **THEN** no write to `~/.next-signal/language.json` occurs
