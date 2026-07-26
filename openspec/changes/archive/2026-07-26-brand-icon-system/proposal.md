## Why

The repo is `next-signal`; the brand is an alpaca. The two marks the dashboard ships — `Alpaca` and `RadarAlpaca` — encode a name the project no longer carries, and they were never a system: the alpaca is a filled character glyph, the radar emblem is a line-art scope with the character dropped in the middle. Nothing connects them beyond both being violet.

The mark that has to work hardest is also the weakest. `Alpaca` is the only mark in the nav, the only candidate for a favicon, and the only thing standing in for the product itself — and a filled animal silhouette at 20px reads as a blob. There is no favicon at all today (`dashboard/app/` has no `icon.*`), so a browser tab shows the default Next.js globe.

The replacement is a system rather than three drawings: one node atom, one violet family, three coordinate systems that each say what their machine does — the parent moves along a line, the radar sweeps a circle, the knowledge base traverses a network.

## What Changes

- **Three new brand components** replacing `Alpaca` + `RadarAlpaca`. Each family ships two exports: a **mark** (flat glyph, `icon` and `nav` detail tiers) and an **emblem** (animated, transparent, 64–192px). Detail is a function of size — the radar keeps 12 bearing ticks at emblem size, two rings at icon size, and one ring plus the sweep wedge at nav size, because the wedge is the one element that stops a radar reading as a target.
- **New brand tokens** in `globals.css`: two spark colours (`--brand-spark-radar`, `--brand-spark-kb`) and three badge gradients, each defined for light and dark. The sparks are deliberately *not* the existing `--purple` / semantic verdict colours — brand hue and status hue must stay separable.
- **Emblem animation moves to namespaced classes.** The current `.blip` / `.radar-sweep` / `.radarSpin` / `.blipPulse` block is replaced by `.brand-*` equivalents, and the sweep/blip desync is fixed: blips currently pulse on a 2.4s timer against a 4.5s sweep, so they light when the beam is nowhere near them.
- **Wordmark becomes `next-signal`** in the nav brand block and the document title, replacing `paca`.
- **Nav link icons for Radar and Knowledge** switch from lucide (`Radar`, `Book`) to the brand nav glyphs. `Goals` and `Subscriptions` have no brand mark and stay on lucide.
- **A favicon ships** — `dashboard/app/icon.svg`, the Vanguard mark on the signal gradient.
- `/design` Brand tab is rebuilt to show all three families across all three tiers; the new tokens are added to the Tokens tab.
- Bilingual dashboard README updates, English canonical.

Non-goals: no change to any Python surface, env var, module, or config key — `paca` stays the package name and the CLI name, and this change renames nothing outside the dashboard's visible brand layer. No new pages or routes. No motion beyond the three emblems.

## Capabilities

### Modified Capabilities

- `dashboard-shell`: the **Brand assets** requirement is rewritten around the three-family system and its tier contract; **Global app shell** changes the brand block to the Vanguard mark plus a `next-signal` wordmark and pins the nav-icon split; **Design token system** gains the brand token group; **Design system page** changes what the Brand tab must show.
- `dashboard-radar-reader`: the `/radar` hero renders `<RadarEmblem />` instead of `<RadarAlpaca />`.

## Impact

**New files**: `dashboard/components/brand/signal-mark.tsx`, `radar-mark.tsx`, `knowledge-mark.tsx`, `dashboard/app/icon.svg`.

**Deleted**: `dashboard/components/brand/alpaca.tsx`, `dashboard/components/brand/radar-alpaca.tsx`.

**Modified**: `dashboard/app/globals.css` (brand tokens + `.brand-*` animation block, replacing the `.blip` / `.radar-sweep` block), `dashboard/components/nav.tsx` (brand block, wordmark, two nav icons), `dashboard/app/layout.tsx` (title), `dashboard/app/radar/page.tsx` (hero emblem), `dashboard/app/design/page.tsx` (Brand tab + Tokens tab), `dashboard/README.md` + `dashboard/README.zh-CN.md`.

**Risk**: the generic global class names being retired (`.blip`, `.radar-sweep`) are referenced only by `radar-alpaca.tsx`, which this change deletes — but they are unnamespaced, so the replacement uses `.brand-*` to avoid collecting future collisions.

**Verification**: the dashboard already runs in the Compose stack on port 3000, so runtime checks go through the container per project convention rather than a second host `next dev`.
