## Context

The dashboard's design system is already token-driven and self-authored: `globals.css` holds the full light/dark token set, `components/ui/` holds the primitives, and `/design` is the living reference. Brand marks are the one part of that system that never became systematic — `Alpaca` is a filled character, `RadarAlpaca` wraps that character in an unrelated line-art scope, and neither has a defined behaviour at small sizes.

Three constraints shape this design:

1. **One asset must serve light and dark.** Every existing mark takes its colour from CSS variables rather than baking hex values. The new marks keep that, which rules out any raster or gradient-baked SVG for the flat tiers.
2. **The nav is the hardest case, not the easiest.** The brand mark renders at 20px inside a 27px tile, and the nav glyphs at 15–16px. A mark that only works at hero size is not a mark.
3. **`globals.css` is a single global stylesheet.** The existing animation hooks (`.blip`, `.radar-sweep`) are unnamespaced generic words. Adding four more (`.chev`, `.flow`, `.sat`, `.ping`) at global scope would be actively hostile to whoever writes the next component.

## Goals / Non-Goals

**Goals:**

- Three marks that read as one system, from a shared atom and a shared grid.
- A defined, explicit answer to "what does this mark look like at 16px" for each family.
- Colour entirely from tokens, so light/dark is one asset.
- Retire the alpaca completely — no dormant exports, no variants left behind.

**Non-Goals:**

- Renaming anything outside the dashboard's visible brand layer. `paca` remains the package, the CLI, the env prefix, and the subprocess launcher.
- A general-purpose icon library. These are brand marks; product iconography stays lucide.
- Automatic tier selection by size. See D3.

## Decisions

### D1: Three coordinate systems, one atom

Each mark is nodes plus exactly one connective form, and each family gets its own geometry of thought:

| Family | Field | Connective form | Motion |
| --- | --- | --- | --- |
| next-signal | linear | chevron | launch wave fires outward through the gates |
| info-radar | polar | wedge | beam sweeps; blips light as it passes |
| knowledge-base | network | link | signals converge inward to the index |

This is what makes them siblings rather than three drawings that happen to share a hue. It also gives a rule for future marks: a new machine earns a new field, not a new decorative flourish.

The parent mark is the **Vanguard** — a node leaving the origin and accelerating up-and-right through two chevrons. Two earlier candidates were rejected: a monogram `N` (ownable but safe, and says nothing about the product) and a rotationally symmetric aperture (the best pure app icon, but says *system* rather than *ahead*). The round-one parent — three arcs radiating from a corner node — was retired because it is structurally the RSS/wifi glyph and therefore was never ownable.

### D2: Violet is the family, the spark is the module

Violet (`--accent`) carries structure in all three marks. Each module mark spends exactly one secondary colour, on the single element that *is* that module's job: cyan on the radar's caught blip, magenta on the knowledge hub. The parent mark spends none — it is the family colour, undiluted.

The sparks get their own tokens (`--brand-spark-radar`, `--brand-spark-kb`) rather than reusing `--purple` / `--green` / the verdict ramp. Brand hue and status hue must stay independently changeable; a radar blip that shares a variable with "verdict: keep" will eventually be wrong in one place or the other.

### D3: Tiers are explicit props, not size thresholds

A mark could inspect its `size` and pick a detail level automatically. It will not. Auto-switching means a component silently renders different geometry depending on a number, which is invisible in review and surprising at boundaries.

Instead each family exports two components, and the flat one takes an explicit `variant`:

```tsx
<SignalMark size={20} variant="nav" />     // flat glyph, currentColor
<RadarEmblem size={72} />                  // animated, transparent
```

- `variant="icon"` (default) — full detail, for 24–48px and badge tiles.
- `variant="nav"` — reduced detail and retuned weight, for 15–20px.

What each tier drops is a real design decision, recorded in the spec so it survives a refactor. The radar is the clearest case: bearing ticks exist only at emblem size, the inner ring and crosshairs drop below icon size, and the **sweep wedge is never dropped** — it is the single element separating a radar from a target reticle.

### D4: The nav tier is not a scaled-down icon tier

Stroke weights do not scale linearly with render size. The knowledge mark uses stroke `2.4` at icon tier and `2.5` at nav tier — a *larger* authored number for the smaller render, because a 24-unit viewBox drawn into 16px scales by 0.667, putting the nav stroke at 1.67 device pixels against the icon's 2.4. The parent mark goes further and changes geometry outright: the nav variant re-spaces both chevrons rather than inheriting the icon's spacing, so the pair keeps roughly two device pixels of clearance at 16px instead of merging into a smear.

This is why the round-1 nav glyph had dropped to a single chevron and had to be fixed: reducing detail is legitimate, but not when it costs the mark its signature.

### D5: Animation lives in `globals.css`, namespaced `.brand-*`

Keeping keyframes in the global stylesheet matches the existing pattern (`.radar-sweep` is already there) and keeps the emblems as plain SVG with no client-side JS — they can stay server components.

Every hook gets a `brand-` prefix. The retired names (`.blip`, `.radar-sweep`) are generic enough to collide with real feature CSS, and this change is adding four more concepts (`chev`, `flow`, `sat`, `ping`) that would be far worse offenders unprefixed.

Each emblem must hold a **composed still** under `prefers-reduced-motion: reduce` — not a frozen frame at t=0, which for the radar parks the beam on top of a blip and for the knowledge graph hides the travelling signals behind the concept nodes. The reduce branch positions the beam 15° past the first blip so it reads as *just detected*.

### D6: Blip timing is derived, not eyeballed

The current emblem animates blips on a 2.4s pulse against a 4.5s sweep. Those do not divide, so a blip lights while the beam is on the far side of the scope — the emblem is animated, but it is not depicting radar.

The replacement derives each delay from geometry. The beam starts at bearing 45° and turns 90°/s at a 4s revolution, so a blip at bearing `B` lights at:

```
t = (B - 45) / 90
```

giving 0s / 1.72s / 2.83s for the three blips. Any future blip must have its delay computed the same way; a hand-tuned value is a bug waiting to happen.

### D7: Wordmark moves to `next-signal`, code identifiers do not

The nav wordmark and document title become `next-signal`, matching the repo. This is deliberately scoped to the visible brand layer: `paca` stays the Python package, the CLI binary, the `PACA_*` env prefix, and the `spawnPaca*` launcher names. Renaming a visible label is a brand decision; renaming identifiers is a migration, and this change is not that.

### D8: Radar and Knowledge nav links adopt the brand glyphs

`/radar` and `/knowledge` are the two products with brand marks, so their nav entries use them. `Goals` and `Subscriptions` are plain sections with no mark and stay on lucide. The mixed set is intentional and legible — having a brand glyph *means* something, and it would stop meaning anything if every nav row had one.

## Risks / Trade-offs

- **Mixed nav iconography.** Two brand glyphs beside two lucide icons could read as inconsistent rather than hierarchical. Mitigated by weight-matching the glyphs to lucide's 24-grid/stroke-2 convention. If it reads badly in the container, D8 is the cheapest decision to reverse — revert two imports.
- **`/design` is the only regression net.** There are no visual tests. The Brand tab showing all three families at all three tiers is what makes a broken mark visible, so it has to be built in this change rather than deferred.
- **Deleting rather than deprecating.** `Alpaca` and `RadarAlpaca` are removed outright. Both have exactly three call sites between them, all updated here, and the existing spec already forbids keeping unused brand variants around.

## Migration Plan

Components land before call sites, so nothing is ever importing a deleted file:

1. Add brand tokens and the `.brand-*` animation block to `globals.css`, leaving the old `.blip` / `.radar-sweep` block in place.
2. Add the three new brand components.
3. Repoint the three call sites (`nav.tsx`, `radar/page.tsx`, `design/page.tsx`) and the title.
4. Delete `alpaca.tsx`, `radar-alpaca.tsx`, and the old animation block together.
5. Verify in the running container, then sync specs and bilingual docs.

## Open Questions

None. Wordmark scope (D7) and nav-icon split (D8) were confirmed with the operator before this change was written.
