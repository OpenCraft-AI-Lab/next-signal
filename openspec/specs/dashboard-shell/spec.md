# dashboard-shell Specification

## Purpose
TBD - created by archiving change dashboard-foundation. Update Purpose after archive.
## Requirements

### Requirement: Next.js app scaffold

The `dashboard/` directory SHALL contain a Next.js 15 App Router project that runs via `pnpm dev` on port 3000 and builds via `pnpm build`.

#### Scenario: pnpm dev starts the dashboard

- **WHEN** the operator runs `pnpm install && pnpm dev` from `dashboard/`
- **THEN** the Next.js dev server starts on `http://localhost:3000`, the root route resolves without errors, and HMR is enabled

#### Scenario: pnpm build produces a deployable bundle

- **WHEN** the operator runs `pnpm build` from `dashboard/`
- **THEN** the build completes without TypeScript or ESLint errors and writes the `.next/` output directory

### Requirement: Dependency surface mirrors agent-ui

`dashboard/package.json` SHALL pin every runtime and dev dependency that appears in `agno-agi/agent-ui`'s `package.json` to the same minimum semver range, so individual `agent-ui` components can be copied into the dashboard later with no install drift. The dashboard MAY add packages on top (e.g. `geist` for fonts, `@radix-ui/react-collapsible` if not in agent-ui, `pg` for downstream radar reads) but MUST NOT downgrade or remove any agent-ui entry.

#### Scenario: dep list is a superset of agent-ui

- **WHEN** a reviewer diffs `dashboard/package.json` against the `agent-ui` reference
- **THEN** every entry under `agent-ui`'s `dependencies` and `devDependencies` is present in `dashboard/package.json` at the same or wider range, and the dashboard adds no incompatible major-version overrides

#### Scenario: ported component installs cleanly

- **WHEN** a developer copies a single source file from `agent-ui` into `dashboard/components/` and runs `pnpm install`
- **THEN** no new packages are installed for that component and no peer-dep warnings related to it appear

### Requirement: Geist Sans + Geist Mono via the `geist` package

The dashboard SHALL load Geist Sans and Geist Mono via Vercel's `geist/font/sans` and `geist/font/mono` (no Google Fonts request), and expose them as the project's default sans / mono fonts in Tailwind's theme.

#### Scenario: both fonts are available

- **WHEN** any page renders
- **THEN** the body inherits Geist Sans, elements with the `font-mono` Tailwind utility (or the design's `.mono` class) render in Geist Mono, and no font-related network request goes to `fonts.googleapis.com`

### Requirement: Theme provider uses the `data-theme` attribute

The dashboard SHALL wrap the app in `<ThemeProvider attribute="data-theme" defaultTheme="light" disableTransitionOnChange>` (from `next-themes`, via `dashboard/components/theme-provider.tsx`) so the design's `[data-theme="dark"]` / `[data-theme="light"]` CSS selectors work as authored, and SHALL configure Tailwind's `darkMode` to recognize the same selector. The default theme is `light`; the provider does NOT pass `enableSystem`, so the app does not follow the OS theme by default — the operator must explicitly toggle to dark.

#### Scenario: theme toggle flips data-theme

- **WHEN** the operator toggles the theme
- **THEN** `<html data-theme="dark">` or `data-theme="light"` updates, the design's CSS variables swap accordingly, and Tailwind dark utilities (`dark:`) resolve to the same state

#### Scenario: default theme is light, not OS-driven

- **WHEN** the operator loads the dashboard for the first time with no stored theme preference, regardless of OS theme setting
- **THEN** the dashboard renders with `data-theme="light"`

#### Scenario: SSR avoids hydration mismatch

- **WHEN** the page is rendered server-side with no `data-theme` preset
- **THEN** `next-themes` injects an inline script that sets the attribute before first paint, and no theme flash is observed

### Requirement: Global app shell

The dashboard SHALL render a global app shell — top navigation bar (`Radar`, `Knowledge`, `Goals`, `Subscriptions`, `Design System` entries; `Goals` and `Subscriptions` MAY be placeholder links until their pages land), a brand block (`SignalMark` on the signal gradient tile + `next-signal` wordmark), a theme toggle, a settings entry, and a `sonner` `<Toaster />` root — that is shared by every page under `app/`.

The `Radar` and `Knowledge` nav entries SHALL use their brand marks at `variant="nav"`. The remaining entries have no brand mark and SHALL use lucide icons; a brand glyph in the nav signifies a product with its own identity, and SHALL NOT be introduced for sections that lack one.

The settings entry SHALL sit in the nav's tools cluster rather than among the page links, and SHALL be a link to `/settings` that marks itself as the current page while that route is active. It is chrome that follows the operator between products rather than being one of them.

The shell SHALL NOT carry a host or environment chip. It was the shell's only client-resolved state, requiring a mount effect to read `window.location.host` on every page, and it reported to the operator of a loopback-bound dashboard the address they had just typed.

#### Scenario: every page renders inside the shell

- **WHEN** the operator visits any `app/<page>` route
- **THEN** the top nav, the brand block, the theme toggle, the settings entry, and the toast root are present in the rendered HTML

#### Scenario: the shell carries the next-signal wordmark

- **WHEN** the operator loads any page
- **THEN** the brand block reads `next-signal` beside the signal mark, and the document title is `next-signal · local dashboard`

#### Scenario: brand glyphs are scoped to branded sections

- **WHEN** a reviewer inspects the nav entries
- **THEN** `Radar` and `Knowledge` render brand marks while `Goals`, `Subscriptions`, and `Design System` render lucide icons

#### Scenario: theme toggle persists

- **WHEN** the operator clicks the theme toggle and reloads
- **THEN** the previously selected theme (light / dark / system) is restored without a flash of incorrect theme

#### Scenario: the settings entry navigates rather than opening a panel

- **WHEN** the operator activates the nav's settings control
- **THEN** the browser navigates to `/settings`, and the control renders as the active page while there

### Requirement: UI primitive library

The dashboard SHALL provide a self-authored set of UI primitives under `dashboard/components/ui/` covering at minimum `Button`, `Card`, `Badge`, `Dialog`, `Sheet`, `Tooltip`, `Collapsible`, `Segmented`, plus a `cn()` utility in `dashboard/lib/utils.ts`. Each primitive that has a Radix equivalent SHALL be built on the matching Radix primitive (e.g. `Dialog` uses `@radix-ui/react-dialog`, `Collapsible` uses `@radix-ui/react-collapsible`), styled to the design tokens in `dashboard/app/globals.css`.

#### Scenario: primitives are importable

- **WHEN** any page imports `Button` from `@/components/ui/button`
- **THEN** the component compiles, renders Radix-backed markup, and accepts CVA variants for `variant` and `size`

#### Scenario: Collapsible uses Radix and matches the design's expand animation

- **WHEN** a page uses `<Collapsible>` from `@/components/ui/collapsible`
- **THEN** the underlying element is a `@radix-ui/react-collapsible` `Root`, and the open/close animation matches the design's `.collapsible / .inner` height transition

#### Scenario: cn() merges Tailwind classes

- **WHEN** code calls `cn("p-4", condition && "bg-red-500", "p-2")`
- **THEN** the returned string has duplicate padding utilities deduped (latter wins) per `tailwind-merge`

### Requirement: Design token system

The dashboard SHALL define the CSS-variable token set in `dashboard/app/globals.css`, wired through Tailwind's `theme.extend` so the same tokens are accessible as both raw CSS variables (e.g. `var(--accent)`) and Tailwind utilities (e.g. `bg-accent`).

The token set SHALL include a brand group: `--brand-spark-radar` and `--brand-spark-kb` (the single secondary colour each module mark is allowed to spend), and `--brand-grad-signal`, `--brand-grad-radar`, `--brand-grad-kb` (badge tile gradients). Brand tokens SHALL be defined independently of the semantic verdict colours and SHALL NOT alias `--purple`, `--green`, or the score ramp, so brand hue and status hue remain separately changeable.

The token set SHALL also include a knowledge retention ramp group defining a single-hue sequential ramp with per-theme endpoints, plus a neutral for docs that have left the ramp. Like the brand group, it SHALL be defined independently of the semantic verdict colours and SHALL NOT alias `--purple`, `--green`, or the score ramp: the score ramp encodes the radar's verdict, and reusing it would read an advanced review stage as a high score.

#### Scenario: light and dark token sets are both defined

- **WHEN** `dashboard/app/globals.css` is loaded
- **THEN** `:root[data-theme="light"]` and `:root[data-theme="dark"]` blocks each define the full token set (surfaces, text, border, accent, semantic, score-*, shadow-*, line, hover, active, brand, retention ramp)

#### Scenario: brand colour is independent of status colour

- **WHEN** a reviewer inspects the brand token declarations
- **THEN** each resolves to its own literal value rather than referencing a verdict or score variable

#### Scenario: retention ramp is independent of the score ramp

- **WHEN** a reviewer inspects the retention ramp declarations
- **THEN** each resolves to its own literal value rather than referencing `--score-s`, `--score-l`, or a semantic verdict variable

#### Scenario: the ramp resolves per theme without a client component

- **WHEN** a server-rendered element colours itself from the retention ramp and the reader switches theme
- **THEN** the element re-resolves through the cascade, with no client-side recomputation and no flash of the previous theme's colour

### Requirement: Score color ramp utilities

The dashboard SHALL expose `scoreHue(s: number): number` and `scoreLOff(s: number): number` from `dashboard/lib/score.ts`, implementing a continuous orange→yellow→green ramp, accepting values in the `0..100` range.

#### Scenario: ramp returns expected hues

- **WHEN** code calls `scoreHue(0)`, `scoreHue(50)`, `scoreHue(100)`
- **THEN** the returned values are approximately `28`, `55`, `143` respectively

#### Scenario: upper-half darkening kicks in

- **WHEN** code calls `scoreLOff(60)` vs `scoreLOff(40)`
- **THEN** the value for `60` is strictly positive (upper half darkens) and the value for `40` is `0`

### Requirement: Brand assets

The dashboard SHALL ship three brand mark families, each as one module under `dashboard/components/brand/` exporting a flat **mark** and an animated **emblem**:

| Family | Module | Exports |
| --- | --- | --- |
| next-signal (parent) | `signal-mark.tsx` | `SignalMark`, `SignalEmblem` |
| info-radar | `radar-mark.tsx` | `RadarMark`, `RadarEmblem` |
| knowledge-base | `knowledge-mark.tsx` | `KnowledgeMark`, `KnowledgeEmblem` |

Every mark SHALL be built from the same atom — a node — plus exactly one connective form per family (chevron, wedge, link) on a 24-unit grid with round caps.

Marks SHALL accept an explicit `variant` of `"icon"` (default) or `"nav"`; they SHALL NOT select a detail tier by inspecting `size`. The tier contract is:

- **Emblem** (64–192px, animated, transparent, no background): full detail.
- **Icon** (24–48px): reduced detail, suitable for a flat glyph or a gradient badge tile.
- **Nav** (15–20px): minimum detail that preserves the mark's signature.

For `RadarMark` / `RadarEmblem` specifically, the emblem SHALL render three rings, crosshairs, twelve bearing ticks, an animated sweep and three blips; the icon tier SHALL render two rings, crosshairs, a static wedge and one blip; the nav tier SHALL render one ring, the wedge and the core. The sweep wedge SHALL be present at every tier, since it is the element that distinguishes a radar from a target reticle.

`SignalMark` SHALL render both chevrons at every tier; the `nav` variant SHALL re-space them rather than scaling the icon geometry, and SHALL NOT reduce to a single chevron.

Flat marks SHALL take their colour from `currentColor` and the brand tokens with no baked hex values, so one asset serves both themes. Emblems SHALL remain server components — static SVG animated by CSS, with no `"use client"`.

The retired alpaca marks (`Alpaca`, `RadarAlpaca`) and their exploratory variants (`AlpacaOutline`, `AlpacaFace`, `AlpacaBadge`, `RadarAlpacaScope`, `RadarAlpacaArc`) SHALL NOT exist in the production source.

#### Scenario: marks are usable at every tier

- **WHEN** the nav imports `SignalMark` and `RadarMark`, and `/radar` imports `RadarEmblem`
- **THEN** each renders at its intended size (nav: 20px `SignalMark` in the brand tile, 15px nav-variant glyphs; `/radar` hero: 72px `RadarEmblem` with the sweep running) and inherits the current accent via CSS variables

#### Scenario: detail tier is explicit, not inferred

- **WHEN** a caller renders `<RadarMark size={16} />` without a `variant`
- **THEN** the component renders the `icon` tier at 16px rather than silently switching geometry, because the tier is chosen by prop and never by size threshold

#### Scenario: the signature survives the smallest tier

- **WHEN** a reviewer inspects `SignalMark` at `variant="nav"` and `RadarMark` at `variant="nav"`
- **THEN** the signal mark still shows two chevrons, and the radar still shows its sweep wedge

#### Scenario: alpaca marks are absent

- **WHEN** a reviewer searches the dashboard source for `Alpaca`, `RadarAlpaca`, or their exploratory variants
- **THEN** none of these symbols exist outside `node_modules`

#### Scenario: emblems animate in phase and rest gracefully

- **WHEN** the `RadarEmblem` sweep passes a blip's bearing
- **THEN** that blip lights at that moment, its delay derived as `(bearing - 45) / 90` seconds against the 4s revolution rather than set by hand

- **WHEN** the operator has `prefers-reduced-motion: reduce` set
- **THEN** every emblem renders a composed still — the radar beam parked just past its first blip — rather than a frozen frame at t=0

### Requirement: Design system page

The dashboard SHALL render `/design` as a living style guide, with four tabs (`Tokens`, `Components`, `States`, `Brand`). The `Brand` tab SHALL show all three brand families, each at its emblem, icon, and nav tier. The `Tokens` tab SHALL include the brand token group and the knowledge retention ramp group. `/design` is the only regression net for the marks and for these token groups, so a newly added mark, tier, brand token, or retention ramp token SHALL be added to this page in the same change that introduces it.

#### Scenario: tabs render their reference content

- **WHEN** the operator opens `/design` and switches between the four tabs
- **THEN** each tab shows its corresponding reference (token swatches including the brand group and the retention ramp, primitive usage, interactive states, and all three brand families across all three tiers)

#### Scenario: the retention ramp is shown across its range

- **WHEN** the operator opens the `Tokens` tab
- **THEN** the retention ramp is shown as swatches spanning its endpoints, together with the off-ramp neutral, in the active theme

### Requirement: Search snippets sanitized at the dashboard sink

The dashboard SHALL render `gbrain` search snippets through a component that treats only `<em>...</em>` pairs as real DOM elements and renders every other character as escaped text. `dangerouslySetInnerHTML` SHALL NOT appear anywhere in the knowledge search / preview path.

#### Scenario: em pairs render as elements

- **WHEN** a gbrain snippet contains `here is an <em>orchestration</em> example`
- **THEN** the rendered DOM contains a real `<em>orchestration</em>` element surrounded by text nodes

#### Scenario: non-em HTML is inert

- **WHEN** a gbrain snippet contains `<script>alert(1)</script>` (e.g. lifted from a wiki doc's raw HTML)
- **THEN** the rendered DOM contains the literal characters `<script>alert(1)</script>` as text — no `<script>` element is created

### Requirement: Knowledge doc access scope

`getWikiDoc(id)` SHALL only return content for ids that (a) end with `.md`, (b) are relative paths with no `..` segments, and (c) resolve inside `WIKI_ROOT`. Any other id SHALL yield `null` so the preview pane shows the empty state.

#### Scenario: non-markdown id is rejected

- **WHEN** `?doc=.env` or `?doc=secret.txt` is passed
- **THEN** `getWikiDoc` returns `null` and the preview pane shows the empty state

#### Scenario: traversal attempt is rejected

- **WHEN** `?doc=../../etc/passwd` is passed
- **THEN** `getWikiDoc` returns `null` without reading any file

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

### Requirement: Visual design system is documented for contributors

`dashboard/README.md` SHALL document the dashboard's visual design system and how a design mock is consumed: the in-app `/design` showcase route (tokens, components, states, brand) is the design-system source of truth; incoming Claude Design mocks are transient and external and are never committed to this repo; and new pages SHALL be built by reusing the existing tokens (`dashboard/app/globals.css`) and primitives (`dashboard/components/ui/`) rather than inventing new styling. Once a page ships, the shipped page plus the `/design` showcase are the durable reference — specs and docs SHALL reference those, never a mock file.

#### Scenario: README documents the design system and mock practice

- **WHEN** a contributor reads `dashboard/README.md`
- **THEN** they find a "Visual design system" section that names `/design` as the source of truth, states that design mocks are transient and external, and directs new work to reuse existing tokens and `components/ui/` primitives

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

`LanguageToggle` SHALL govern **UI chrome only**. It SHALL NOT read or write the pipeline's content-language preference file (`~/.next-signal/language.json`); that preference is owned by the settings page specified below. The two settings are independent and MAY hold different values — an operator reading the interface in one language while generating content in another is a supported state, not a drift bug, and the dashboard SHALL NOT reconcile them, warn about the difference, or offer to sync them.

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

### Requirement: The settings page owns the content-language preference

The dashboard SHALL own its settings on a page at `/settings`, reached from the nav's settings entry, carrying the pipeline's **content language** setting among the others specified below. A page rather than a panel anchored to the nav: the settings outgrew what an anchored panel can hold, and a page is the only surface on which they can be laid out and scrolled. The page SHALL introduce no new UI primitive, and the `Popover` primitive and `/design` catalogue entry that the anchored panel required SHALL be retired with it, since nothing else uses them.

The page SHALL be organised into labelled sections, one per setting it owns, separated so that no control is mistaken for a qualifier of another. Sections SHALL be independent: changing one SHALL NOT read, write, or invalidate another's state.

The control SHALL be labelled by what it governs — the language of generated content (radar analyses, wiki frontmatter) — and SHALL NOT be labelled merely "language", so it is distinguishable from the UI-locale picker in the nav. Language names inside it SHALL be self-labelled and never translated, for the same reason the locale picker's are.

Selecting a value SHALL write it as `content_language` into `~/.next-signal/language.json` via the `setContentLanguage` server action, the file `core-output-language`'s `global` policy reads. The write SHALL be atomic (temp file + rename) so a concurrent pipeline read never observes a torn file.

Every value the page displays SHALL be resolved on the server by the page itself, so each control paints its active state on first render with no loading state. The app shell SHALL NOT read these settings: only `/settings` needs them, and a header that reads several state files and a database row to render is a cost every other page would pay. The reader SHALL tolerate a missing or unreadable preference file by falling back to `DEFAULT_LOCALE` and logging, rather than raising, because the page that would repair the file is the page that raising would take down. This is a deliberate asymmetry with `next_signal.core.language`, which SHALL continue to raise on the pipeline side.

Once per dashboard container start, a startup hook SHALL create the preference file — seeded with `DEFAULT_LOCALE` — if it does not already exist, so a freshly started dashboard with no prior preference still leaves the pipeline in a defined state. It SHALL NOT overwrite an existing file, and SHALL NOT re-run per request.

#### Scenario: operator changes the content language

- **WHEN** the operator opens `/settings` and selects a content language different from the current one
- **THEN** `~/.next-signal/language.json`'s `content_language` is written to that value, and the next agent build resolving the `global` policy observes it

#### Scenario: the page shows current state on first paint

- **WHEN** the operator opens `/settings`
- **THEN** the currently configured content language is already marked as selected, with no spinner or flash of a default value

#### Scenario: unreadable preference file does not break the settings page

- **WHEN** `~/.next-signal/language.json` is missing, corrupt, or holds an unrecognized value, and `/settings` is rendered
- **THEN** the section renders normally showing `DEFAULT_LOCALE`, the error is logged, and no page render fails

#### Scenario: the setting is independent of the UI locale

- **WHEN** the operator changes the content language on `/settings`
- **THEN** the `ns_locale` cookie is unchanged and the UI chrome stays in its current language

#### Scenario: first launch with no preference file

- **WHEN** the dashboard container starts and `~/.next-signal/language.json` does not exist
- **THEN** the startup hook creates it, seeded with `DEFAULT_LOCALE`, before any request is served

#### Scenario: preference file untouched by ordinary page loads

- **WHEN** the operator navigates between pages other than `/settings`
- **THEN** no read or write of `~/.next-signal/language.json` occurs

#### Scenario: settings sections do not interfere

- **WHEN** the operator changes a value in one section of the page
- **THEN** the other sections' stored state is unread and unwritten, and their displayed values are unchanged

### Requirement: Settings persist on commit, and every commit is acknowledged

Each control on the settings page SHALL persist when the user *commits* it, and what counts as a commit SHALL be determined by the control:

- A **discrete choice** (a segmented control such as the content language, the schedule's enable, or its catch-up policy) SHALL commit on click. One interaction already expresses one complete, valid intent, so it SHALL NOT require a separate confirm step.
- A **typed value** (the schedule time) SHALL commit on blur or Enter, and SHALL NOT persist per keystroke. A native time input emits a complete value for every segment edited, so persisting each change would publish values the operator never chose — and the scheduler reads the file within one poll, so such a value can become the live schedule.
- An **interdependent group** whose partial states are invalid (the Codex and Claude settings) SHALL commit through an explicit Save control.

Regardless of path, a successful write SHALL be acknowledged to the operator, and a failed one SHALL roll the control back to the last value known to be stored and report the failure. These controls update optimistically, so they move whether or not the write landed; without an acknowledgement the operator cannot distinguish a saved setting from an unsaved one, and a section with no Save control reads as not wired up at all.

A commit that would not change the stored value SHALL be a no-op: no write, no acknowledgement.

Every state file the page owns SHALL be published through one shared atomic writer rather than a copy per setting, and its temp path SHALL be unique per write. Two commits in flight at once — which optimistic controls produce whenever one commits while another is still writing — otherwise collide on a single temp path: the first rename consumes it and the second fails for want of it. The file left behind is intact; what breaks is the second caller, which reports a failed save and rolls its control back to a value that is no longer what is on disk.

#### Scenario: a discrete choice saves on click

- **WHEN** the operator clicks a segmented option different from the current one
- **THEN** the new value is written and the save is acknowledged, with no further confirmation step

#### Scenario: typing a time does not publish intermediate values

- **WHEN** the operator edits the schedule time from 13:55 to 09:30, which the control reports as 09:55 and then 09:30
- **THEN** nothing is written while the field is being edited, and exactly one write of 09:30 occurs when it commits

#### Scenario: a failed write rolls the control back

- **WHEN** a write fails
- **THEN** the control returns to the last value known to be stored and the failure is reported

#### Scenario: re-selecting the current value writes nothing

- **WHEN** the operator commits a value identical to the stored one
- **THEN** no write occurs and no acknowledgement is shown

#### Scenario: concurrent commits do not report a failure neither had

- **WHEN** two commits to the same state file are in flight at once
- **THEN** both report success and one of the two payloads is left in place in full, rather than one being told its save failed because the other got there first

### Requirement: The settings page owns the unattended run schedule

The settings page SHALL carry a section, visually separated from the sections around it, that owns the wall-clock schedule specified by `core-schedule`. It SHALL expose three controls — whether the schedule is enabled, the daily times, and whether a missed run is caught up — SHALL state the zone those times fire in without offering to change it, and SHALL read back the state of the most recent run.

The times SHALL be editable as a list, added and removed one row at a time, since the schedule is a set of daily times rather than a single one. A newly added row SHALL be a draft: it SHALL NOT be written until it holds a time and commits. The last remaining time SHALL NOT be removable — an enabled schedule with nothing to fire is not a reachable state, and the enable control is how the schedule is stopped. Adding a row SHALL choose the first hour not already taken, and SHALL do nothing once every hour is; a search for a free value SHALL be bounded by the values it can return.

Writes SHALL go to `~/.next-signal/schedule.json` through a server action, atomically, mirroring how the content-language setting writes its own file. The section SHALL NOT write on render.

The time control SHALL express a wall-clock time of day and nothing else, so that every value the file can hold is a value the page can display.

The timezone SHALL be displayed, not chosen: the section SHALL name the zone `core-schedule` resolves from `INFO_RADAR_TIMEZONE` and say where it is set, and SHALL NOT offer a control that records a zone of its own. The same value fixes radar day grouping and review due dates, so a schedule carrying its own zone would fire at 08:00 in one zone while its results were filed under a day boundary drawn in another. A stored zone that steers nothing is worse than none: its only observable effect is the warning that it has no effect.

The section SHALL display the next time a slot comes round, and SHALL compute it in the zone the scheduler resolves rather than the browser's. A next-run stated in a zone that decides nothing is confidently wrong, and it is the one value on this page an operator would act on without checking.

The times and catch-up controls SHALL be hidden while the schedule is disabled, since neither has meaning then.

The section SHALL state, in its hint text, that catch-up applies only to runs that were genuinely missed — including one missed while the machine was asleep — and that changing the schedule never triggers a run for a time that has just passed. This distinction is not discoverable from the controls themselves.

The run read-back SHALL come from the `schedule_state` row via the dashboard's existing Postgres pool, rendered with the existing relative-time helper, and SHALL distinguish four states: never run, in progress, succeeded, and failed. When the last run failed, the recorded error SHALL be reachable from the section rather than only from container logs.

While a run is in progress the section SHALL say so and SHALL show how long it has been running. A run of this chain can last far longer than an operator expects it to, and a section that shows only the previous run's outcome for that whole window reads as though nothing is happening — or, worse, as though the run that later appears was triggered late. Any status that is neither in progress nor success SHALL read as a failure, so a run nobody finished is never displayed as one that did.

The section SHALL reuse existing UI primitives rather than introducing new ones, so it inherits the page's visual language and incurs no `/design` catalogue addition.

Reads SHALL be forgiving in the same way, and for the same reason, as the content-language reader: a missing, corrupt, or invalid `schedule.json` SHALL render the section as disabled and log, never raise, so the page that would fix the file still renders. The pipeline-side reader SHALL continue to raise.

#### Scenario: operator schedules a daily run

- **WHEN** the operator enables the schedule and sets the time to 08:00
- **THEN** `~/.next-signal/schedule.json` is written atomically with `enabled: true` and `at: ["08:00"]`, and the running scheduler observes it on its next poll

#### Scenario: disabled schedule hides its details

- **WHEN** the schedule is disabled
- **THEN** the times, timezone line, and catch-up control are not rendered, and only the enable control and the section's hint remain

#### Scenario: the zone is stated rather than offered

- **WHEN** the operator opens an enabled schedule
- **THEN** the section shows the zone `core-schedule` resolves as read-only text, names the environment variable that sets it, offers no way to record a different one, and states the next run in that same zone

#### Scenario: adding a time terminates when every hour is taken

- **WHEN** the operator adds times until all twenty-four hours are occupied and adds once more
- **THEN** nothing is added and the page remains responsive

#### Scenario: last run is reported

- **WHEN** the most recent scheduled run failed
- **THEN** the section reports the failure and its time, and the recorded error text is reachable from the section

#### Scenario: a run in progress is reported as running

- **WHEN** the operator opens `/settings` while the chain has been executing for twenty minutes
- **THEN** the section reports that a run is in progress and how long it has been running, rather than reporting the previous run's outcome

#### Scenario: an interrupted run does not read as a success

- **WHEN** the most recent run was interrupted by the container being killed
- **THEN** the section reports it as a failure rather than as a completed run, with the recorded error explaining that the process exited mid-run

#### Scenario: never-run schedule reads as such

- **WHEN** a schedule is enabled but has not yet reached its first slot
- **THEN** the section reports that no run has happened yet, rather than showing an empty or zeroed timestamp

#### Scenario: unreadable schedule file does not break the settings page

- **WHEN** `~/.next-signal/schedule.json` is corrupt or holds an invalid time, and `/settings` is rendered
- **THEN** the section renders as disabled, the error is logged, and no page render fails

#### Scenario: rendering the page does not write the schedule

- **WHEN** the operator opens `/settings` without changing anything
- **THEN** no write to `~/.next-signal/schedule.json` occurs

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
