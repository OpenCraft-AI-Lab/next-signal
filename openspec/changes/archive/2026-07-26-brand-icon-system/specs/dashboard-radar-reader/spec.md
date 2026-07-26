## MODIFIED Requirements

### Requirement: Radar index page

The dashboard SHALL render `/radar` showing analyzed `radar_items` grouped by `analyzed_at::date`, with today's group expanded by default and prior days collapsed. The page hero SHALL render `<RadarEmblem />` (from foundation's `dashboard/components/brand/radar-mark.tsx`) alongside the page title and a "N kept" subtitle.

#### Scenario: today's items appear at the top

- **WHEN** the operator visits `/radar`
- **THEN** the page renders a section labelled with today's calendar date containing every `radar_analyses` row where `analyzed_at::date = today` and `verdict = 'keep'`, ordered per the current sort param

#### Scenario: past days are grouped and collapsed

- **WHEN** the operator visits `/radar`
- **THEN** prior calendar days appear as collapsed sections below today's section, each showing the day, the kept-count, and the median score, expandable to reveal the items

#### Scenario: drop verdicts are filtered out of the reading view

- **WHEN** the operator visits `/radar`
- **THEN** rows where `verdict = 'drop'` are NOT shown in either today's section or any past-day section — they only contribute to the tracker counters

#### Scenario: the hero emblem is the radar mark

- **WHEN** the operator visits `/radar`
- **THEN** the hero renders the 72px `RadarEmblem` with its sweep running, and no alpaca mark appears anywhere on the page
