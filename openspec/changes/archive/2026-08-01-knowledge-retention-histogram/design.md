## Context

`knowledge_reviews` already stores everything this chart needs: `stage` (0-based count of
completed reviews), `captured_at`, and `next_due_at` (`NULL` once a doc passes the final stage).
`REVIEW_STAGES = [1, 3, 7, 15, 30, 60, 120]` in `dashboard/lib/knowledge/review.ts` mirrors
`paca.workflows.knowledge_review`, which is the source of truth for the arithmetic.

The review section renders server-side and takes its dictionary as a `t` prop
(`review-section.tsx`); it never writes review state during render. The radar page already
solves the visually equivalent problem — `ScoreHistogram` in a fixed-width slot on
`TodayTracker`'s header — and that component's geometry is the style target here.

Constraint worth stating up front: the production table currently holds 2 enrolled docs. The
design has to look deliberate at N=2 as well as N=200.

## Goals / Non-Goals

**Goals:**

- Show, at a glance, how the enrolled collection is distributed across the curve, and how much of
  it is already due.
- Reuse the radar histogram's visual language so the two pages read as one system.
- Stay a server component with no client-side JavaScript and no extra round trip.
- Keep the signal present in the collapsed "nothing due" state, which today carries none.

**Non-Goals:**

- Changing the schedule, the stage arithmetic, enrollment, or the "seen" advance.
- Forecasting future review load by day. That is a different chart answering a different
  question; this one is about position on the curve.
- Interactivity — no filtering, no drill-down, no click-through to a stage's docs.
- Drawing the forgetting curve itself. Prototypes that did (a retention sawtooth with one dot per
  doc) read better as an explainer but cost roughly 150px of vertical space at full card width;
  the histogram was chosen for the header slot.

## Decisions

### Bins come from `stage`, not from date arithmetic

Eight bins: `stage` 0..6, labelled by the interval each is waiting on (`1d` … `120d`), plus a
terminal bin for `next_due_at IS NULL`.

`stage` is already the authoritative position on the curve, and `advanceReview` deliberately
fast-forwards it (`GREATEST(stage + 1, stages-already-elapsed)`) inside SQL. Deriving bins from
`captured_at` and today in TypeScript would re-implement that rule in a second place and drift
from it. Alternative rejected: bucketing by `next_due_at - captured_at`, which is the same
information one inference removed and breaks for retired rows.

### One aggregate query, run alongside the existing one

A single `GROUP BY stage` with `count(*) FILTER (WHERE next_due_at IS NOT NULL AND next_due_at <=
today)` for the due split, using the same `RADAR_TZ` day boundary as `getDueReviews` so "due" means
the same thing in the chart and in the cards. It joins the existing `Promise.all` in the section's
data load rather than adding a serial round trip.

Deriving the distribution from the already-fetched due rows is not an option — those are capped at
5 and filtered to due-only.

### A new `--kb-*` ramp, not `scoreColor()`

`globals.css` already carries the rule that brand colour and verdict colour stay separately
changeable, and `scoreHue`/`scoreLOff` implement the radar's orange→green *verdict* ramp. Reusing
it would make a doc at the 120d stage green — reading as "scored well" rather than "consolidated".

The new group is a single-hue sequential ramp on the KB brand hue (333°), pale→deep in light,
dim→bright in dark:

```css
:root, [data-theme="light"] { --kb-h:333; --kb-s:70%; --kb-l-lo:78%; --kb-l-hi:38%; --kb-held:#b0b0b0; }
[data-theme="dark"]        { --kb-h:333; --kb-s:64%; --kb-l-lo:28%; --kb-l-hi:74%; --kb-held:#4e4e4e; }
```

Colour is redundant with x-position here, which is intentional and matches `ScoreHistogram` — the
bin's identity survives being read at a glance, out of order, or in a tooltip.

### The ramp interpolates in CSS, not in JS

The helper returns an `hsl()` expression whose endpoints are the theme variables:

```
hsl(var(--kb-h) var(--kb-s) calc(var(--kb-l-lo) + (var(--kb-l-hi) - var(--kb-l-lo)) * <t>))
```

Same technique as `scoreColor()`, and it is what lets the component stay server-rendered: the
server cannot know the reader's theme, so the theme has to resolve in the cascade. A JS-computed
hex would need a client component and would flash the wrong colour on theme switch.

### Due sits at the baseline, scheduled above it, same hue

Each bar is two stacked segments separated by a 2px gap: the due count solid at the baseline, the
remainder above at ~32% opacity. Bar height stays the bin total, so the chart still reads as a
distribution.

Alternatives rejected: colouring due in `--amber` (that token means warning/degraded elsewhere —
being due is normal, not a fault); a separate overlay row (doubles the height budget for one extra
number).

### The terminal bin is off-ramp

Docs past 120 days get a neutral grey, not the deep end of the pink ramp. They are no longer
decaying or scheduled, so placing them at the extreme of a continuum they have left would invite
reading them as "most consolidated" on the same scale. Grey says "out of rotation".

### Exact counts live in the tooltip, not above the bars

`max`-scaled bars mean one dominant bin flattens the rest — with the real distribution likely
skewed toward early stages, that is the expected case, not the edge case, so exact counts have to
be recoverable some other way.

Printing a count above every bar was the first answer, and it is what the prototype did. It loses
to matching the radar: `ScoreHistogram` sizes bars as `(value / max) * (height - 14)` with the
tick label living *inside* the 56px block, so adding a count row either overflows that block or
squeezes the tallest bar from 42px down to 27px. Either way the two pages stop looking alike,
which is the thing this component is for.

A native `title` on each bar carries the bin's total and due count instead. It costs no
JavaScript, no layout, and no divergence.

### The split needs a key; the ramp does not

Dropping the count row is safe. Dropping the *legend* is not, and the first cut of this component
did both by copying `ScoreHistogram` wholesale. That copy does not transfer: a score bar is a
single solid fill whose colour the x-axis already explains, whereas a retention bar is two
segments separated only by opacity. A reader meeting a two-tone bar with no key cannot tell
whether the solid part means due, overdue, or read — and nothing else on the page says.

So the full variant carries a two-item key (`due` / `scheduled`) below the tick labels. Two items,
not three: the terminal bar's own `done` tick already explains its grey, and a third entry would
crowd the 232px slot.

The key renders in every state, including when nothing is due and no bar is split. It costs one
row, and a key that comes and goes teaches the reader nothing.

### Placement mirrors the radar tracker exactly

`TodayTracker` does not put its histogram in the header row. Its card is a header row (badge,
date, source chips) followed by a stats strip, and the histogram is the strip's trailing cell:
`justifySelf: "end"`, `minWidth: 232`. The review section copies that structure — header row
untouched, histogram flush right in a strip below it, above the cards.

Geometry is copied from `ScoreHistogram` rather than re-chosen: `height: 56`, `gap: 3` between
bars, `borderRadius: 2`, an `eyebrow` label above, 9px mono tick labels below. Fixed slot width
rather than fluid, so eight bins never degrade into slivers when the header text is long or the
locale is verbose.

The leading edge carries a summary, as the radar strip does: stat pills, `vdiv` separators, chart
flush right. Every figure comes from the bins already fetched, so the summary costs no query —
enrolled, due, scheduled, done, plus the stage the median doc is waiting on.

The median is the one figure that is not a count, and it is the reason the summary is worth its
row: it answers "where is my collection on the curve" in one glance, which is the question the
chart exists for and which reading eight bars only approximates. Docs past the final stage sort
after every stage, so a mostly-retired collection reads as done rather than as its last active
bin.

The due figure repeats the header chip in the populated state. That is worth it — the chip
disappears when nothing is due, and a summary whose row shape changes between states is worse
than one number appearing twice.

### The frame always renders; there is no reduced variant

The first cut had two escape hatches: return `null` when nothing is enrolled, and a `compact`
prop that dropped the axis and key for the collapsed "nothing due" line. Both are wrong, and
`ScoreHistogram` shows why — on a day with no items the radar tracker still reads "Score
distribution · 0-100" over a full eleven-tick axis. The chart holds its shape and its space.

Stripped of its labels, this chart is worse than absent: the collapsed line rendered a lone
two-tone block with no title, no axis, and no key, which is a shape rather than a chart. And a
chart that disappears entirely at zero moves everything beneath it the moment the first doc
enrolls.

So the component has one form, and so does the section around it. The `total === 0` branch keeps
the panel, the header, and the strip, and drops only the *cards* — the "nothing due" line takes
the subtitle's place. Dropping the card chrome as well (which the first pass did) left the
summary and chart floating unframed, reading as a different component rather than the same one
with less to say.

The existing requirement is amended to say what it was actually protecting against: an empty
panel. The section is never empty now — it always carries the collection's position on the curve
— so the reason to strip its frame is gone.

### Server component, dictionary by prop

`ScoreHistogram` is a client component only because it calls `useI18n()`. This one follows
`ReviewSection` and takes `t` as a prop, so it stays server-rendered with zero hydration cost.
Per-bar tooltips use the native `title` attribute, which needs no JavaScript.

## Risks / Trade-offs

- **The chart is nearly empty at today's N=2** → counts printed above bars, and the zero-enrolled
  case renders nothing rather than a row of empty slots. The chart earns its space as the base
  grows; it does not mislead before then.
- **Due vs scheduled is encoded by opacity alone within a bar** → the due total also appears as a
  chip in the header, per-bar tooltips state both numbers, and the count label gives the total. No
  fact is available only from the opacity.
- **A new token group is one more thing `/design` has to keep honest** → `dashboard-shell` already
  requires new tokens to land on `/design` in the same change; this change carries that task.
- **`REVIEW_STAGES` now has two jobs** (mirroring the Python schedule, and defining the chart's
  bins) → the existing comment naming Python as the source of truth is extended to cover the bin
  role, so a schedule change still has exactly one place to update on this side.
- **Skew makes the tall bin dominate** → accepted. It is the true shape of the data, and the
  printed counts recover the detail that bar height loses.

## Migration Plan

None. No schema change, no data migration, no backfill — the change only reads columns that
`knowledge_reviews` has carried since the `knowledge-review` change. Rollback is a revert; the
review section returns to its current header and collapsed line with no state to unwind.

## Open Questions

- Docs retire permanently once past 120 days (`next_due_at = NULL`), so the terminal bin only ever
  grows. If re-enrollment is ever wanted, that bin becomes a queue rather than a resting place and
  its neutral colour should be revisited. Out of scope here; flagged so the colour choice is not
  mistaken for a claim that the state is final by design.
