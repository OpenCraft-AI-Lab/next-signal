## ADDED Requirements

### Requirement: Recap range selector

The radar index page SHALL offer a recap range selector with two rolling presets — last 7 days and last 30 days, both ending on the current local radar day — plus a custom `from`–`to` date pair. Presets SHALL be rolling windows rather than calendar periods, so their meaning does not depend on a locale-specific week start. The selected range SHALL be reflected in the URL query string so a recap view is linkable and survives reload. The recap request SHALL inherit the filter bar's current score threshold and novel-only setting as its quality gate, so the recap and the item list it summarizes describe the same population. The recap section SHALL be titled "Smart Recap" and SHALL sit above the "today's high-signal items" heading and its filter bar, since the recap is a synthesis over the items rather than one of them.

#### Scenario: recap section precedes the item list

- **WHEN** the radar index page renders outside export mode
- **THEN** the "Smart Recap" section appears above the filter bar and the item list

### Requirement: Smart Recap section is collapsible with a persisted preference

The Smart Recap section SHALL be collapsible from its header. The collapsed/expanded choice SHALL persist across navigation and reload — including the full re-render a filter change triggers — rather than resetting each time. Opening a specific saved recap SHALL present it expanded even when the reader's stored preference is collapsed, so a reopened recap is never hidden behind a collapsed header.

#### Scenario: collapse survives a filter change

- **WHEN** the reader collapses the Smart Recap section and then changes the score filter
- **THEN** the page re-renders with the section still collapsed

#### Scenario: reopening a saved recap shows it expanded

- **WHEN** the reader has the section collapsed and selects a recap from the saved list
- **THEN** the section renders expanded with that recap's content

#### Scenario: preset selects a rolling window

- **WHEN** the reader picks the last-7-days preset on local day 2026-07-20
- **THEN** the recap range resolves to `since` = 2026-07-14 and `until` = 2026-07-20, and the range appears in the URL

#### Scenario: quality gate follows the filter bar

- **WHEN** the reader has a minimum score of 70 and novel-only active, then requests a recap
- **THEN** the recap is requested with `min_score=70` and `novel_only=true`, keyed separately from the same range at the default gate

### Requirement: Recap panel renders themes with citations

When a recap exists for the selected range and gate, the radar index page SHALL render its headline and each theme's title and narrative, with each theme's citations shown as links to the corresponding radar detail pages. A citation whose `radar_items` row no longer exists SHALL render as plain text rather than a broken link. When the stored `considered_count` exceeds `item_count`, the panel SHALL state that the recap covers a subset (for example, "synthesized from the top 60 of 143 signals") rather than implying full coverage. All recap chrome SHALL be omitted in `?export=1` print mode unless and until export support is specified.

#### Scenario: themes render with working citations

- **WHEN** a `done` recap with three themes is displayed
- **THEN** each theme shows its title, narrative, and citation links that navigate to the cited items' detail pages

#### Scenario: capped recap states its coverage

- **WHEN** the displayed recap stores `item_count=60` and `considered_count=143`
- **THEN** the panel states that it covers 60 of 143 signals

#### Scenario: citation to a swept item degrades gracefully

- **WHEN** a displayed recap cites an item whose `radar_items` row has been removed by the 30-day sweep
- **THEN** that citation renders as plain non-clickable text and the rest of the panel is unaffected

### Requirement: Recap generation is spawn-and-poll, with visible status

Triggering a recap SHALL spawn the CLI detached through the shared `spawnPacaDetached` launcher and return immediately — the request path MUST NOT block on inference, which takes 30–60s locally. The page SHALL then poll the recap row for the selected key and render according to `status`: `'running'` shows an in-progress state, `'done'` renders the panel, `'error'` surfaces the failure message. A recap that ends in `'error'` after a regeneration SHALL still display its previously stored content alongside the error. Triggering while the key is already `'running'` SHALL NOT start a second generation.

#### Scenario: trigger returns immediately

- **WHEN** the reader triggers a recap
- **THEN** the server action spawns `paca info-radar recap` detached and returns a started response without waiting for completion

#### Scenario: poll surfaces a failure instead of hanging

- **WHEN** a recap generation ends with `status='error'`
- **THEN** the panel stops polling and displays the stored error message

#### Scenario: failed regeneration still shows the prior recap

- **WHEN** a regeneration of an existing `done` recap ends in `'error'`
- **THEN** the panel shows the previously stored headline and themes together with the error indication

### Requirement: Stale recaps are labelled, never silently regenerated

When further analyses have landed in the recap's range and gate since its `max_analyzed_at`, the panel SHALL display the cached recap together with an explicit staleness marker naming the number of newer signals, next to the regenerate control. The page MUST NOT auto-regenerate a stale recap on load — doing so would make every visit to a live range trigger a minute of inference.

#### Scenario: live range shows a staleness marker

- **WHEN** a last-7-days recap was generated and 5 further items in that range have since been analyzed
- **THEN** the panel renders the stored recap plus a marker reporting 5 newer signals, and no generation starts automatically

#### Scenario: settled range shows no marker

- **WHEN** the displayed recap's range and gate have had no analyses since `max_analyzed_at`
- **THEN** no staleness marker is shown

### Requirement: Previously-generated recaps are browsable

The radar index page SHALL list previously-generated (`done`) recaps in the past-days area, each showing its date range, item count, and headline, ordered by range newest-first. Selecting one SHALL reopen it in the recap section above without generating anything. Because a recap's identity includes its quality gate, the link SHALL carry the stored `min_score` and `novel_only` as well as the range; since those are the same parameters the filter bar uses, opening a past recap MAY also re-scope the item list to that gate, keeping the recap and the items consistent. The list SHALL be omitted in `?export=1` print mode.

#### Scenario: reopening a saved recap makes no LLM call

- **WHEN** the reader selects a recap from the saved list
- **THEN** the page navigates to that recap's range and gate, the recap section renders the stored content, and no generation is triggered

#### Scenario: saved list reflects the recap's own gate

- **WHEN** a saved recap was generated with `min_score=70` and `novel_only=true`
- **THEN** its list entry links with those parameters so the reopened recap resolves the same stored row
