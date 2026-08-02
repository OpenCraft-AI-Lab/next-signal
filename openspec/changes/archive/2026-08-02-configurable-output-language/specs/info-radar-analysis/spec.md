## ADDED Requirements

### Requirement: Tier-2 prose fields follow the configured output language

The `summary` and `impact` fields returned by `radar_tier2_impact` SHALL be
written in the configured output language, independent of the language of
`goals` and independent of the language of the article body. The prompt's own
language rule SHALL be phrased unconditionally, so an agent built without rule
injection still behaves correctly.

The previously shipped conditional phrasing ("match the language of `goals`")
SHALL be removed. It was measured to produce an English `summary` in 64/64
replays and 13/13 real production rows against Chinese goals, while `impact`
stayed Chinese in the very same responses.

`tags` remain lowercase kebab-case English and are unaffected.

#### Scenario: English article under a Chinese target

- **WHEN** `SIGNAL_OUTPUT_LANG=zh`, the goals are Chinese, and the fetched article body is English
- **THEN** both `summary` and `impact` are written in Chinese, with proper nouns kept in their original form

#### Scenario: Chinese article under an English target

- **WHEN** `SIGNAL_OUTPUT_LANG=en`, the goals are Chinese, and the fetched article body is Chinese
- **THEN** both `summary` and `impact` are written in English

#### Scenario: tier-1 reason follows the same language

- **WHEN** a tier-1 verdict is produced under a configured output language
- **THEN** the one-sentence `reason` is written in that language, while the English goal identifiers it cites remain unchanged

### Requirement: Downstream radar agents do not re-derive language from their input

`radar_recap` and `radar_dedup_judge` SHALL take their output language from the
configured setting rather than from the language of the summaries they are given.
Both previously inherited it from their input, which made their language a
side effect of whatever tier-2 happened to emit.

#### Scenario: recap over mixed-language summaries

- **WHEN** a recap covers a period whose stored summaries are a mix of languages
- **THEN** the headline, theme titles, and narratives are all written in the configured output language
