# dashboard-knowledge-review Specification

## Purpose

The delivery surface for the knowledge-review schedule: a section at the top of `/knowledge`, above the ingest form, showing the documents currently due. Each due doc renders as a card carrying its title, capture date, position on the curve, and the doc's own frontmatter `summary`; clicking the card opens that doc's full text in the page's existing preview pane and scrolls to it, so a review is a re-read of the source rather than only a reminder. Reading and dismissing are deliberately distinct — opening a card never advances the curve, while a separate "seen" control is a POST server action that does. The section caps at five cards and always states the remainder rather than silently truncating, and collapses to a single line when nothing is due. The dashboard never writes review state during render: enrollment happens only through a refresh control that spawns the reconcile CLI detached.

## Requirements
### Requirement: Review section on the knowledge page

The `/knowledge` page SHALL render a review section above the ingest form showing the documents currently due, each as a card with the doc's title, its capture date, which review this is (stage position), and the doc's frontmatter `summary`. A card's body SHALL open that doc's full-text preview in the same page's preview pane and bring the pane into view (an in-page anchor), so a review card re-reads the source rather than only reminding the reader it is due. Opening a card MUST NOT advance its stage — reading and the "seen" acknowledgement are distinct. When nothing is due, the section SHALL collapse to a single unobtrusive line rather than occupying the top of the page with an empty panel.

#### Scenario: due cards render with the doc summary

- **WHEN** three docs are due
- **THEN** the section renders three cards, each showing title, capture date, review position, and the doc's summary

#### Scenario: clicking a card opens the full text without dismissing it

- **WHEN** the reader clicks a due review card
- **THEN** the doc's full text opens in the preview pane, the pane is scrolled into view, and the card remains due (its stage is unchanged)

#### Scenario: nothing due collapses the section

- **WHEN** no doc is due
- **THEN** the section renders a single line and does not push the ingest form down the page

### Requirement: Display cap of five cards with an explicit remainder

The section SHALL render at most 5 due cards, ordered longest-overdue first, and SHALL state how many further docs are due beyond those shown. The remainder MUST NOT be silently omitted.

#### Scenario: overflow states the remainder

- **WHEN** 17 docs are due
- **THEN** 5 cards render and the section reports that 12 more are due

### Requirement: Marking a card seen is a POST action

The "seen" control SHALL be a POST server action that advances the doc's review stage and revalidates the page. It MUST NOT be a GET link or a GET query parameter — a prefetch or a crawler following a GET would silently advance the curve.

#### Scenario: seen advances the stage and refreshes

- **WHEN** the reader marks a due card seen
- **THEN** a POST server action advances that doc's stage, the card leaves the due list, and the section re-renders without a full page navigation

#### Scenario: stage advance is not reachable by GET

- **WHEN** the page is rendered or prefetched
- **THEN** no review stage is advanced

### Requirement: Refresh spawns reconciliation detached

The section SHALL offer a refresh control that spawns `paca knowledge review` through the shared `spawnPacaDetached` launcher and returns immediately. The dashboard MUST NOT write review state during page render — enrollment happens only through this spawned command.

#### Scenario: refresh returns without waiting

- **WHEN** the reader triggers refresh
- **THEN** the server action spawns the CLI detached and returns a started response rather than waiting for reconciliation to finish

#### Scenario: rendering the page enrolls nothing

- **WHEN** the `/knowledge` page is rendered while the wiki contains docs with no review row
- **THEN** no rows are inserted as a side effect of rendering

### Requirement: Review section strings are bilingual

All review section interface text SHALL be added to `dashboard/lib/i18n/dictionaries.ts` in both locales with English canonical. Document titles, tags, and summaries SHALL render as-is without translation, consistent with how the dashboard already treats article titles and analysis summaries.

#### Scenario: section renders in both locales

- **WHEN** the reader switches locale using the nav language control
- **THEN** the review section's labels and controls render in the selected locale while doc titles and summaries remain in their original language
