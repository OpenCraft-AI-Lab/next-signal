## 1. Retention ramp tokens

- [x] 1.1 Add the `--kb-*` retention ramp group to both theme blocks in `dashboard/app/globals.css` (hue, saturation, the two lightness endpoints, and the off-ramp neutral), with a comment stating why it does not alias `--score-*` or the semantic verdict colours
- [x] 1.2 Add a `retentionColor(t: number): string` helper next to `dashboard/lib/score.ts`, returning the `hsl(... calc(...))` expression that interpolates between the two theme-provided endpoints — mirroring how `scoreColor` defers to CSS so a server component stays theme-correct
- [x] 1.3 Add the ramp swatches plus the off-ramp neutral to the `Tokens` tab of `dashboard/app/design/page.tsx` (required by `dashboard-shell`: new tokens land on `/design` in the same change)

## 2. Stage distribution query

- [x] 2.1 Add `getStageDistribution()` to `dashboard/lib/knowledge/review.ts`: `GROUP BY stage` with a `count(*) FILTER (...)` for the due split, using the same `RADAR_TZ` day boundary as `getDueReviews`
- [x] 2.2 Extend the `REVIEW_STAGES` comment to record its second job — it now defines the histogram's bins as well as mirroring the Python schedule
- [x] 2.3 Export a pure `toBins(rows)` helper that shapes sparse query rows into the fixed 8-bin array (7 stages + terminal), filling absent stages with zeros
- [x] 2.4 Call `getStageDistribution()` inside the existing `Promise.all` in the section's data load, not as a serial round trip
- [x] 2.5 Add `dashboard/lib/retention-bins.test.ts` covering `toBins`: sparse rows, an out-of-range stage, all-zero input, and terminal-bin rows. Top-level `lib/` so the existing `tsx --test lib/*.test.ts` glob picks it up without touching the test script

## 3. Histogram component

- [x] 3.1 Add `dashboard/components/knowledge/retention-histogram.tsx` as a server component taking the bins and `t` as props (follow `ReviewSection`, not `ScoreHistogram` — no `useI18n`, no hydration)
- [x] 3.2 Render 8 bars scaled to the max bin: due segment solid at the baseline, scheduled above at reduced opacity, 2px gap between them. Copy `ScoreHistogram`'s geometry exactly — `height: 56`, `gap: 3`, `borderRadius: 2`, eyebrow above, 9px mono ticks below
- [x] 3.3 Label each bar with its interval below (9px mono, as in `ScoreHistogram`); give the terminal bin the off-ramp neutral and its own label. No count row — it would break the shared 56px block, and the tooltip carries the numbers
- [x] 3.4 Add a native `title` on each bar stating bin, total, and due count — no JavaScript
- [x] 3.5 Add a two-item `due` / `scheduled` key below the tick labels — the split is opacity-only and nothing else on the page explains it
- [x] 3.6 Render the full frame (eyebrow, all eight axis labels, key) in every state, including zero enrolled — as `ScoreHistogram` does on a day with no items. No `null` return, no reduced variant

## 4. Wire into the review section

- [x] 4.1 In `dashboard/components/knowledge/review-section.tsx`, add a strip below the header row holding the histogram at its trailing edge (`justifySelf: "end"`, `minWidth: 232`) — the same seating `TodayTracker` gives `ScoreHistogram`. Leave the header row as it is
- [x] 4.2 In the `total === 0` branch, keep the panel, header, and strip and drop only the cards — the "nothing due" line replaces the subtitle. Both states share one card and one header shape
- [x] 4.3 Confirm the due total across bins matches the section's `total` — same day boundary, same predicate

## 4b. Summary on the strip's leading edge

- [x] 4b.1 Add a `ReviewStat` pill mirroring `StatPill` on the radar tracker, and lay the strip out as `TodayTracker` does: pills, `vdiv` separators, chart flush right
- [x] 4b.2 Derive enrolled / due / scheduled / done from the bins already fetched — no second query
- [x] 4b.3 Add a median-stage figure (the stage the middle doc waits on, with retired docs sorting after every stage), the one summary figure that is not a count
- [x] 4b.4 Name the Ebbinghaus curve outright in the chart title, in both locales

## 5. Strings

- [x] 5.1 Add the histogram's labels (section eyebrow, enrolled-count chip, due/scheduled/terminal legend, bar tooltip) to `dashboard/lib/i18n/dictionaries.ts` in both locales, English canonical
- [x] 5.2 Verify the fixed-width header slot holds without overflow in both locales

## 6. Docs

- [x] 6.1 Update the review section's description in `docs/modules/knowledge.md`
- [x] 6.2 Mirror the same edit in `docs/zh/modules/knowledge.md` — both languages in this change, per CLAUDE.md

## 7. Verify

- [x] 7.1 `pnpm test`, `pnpm typecheck`, and `pnpm lint` clean in `dashboard/`
- [x] 7.2 `docker compose build && docker compose up`, then check `/knowledge` in both themes and both locales — runtime verification goes through the container, not a bare host dev server
- [x] 7.3 Check all three states against real data: docs due, nothing due but docs enrolled, nothing enrolled — confirming the frame holds in all three (seed extra rows to exercise a populated distribution, then remove them)
- [x] 7.4 Confirm loading `/knowledge` still inserts, advances, and retires nothing — the render path stays read-only
- [x] 7.5 Stop the compose stack and drop any seeded rows
