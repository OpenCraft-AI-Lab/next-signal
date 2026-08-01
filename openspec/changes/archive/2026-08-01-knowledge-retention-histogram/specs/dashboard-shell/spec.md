## MODIFIED Requirements

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

### Requirement: Design system page

The dashboard SHALL render `/design` as a living style guide, with four tabs (`Tokens`, `Components`, `States`, `Brand`). The `Brand` tab SHALL show all three brand families, each at its emblem, icon, and nav tier. The `Tokens` tab SHALL include the brand token group and the knowledge retention ramp group. `/design` is the only regression net for the marks and for these token groups, so a newly added mark, tier, brand token, or retention ramp token SHALL be added to this page in the same change that introduces it.

#### Scenario: tabs render their reference content

- **WHEN** the operator opens `/design` and switches between the four tabs
- **THEN** each tab shows its corresponding reference (token swatches including the brand group and the retention ramp, primitive usage, interactive states, and all three brand families across all three tiers)

#### Scenario: the retention ramp is shown across its range

- **WHEN** the operator opens the `Tokens` tab
- **THEN** the retention ramp is shown as swatches spanning its endpoints, together with the off-ramp neutral, in the active theme
