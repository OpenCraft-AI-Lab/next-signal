## MODIFIED Requirements

### Requirement: Review section on the knowledge page

The `/knowledge` page SHALL render a review section above the ingest form showing the documents currently due, each as a card with the doc's title, its capture date, which review this is (stage position), and the doc's frontmatter `summary`. A card's body SHALL open that doc's full-text preview in the same page's preview pane and bring the pane into view (an in-page anchor), so a review card re-reads the source rather than only reminding the reader it is due. Opening a card MUST NOT advance its stage — reading and the "seen" acknowledgement are distinct. When nothing is due, the section SHALL drop the due cards and say so in place of the subtitle, while keeping its panel, its header, and its summary-and-chart strip. The section is never an empty panel — it always carries the collection's position on the curve — so what collapses is the card list, not the frame.

#### Scenario: due cards render with the doc summary

- **WHEN** three docs are due
- **THEN** the section renders three cards, each showing title, capture date, review position, and the doc's summary

#### Scenario: clicking a card opens the full text without dismissing it

- **WHEN** the reader clicks a due review card
- **THEN** the doc's full text opens in the preview pane, the pane is scrolled into view, and the card remains due (its stage is unchanged)

#### Scenario: nothing due drops the cards but keeps the panel

- **WHEN** no doc is due
- **THEN** the section renders its panel and header with the "nothing due" message in place of the subtitle, followed by the summary-and-chart strip, and renders no cards

## ADDED Requirements

### Requirement: Retention histogram of the enrolled collection

The review section SHALL render a histogram of every enrolled doc's position on the curve, with
one bin per Ebbinghaus stage — labelled by the interval that stage waits on (`1d`, `3d`, `7d`,
`15d`, `30d`, `60d`, `120d`) — plus one terminal bin for docs past the final stage
(`next_due_at IS NULL`).

Bins SHALL be derived from the stored `stage` column and the presence of `next_due_at`, not
recomputed from `captured_at` and the current date: the stage advance already fast-forwards in
SQL, and re-deriving the position on the dashboard would put that rule in two places.

Each bar SHALL show the bin's total and SHALL split it into the portion already due and the
portion still scheduled, using the same radar-timezone day boundary that decides which cards are
due, so a doc counted as due in the chart is a doc that can appear as a card. Each bin's exact
total and due count SHALL be recoverable without measuring bar height or distinguishing opacity —
by a per-bar tooltip that needs no JavaScript.

The terminal bin SHALL be rendered in a colour outside the stage ramp, since those docs are
neither decaying nor scheduled.

Because the due/scheduled split is carried by an opacity difference within one bar, the chart
SHALL label that encoding with a visible key. A reader MUST NOT have to hover, or infer from
context, to learn which part of a bar is due.

#### Scenario: bins reflect the stored stage

- **WHEN** the collection holds docs at stages 0, 3, and 3, and one doc whose `next_due_at` is `NULL`
- **THEN** the histogram shows 1 in the `1d` bin, 2 in the `15d` bin, 1 in the terminal bin, and 0 elsewhere

#### Scenario: due and scheduled are distinguished within a bin

- **WHEN** a bin holds 9 docs of which 2 are due today
- **THEN** that bar renders 2 as due and 7 as scheduled, and reports both numbers

#### Scenario: exact counts do not depend on bar height

- **WHEN** one bin dominates the distribution and the others render as short bars
- **THEN** every bin still reports its total and due count on hover, without JavaScript

#### Scenario: the split is legible without interaction

- **WHEN** the reader first sees the chart, without hovering anything
- **THEN** a key states which shade means due and which means scheduled

#### Scenario: the collapsed variant needs no key

- **WHEN** the compact variant renders on the collapsed line
- **THEN** no bar is split (nothing is due in that state) and no key is shown

#### Scenario: due in the chart matches due in the cards

- **WHEN** the section renders
- **THEN** the total counted as due across all bins equals the due total reported by the section's card list

### Requirement: Histogram placement and its frame

The histogram SHALL sit at the trailing edge of a strip below the section header, in a
fixed-width slot, so the eight bins do not degrade into slivers as header text or locale length
varies.

Its seating SHALL mirror how the radar tracker seats its score histogram — same slot width, same
trailing alignment, same bar geometry and label treatment — so the two pages read as one system.

The chart's frame — its title, its full axis, and its key — SHALL render in every state,
including with nothing due and with nothing enrolled. The chart MUST NOT be omitted, and MUST NOT
shed labels, when it has little or nothing to plot: bars without an axis are an unexplained
shape, and a chart that disappears moves the content beneath it.

The title SHALL name the Ebbinghaus curve outright rather than describing it generically. The
schedule is the section's whole premise, and a reader who does not already know what the bars
measure gets no second chance to learn it.

The strip's leading edge SHALL carry a summary of the same distribution — how many docs are
enrolled, how many are due, how many are scheduled, how many are past the final stage, and the
stage the median doc is waiting on — laid out as the radar tracker lays out its stat pills, so
the two strips read alike. Every figure SHALL derive from the same bins the chart plots, with no
additional query.

#### Scenario: the title names the curve

- **WHEN** the chart renders in either locale
- **THEN** its title names the Ebbinghaus curve

#### Scenario: the summary agrees with the bars

- **WHEN** the strip renders
- **THEN** the enrolled figure equals the sum of every bin, the due figure equals the sum of every bin's due portion, and the terminal-stage figure equals the terminal bin

#### Scenario: seating matches the radar tracker

- **WHEN** a reviewer compares the review section with the radar tracker card
- **THEN** both histograms occupy a fixed-width slot of the same width at the trailing edge of a strip below their card's header, with the same bar height, bar spacing, corner radius, and label placement

#### Scenario: the frame survives an empty chart

- **WHEN** no doc is enrolled
- **THEN** the chart still renders its title, all eight axis labels, and its key, with no bars — and occupies the same space it will once docs enroll

When nothing is due, the section SHALL still render the chart in the same trailing strip of the
same panel. It SHALL NOT shrink the chart to a variant without its axis and key, and SHALL NOT
drop the panel around it: the strip is the section's constant, and framing it in one state but
not the other reads as two different components rather than one with less to say.

#### Scenario: populated state seats the chart below the header

- **WHEN** docs are due
- **THEN** the histogram renders flush with the trailing edge of the strip below the section header, above the due cards

#### Scenario: nothing due keeps the full chart

- **WHEN** no doc is due but docs are enrolled
- **THEN** the section renders the chart with its title, axis, and key in the same trailing strip of the same panel, dropping only the cards

#### Scenario: the chart is seated identically in both states

- **WHEN** the reader compares the section with docs due against the section with nothing due
- **THEN** the chart occupies the same slot width and trailing alignment in both, so it does not shift as docs fall due

### Requirement: The histogram is read-only and adds no round trip

The histogram's data SHALL be fetched in the same server render pass as the due cards, and MUST
NOT be derived from the capped due-card list. Rendering the histogram MUST NOT write review
state.

#### Scenario: distribution is not derived from the capped card list

- **WHEN** 17 docs are due and the section caps display at 5 cards
- **THEN** the histogram still reflects all enrolled docs, not only the 5 rendered

#### Scenario: rendering the histogram writes nothing

- **WHEN** the `/knowledge` page is rendered or prefetched
- **THEN** no review row is inserted, advanced, or retired
