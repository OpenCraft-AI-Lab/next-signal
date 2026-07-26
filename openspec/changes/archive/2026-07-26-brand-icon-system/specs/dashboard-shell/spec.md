## MODIFIED Requirements

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

### Requirement: Design token system

The dashboard SHALL define the CSS-variable token set in `dashboard/app/globals.css`, wired through Tailwind's `theme.extend` so the same tokens are accessible as both raw CSS variables (e.g. `var(--accent)`) and Tailwind utilities (e.g. `bg-accent`).

The token set SHALL include a brand group: `--brand-spark-radar` and `--brand-spark-kb` (the single secondary colour each module mark is allowed to spend), and `--brand-grad-signal`, `--brand-grad-radar`, `--brand-grad-kb` (badge tile gradients). Brand tokens SHALL be defined independently of the semantic verdict colours and SHALL NOT alias `--purple`, `--green`, or the score ramp, so brand hue and status hue remain separately changeable.

#### Scenario: light and dark token sets are both defined

- **WHEN** `dashboard/app/globals.css` is loaded
- **THEN** `:root[data-theme="light"]` and `:root[data-theme="dark"]` blocks each define the full token set (surfaces, text, border, accent, semantic, score-*, shadow-*, line, hover, active, brand)

#### Scenario: brand colour is independent of status colour

- **WHEN** a reviewer inspects the brand token declarations
- **THEN** each resolves to its own literal value rather than referencing a verdict or score variable

### Requirement: Design system page

The dashboard SHALL render `/design` as a living style guide, with four tabs (`Tokens`, `Components`, `States`, `Brand`). The `Brand` tab SHALL show all three brand families, each at its emblem, icon, and nav tier. The `Tokens` tab SHALL include the brand token group. `/design` is the only regression net for the marks, so a newly added mark, tier, or brand token SHALL be added to this page in the same change that introduces it.

#### Scenario: tabs render their reference content

- **WHEN** the operator opens `/design` and switches between the four tabs
- **THEN** each tab shows its corresponding reference (token swatches including the brand group, primitive usage, interactive states, and all three brand families across all three tiers)
