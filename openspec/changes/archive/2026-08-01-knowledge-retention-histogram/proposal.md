## Why

The review section tells the reader what is due *today* and nothing about the shape of the
collection behind it. A knowledge base whose docs are all sitting at the 1-day stage and one
whose docs have mostly reached 120 days both render as "3 due" — the reader cannot tell whether
the base is still fragile or largely consolidated, and has no signal about the review load
building up behind today's cards. The radar page already answers the equivalent question for
signals with its score histogram; `/knowledge` has no counterpart.

## What Changes

- Add a retention histogram to the `/knowledge` review section: one bin per Ebbinghaus stage
  (`1d, 3d, 7d, 15d, 30d, 60d, 120d`) plus a terminal bin for docs past the final stage, showing
  how many enrolled docs sit at each, split into the portion already due and the portion still
  scheduled.
- Add a stage-distribution query alongside the existing due-cards query, so the section's single
  render pass covers both.
- Render the histogram in a fixed-width slot on the review section header, mirroring how the radar
  tracker seats its score histogram — and keep it visible in the collapsed "nothing due" state,
  which today shows only a bare line.
- Add a knowledge retention colour ramp to the token set, running pale (fragile) to deep
  (consolidated) on the KB brand hue. It is a new token group, deliberately **not** an alias of
  the score ramp: that ramp encodes the radar's verdict, and reusing it would read a high stage as
  a high score.
- Cover the new tokens on `/design` and add the section's new strings to both locales.

No change to the review schedule, the stage arithmetic, enrollment, or the "seen" advance — this
change only reads what `knowledge_reviews` already stores.

## Capabilities

### New Capabilities

None. This extends two existing dashboard capabilities.

### Modified Capabilities

- `dashboard-knowledge-review`: new requirement for the stage-distribution histogram — its bins,
  its due/scheduled split, its placement in both the populated and collapsed states, and the rule
  that it never writes review state.
- `dashboard-shell`: the design token requirement gains the knowledge retention ramp group, under
  the same independence rule the brand tokens already carry (no aliasing of the semantic verdict
  colours or the score ramp).

## Impact

- `dashboard/lib/knowledge/review.ts` — new stage-distribution query; `REVIEW_STAGES` becomes the
  bin definition as well as the schedule mirror.
- `dashboard/components/knowledge/` — new histogram component; `review-section.tsx` gains the
  header slot and keeps the histogram in its `total === 0` branch.
- `dashboard/app/globals.css` — new `--kb-*` token group in both themes.
- `dashboard/app/design/page.tsx` — token swatches for the new group.
- `dashboard/lib/i18n/dictionaries.ts` — new strings, English canonical, both locales.
- `docs/modules/knowledge.md` + `docs/zh/modules/knowledge.md` — the review section's description.
- No Python, no schema, no migration: `knowledge_reviews` already carries `stage` and
  `next_due_at`.
