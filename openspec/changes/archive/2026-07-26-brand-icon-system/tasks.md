## 1. Tokens and animation

- [x] 1.1 Add the brand token group to `dashboard/app/globals.css` for both `:root[data-theme="light"]` and `:root[data-theme="dark"]`: `--brand-spark-radar` (`#0891b2` / `#22d3ee`), `--brand-spark-kb` (`#db2777` / `#f472b6`), and the three badge gradients `--brand-grad-signal` / `--brand-grad-radar` / `--brand-grad-kb`. Do not reuse `--purple` or any verdict-ramp variable (D2)
- [x] 1.2 Add the `.brand-*` animation block: `.brand-sweep` (4s linear spin, `transform-box: view-box`, origin `50px 50px`), `.brand-blip` (flash keyframes, delays `0s` / `1.72s` / `2.83s` derived per D6), `.brand-chev` (launch wave, delays `0.30s` / `0.52s` / `0.74s`), `.brand-flow` (translate via `--dx` / `--dy` custom props), `.brand-sat` (breathe), `.brand-ping` (expanding ring, `transform-box: fill-box`)
- [x] 1.3 Give every emblem a composed still under `@media (prefers-reduced-motion: reduce)` — beam parked 15° past the first blip, chevrons at their static 0.42 / 0.66 / 1 hierarchy, satellites and flow dots visible (D5). Verify by toggling Reduce Motion, not by reading the CSS
- [x] 1.4 Leave the existing `.blip` / `.radar-sweep` / `radarSpin` / `blipPulse` block in place for now — it is deleted in 5.2 once nothing references it

## 2. Brand components

- [x] 2.1 Create `dashboard/components/brand/signal-mark.tsx` exporting `SignalMark` (`variant: "icon" | "nav"`, default `icon`) and `SignalEmblem`. The `nav` variant re-spaces both chevrons rather than scaling the icon geometry (D4) — it must never fall back to a single chevron
- [x] 2.2 Create `dashboard/components/brand/radar-mark.tsx` exporting `RadarMark` and `RadarEmblem`. Tier contract: emblem = 3 rings + crosshairs + 12 bearing ticks + animated sweep + 3 blips; icon = 2 rings + crosshairs + static wedge + 1 blip; nav = 1 ring + wedge + core. The sweep wedge is present at every tier (D3)
- [x] 2.3 Create `dashboard/components/brand/knowledge-mark.tsx` exporting `KnowledgeMark` and `KnowledgeEmblem`. Edge stroke `2.4` at icon tier and `2.5` at nav tier — the larger authored value belongs to the smaller render (D4)
- [x] 2.4 Confirm all three take colour from `currentColor` and the brand tokens with no baked hex in the flat tiers, so one asset serves light and dark. Emblems set no background
- [x] 2.5 Confirm the emblems need no `"use client"` — they are static SVG with CSS-driven animation and must stay server components (D5)

## 3. Call sites

- [x] 3.1 `dashboard/components/nav.tsx`: brand block renders `SignalMark` on the `--brand-grad-signal` tile; wordmark becomes `next-signal` (D7)
- [x] 3.2 `dashboard/components/nav.tsx`: `/radar` and `/knowledge` nav entries use `RadarMark` / `KnowledgeMark` at `variant="nav"`; `/goals`, `/subscriptions`, `/design` stay on lucide (D8). Check the brand glyphs sit at the same optical weight as the neighbouring lucide icons
- [x] 3.3 `dashboard/app/radar/page.tsx`: hero renders `<RadarEmblem size={72} />`
- [x] 3.4 `dashboard/app/layout.tsx`: document title becomes `next-signal · local dashboard`
- [x] 3.5 Add `dashboard/app/icon.svg` — the Vanguard mark on the signal gradient, self-contained with baked colours since a favicon cannot read CSS variables. Confirm the browser tab stops showing the Next.js default

## 4. Design system page

- [x] 4.1 Rebuild the `Brand` tab in `dashboard/app/design/page.tsx`: all three families, each at emblem / icon / nav tier, so a broken mark is visible somewhere (see Risks)
- [x] 4.2 Add the brand tokens to the `Tokens` tab — spark swatches and gradient chips — per the project rule that new tokens are documented in `/design` in the same change
- [x] 4.3 Remove the `Alpaca glyph` and `Radar emblem` sections and the two now-dead imports

## 5. Retire the alpaca

- [x] 5.1 Delete `dashboard/components/brand/alpaca.tsx` and `dashboard/components/brand/radar-alpaca.tsx`
- [x] 5.2 Delete the old `.radar-emblem` / `.radar-sweep` / `.blip` / `radarSpin` / `blipPulse` block from `globals.css`
- [x] 5.3 Grep the dashboard for `Alpaca`, `alpaca`, `radar-sweep`, `blip`, and `radarSpin` and confirm zero hits outside `node_modules` — a dangling class name is invisible until it silently does nothing

## 6. Verify

- [x] 6.1 `pnpm typecheck` and `pnpm lint` clean in `dashboard/`
- [x] 6.2 Rebuild and restart the dashboard container (`docker compose build dashboard && docker compose up -d dashboard`) and verify against the running stack, not a host `next dev` — a second Next process would share `.next` and corrupt the build manifest
- [x] 6.3 Check every mark at its real size in both themes: nav brand block, both nav glyphs, `/radar` hero emblem, `/design` all tiers. Confirm the radar sweep and its blips are in phase — a blip lighting while the beam is elsewhere means 1.2 is wrong
- [x] 6.4 Confirm no horizontal overflow and no hydration warning in the console after the nav change

## 7. Specs and docs

- [x] 7.1 Apply the `dashboard-shell` delta — `Brand assets`, `Global app shell`, `Design token system`, `Design system page`
- [x] 7.2 Apply the `dashboard-radar-reader` delta — `/radar` hero renders `RadarEmblem`
- [x] 7.3 Update `dashboard/README.md` and `dashboard/README.zh-CN.md` together, English canonical: name the three brand families, the tier contract, and the brand token group in the "Visual design system" section. Both languages ship in this change — one side alone is not done
