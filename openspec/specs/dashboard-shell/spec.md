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

The dashboard SHALL render a global app shell — top navigation bar (`Radar`, `Knowledge`, `Goals`, `Subscriptions`, `Design System` entries; `Goals` and `Subscriptions` MAY be placeholder links until their pages land), a brand block (`Alpaca` mark + `paca` wordmark + a `localhost:host` env chip), a theme toggle, and a `sonner` `<Toaster />` root — that is shared by every page under `app/`.

#### Scenario: every page renders inside the shell

- **WHEN** the operator visits any `app/<page>` route
- **THEN** the top nav, the brand block, the theme toggle, and the toast root are present in the rendered HTML

#### Scenario: theme toggle persists

- **WHEN** the operator clicks the theme toggle and reloads
- **THEN** the previously selected theme (light / dark / system) is restored without a flash of incorrect theme

### Requirement: Bilingual UI via a locale cookie

The dashboard SHALL support English and Chinese UI text via `dashboard/lib/i18n/` (dictionaries + a `getDictionary(locale)` lookup), an `I18nProvider` (`dashboard/components/i18n-provider.tsx`) exposing `useI18n() -> {locale, t}` to client components, and a `LanguageToggle` component (`dashboard/components/language-toggle.tsx`) that flips the locale. The active locale SHALL be persisted in a `paca_locale` cookie (`LOCALE_COOKIE`, 1-year `max-age`, `path=/`, `samesite=lax`) and applied on the server for the initial render.

#### Scenario: operator toggles language

- **WHEN** the operator clicks the language toggle
- **THEN** the `paca_locale` cookie flips between `zh` and `en`, the router refreshes, and subsequently rendered text uses the new locale's dictionary

#### Scenario: locale persists across reloads

- **WHEN** the operator reloads the dashboard after toggling language
- **THEN** the same locale (read from the `paca_locale` cookie) is used for the initial server render, with no flash of the other language

### Requirement: UI primitive library

The dashboard SHALL provide a self-authored set of UI primitives under `dashboard/components/ui/` covering at minimum `Button`, `Card`, `Badge`, `Dialog`, `Sheet`, `Tooltip`, `Collapsible`, `Segmented`, plus a `cn()` utility in `dashboard/lib/utils.ts`. Each primitive that has a Radix equivalent SHALL be built on the matching Radix primitive (e.g. `Dialog` uses `@radix-ui/react-dialog`, `Collapsible` uses `@radix-ui/react-collapsible`), styled to the design tokens from `dashboard/design/styles.css`.

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

The dashboard SHALL port the CSS-variable token set from `dashboard/design/styles.css` (and supplementary tokens from `dashboard/design/pages.css`) into `dashboard/app/globals.css`, wired through Tailwind's `theme.extend` so the same tokens are accessible as both raw CSS variables (e.g. `var(--accent)`) and Tailwind utilities (e.g. `bg-accent`).

#### Scenario: light and dark token sets are both defined

- **WHEN** `dashboard/app/globals.css` is loaded
- **THEN** `:root[data-theme="light"]` and `:root[data-theme="dark"]` blocks each define the full token set (surfaces, text, border, accent, semantic, score-*, shadow-*, line, hover, active)

### Requirement: Score color ramp utilities

The dashboard SHALL expose `scoreHue(s: number): number` and `scoreLOff(s: number): number` from `dashboard/lib/score.ts`, with the same continuous orange→yellow→green ramp as `dashboard/design/data.js`, accepting values in the `0..100` range.

#### Scenario: ramp returns expected hues

- **WHEN** code calls `scoreHue(0)`, `scoreHue(50)`, `scoreHue(100)`
- **THEN** the returned values are approximately `28`, `55`, `143` respectively

#### Scenario: upper-half darkening kicks in

- **WHEN** code calls `scoreLOff(60)` vs `scoreLOff(40)`
- **THEN** the value for `60` is strictly positive (upper half darkens) and the value for `40` is `0`

### Requirement: Brand assets

The dashboard SHALL ship the production brand marks ported from `dashboard/design/components.jsx`: `Alpaca` (filled geometric SVG) at `dashboard/components/brand/alpaca.tsx` and `RadarAlpaca` (animated radar-sweep emblem) at `dashboard/components/brand/radar-alpaca.tsx`. Exploratory variants from the design file (`AlpacaOutline`, `AlpacaFace`, `AlpacaBadge`, `RadarAlpacaScope`, `RadarAlpacaArc`) SHALL NOT be ported.

#### Scenario: marks are usable

- **WHEN** the nav imports `Alpaca` and the `/radar` page imports `RadarAlpaca`
- **THEN** both render at the sizes specified by the design (nav: 20px Alpaca; `/radar` hero: 72px RadarAlpaca with the sweep animation running) and inherit the current accent color via CSS variables

#### Scenario: exploratory variants are absent

- **WHEN** a reviewer searches `dashboard/components/brand/` for `AlpacaOutline`, `AlpacaFace`, `AlpacaBadge`, `RadarAlpacaScope`, or `RadarAlpacaArc`
- **THEN** none of these symbols exist in the production source

### Requirement: Design system page

The dashboard SHALL render `/design` as a living style guide reflecting the design's `pages-ds.jsx`, with four tabs (`Tokens`, `Components`, `States`, `Brand`). The `Brand` tab SHALL show only the production marks (`Alpaca` + `RadarAlpaca`).

#### Scenario: tabs render their reference content

- **WHEN** the operator opens `/design` and switches between the four tabs
- **THEN** each tab shows its corresponding reference (token swatches, primitive usage, interactive states, brand marks at multiple sizes)

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

The dashboard SHALL render `/knowledge` matching the design at `dashboard/design/pages-other.jsx::KnowledgePage`: a left sidebar wiki tree (`PACA_WIKI_DIR`-driven, categorized, collapsible), a search input wired to `gbrain search`, a result-cards column with snippet highlights, and a preview pane showing the active document's frontmatter / tags / body. The `Re-index` action SHALL still invoke `uv run paca run-workflow knowledge_ingest` from the repo root.

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

### Requirement: Design-mocks-driven implementation convention

`dashboard/README.md` SHALL document `dashboard/design/` as the source of truth for visual layouts, instructing implementers to build against those mocks rather than inventing visual layouts. This convention is currently stale/inactive in this trimmed repo: `dashboard/design/` does not exist here (no git history for the directory), even though the README still references it. Implementers SHALL treat the shipped pages under `dashboard/app/` as the current source of truth until/unless the mock directory is restored.

#### Scenario: README documents the convention

- **WHEN** a contributor reads `dashboard/README.md`
- **THEN** they find a section that names `dashboard/design/` as the source-of-truth for visual layouts and instructs implementers to pause and ask if a referenced mock is missing

#### Scenario: referenced mock directory is absent in this repo

- **WHEN** a contributor looks for `dashboard/design/` in this repo
- **THEN** it does not exist; new dashboard work should follow the shipped pages' existing patterns rather than blocking on a missing mock

### Requirement: Dev workflow documentation

`dashboard/README.md` SHALL document the `pnpm dev` (port 3000) + `uv run paca serve` (port 7777) two-process workflow and the `NEXT_PUBLIC_AGENT_OS_URL` env var (default `http://localhost:7777`). It SHALL also document the `paca dashboard` CLI wrapper (a thin `pnpm dev|build|start` exec, see core-cli spec) as an alternative entrypoint.

#### Scenario: README covers the two-process flow

- **WHEN** a new operator reads `dashboard/README.md`
- **THEN** they can start the dashboard and AgentOS together without referring to other docs, and they know which env var points the browser at AgentOS

#### Scenario: README documents the paca dashboard wrapper

- **WHEN** a new operator reads `dashboard/README.md`
- **THEN** they find `paca dashboard` documented as an alternative to running `pnpm dev` directly from `dashboard/`

