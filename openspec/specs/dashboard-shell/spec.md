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

The dashboard SHALL render a global app shell — top navigation bar (`Radar`, `Knowledge`, `Goals`, `Subscriptions`, `Design System` entries; `Goals` and `Subscriptions` MAY be placeholder links until their pages land), a brand block (`SignalMark` on the signal gradient tile + `next-signal` wordmark + a `localhost:host` env chip), a theme toggle, and a `sonner` `<Toaster />` root — that is shared by every page under `app/`.

The `Radar` and `Knowledge` nav entries SHALL use their brand marks at `variant="nav"`. The remaining entries have no brand mark and SHALL use lucide icons; a brand glyph in the nav signifies a product with its own identity, and SHALL NOT be introduced for sections that lack one.

This requirement governs the visible brand layer only. The `paca` name SHALL remain unchanged as the Python package, the CLI binary, the `PACA_*` environment prefix, and the subprocess launcher symbols.

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

### Requirement: Bilingual UI via a locale cookie

The dashboard SHALL support English and Chinese UI text via `dashboard/lib/i18n/` (dictionaries + a `getDictionary(locale)` lookup), an `I18nProvider` (`dashboard/components/i18n-provider.tsx`) exposing `useI18n() -> {locale, t}` to client components, and a `LanguageToggle` component (`dashboard/components/language-toggle.tsx`) that sets the locale. The active locale SHALL be persisted in a `paca_locale` cookie (`LOCALE_COOKIE`, 1-year `max-age`, `path=/`, `samesite=lax`) and applied on the server for the initial render.

`LanguageToggle` SHALL be a picker rather than a blind toggle: its trigger SHALL show the **current** locale, and its menu SHALL list every available locale with the active one marked. Locale names in the menu SHALL be self-labelled and never translated (`English`, `中文`) — a language menu has to be readable to someone who cannot read the language the UI is currently in. It SHALL be built on the Radix Select primitive, since it picks a value rather than firing a command.

#### Scenario: operator changes language

- **WHEN** the operator opens the language picker and chooses a locale different from the current one
- **THEN** the `paca_locale` cookie is set to that locale, the router refreshes, and subsequently rendered text uses the new locale's dictionary

#### Scenario: the picker shows current state, not a target

- **WHEN** the operator looks at the language control while the UI is in English
- **THEN** the trigger reads `EN` (the active locale) and the open menu marks `English` as selected — the control never labels itself with the locale it would switch *to*

#### Scenario: choosing the active locale is a no-op

- **WHEN** the operator opens the picker and selects the locale that is already active
- **THEN** no cookie write and no router refresh occur

#### Scenario: locale persists across reloads

- **WHEN** the operator reloads the dashboard after toggling language
- **THEN** the same locale (read from the `paca_locale` cookie) is used for the initial server render, with no flash of the other language

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

### Requirement: Shared `paca` subprocess launcher

Every dashboard server action that runs `uv run paca ...` SHALL go through `dashboard/lib/actions/spawn-paca.ts::spawnPacaDetached`. The helper SHALL spawn detached with `unref()`, pipe stdio to `~/.next-signal/dashboard-actions.log` (creating the directory if missing), and return a result whose success message is `"<verb> started"` (never `"completed"`).

#### Scenario: detached + logged

- **WHEN** any caller invokes `spawnPacaDetached(["run-workflow", "knowledge_ingest"])`
- **THEN** the action returns within the request lifecycle, the subprocess outlives the request, and a line tagged with the call's `logTag` (or default tag) is appended to `~/.next-signal/dashboard-actions.log`

#### Scenario: "started" semantics enforced

- **WHEN** any caller invokes the helper with `verb: "Re-index"`
- **THEN** the success message reads exactly `"Re-index started"` — never `"completed"` or `"finished"`

#### Scenario: synchronous spawn failure surfaces

- **WHEN** the helper cannot spawn (`uv` missing, EACCES, etc.)
- **THEN** it returns `{ ok: false, message: <error excerpt> }` and writes no further log lines for that call

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

The dashboard SHALL render `/knowledge` (`dashboard/app/knowledge/page.tsx`) with a left sidebar wiki tree (`PACA_WIKI_DIR`-driven, categorized, collapsible), a search input wired to `gbrain search`, a result-cards column with snippet highlights, and a preview pane showing the active document's frontmatter / tags / body. The page hero SHALL render `<KnowledgeEmblem />` (from `dashboard/components/brand/knowledge-mark.tsx`) alongside the page title and subtitle, matching the `/radar` hero treatment. The `Re-index` action SHALL still invoke `uv run paca run-workflow knowledge_ingest` from the repo root.

#### Scenario: search still hits gbrain

- **WHEN** the operator submits a query on `/knowledge`
- **THEN** the page executes `gbrain search <query> --limit <N>` server-side and renders the results into the result-cards column

#### Scenario: re-index still works

- **WHEN** the operator clicks `Re-index`
- **THEN** the same `paca run-workflow knowledge_ingest` subprocess runs, with the same cwd, and a `sonner` toast confirms it

#### Scenario: wiki tree reflects PACA_WIKI_DIR

- **WHEN** `/knowledge` loads
- **THEN** the sidebar tree lists categories and documents discovered by walking `PACA_WIKI_DIR`, and clicking a doc swaps the preview pane

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

`dashboard/README.md` SHALL document the `pnpm dev` (port 3000) + `uv run paca serve` (port 7777) two-process workflow and the `NEXT_PUBLIC_AGENT_OS_URL` env var (default `http://localhost:7777`). It SHALL also document the `paca dashboard` CLI wrapper (a thin `pnpm dev|build|start` exec, see core-cli spec) as an alternative entrypoint.

#### Scenario: README covers the two-process flow

- **WHEN** a new operator reads `dashboard/README.md`
- **THEN** they can start the dashboard and AgentOS together without referring to other docs, and they know which env var points the browser at AgentOS

#### Scenario: README documents the paca dashboard wrapper

- **WHEN** a new operator reads `dashboard/README.md`
- **THEN** they find `paca dashboard` documented as an alternative to running `pnpm dev` directly from `dashboard/`

