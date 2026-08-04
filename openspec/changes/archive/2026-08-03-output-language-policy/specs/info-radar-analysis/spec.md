## MODIFIED Requirements

### Requirement: Tier-2 prose fields follow the configured output language

The `title`, `summary`, and `impact` fields returned by `radar_tier2_impact` SHALL be written in the configured output language, independent of the language of `goals`, the article body, and the source's original title. The prompt's own language rule SHALL be phrased unconditionally, so an agent built without rule injection still behaves correctly.

`title` is a new field: previously the dashboard displayed the source's untouched original title (`radar_items.title`) alongside a translated `summary`/`impact`, which produced visibly inconsistent language on the same card. `radar_tier2_impact` now rewrites the title into the same target language as the other two fields, using the source title (already available as prompt input) as its basis.

The previously shipped conditional phrasing ("match the language of `goals`") SHALL remain removed, per the prior measurement (English `summary` in 64/64 replays and 13/13 real production rows against Chinese goals, while `impact` stayed Chinese in the same responses).

`tags` remain lowercase kebab-case English and are unaffected.

#### Scenario: English article under a Chinese target

- **WHEN** the configured output language is `zh`, the goals are Chinese, and the fetched article body is English
- **THEN** `title`, `summary`, and `impact` are all written in Chinese, with proper nouns kept in their original form

#### Scenario: Chinese article under an English target

- **WHEN** the configured output language is `en`, the goals are Chinese, and the fetched article body is Chinese
- **THEN** `title`, `summary`, and `impact` are all written in English

#### Scenario: title is consistent with summary and impact

- **WHEN** any item completes tier-2 analysis
- **THEN** `title`, `summary`, and `impact` are all in the same resolved language — none of the three is left in the source's original language while the others are translated

#### Scenario: tier-1 reason follows the same language

- **WHEN** a tier-1 verdict is produced under a configured output language
- **THEN** the one-sentence `reason` is written in that language, while the English goal identifiers it cites remain unchanged

### Requirement: Downstream radar agents do not re-derive language from their input

`radar_recap` SHALL take its output language from the configured `global` setting rather than from the language of the summaries it is given, which previously made its language a side effect of whatever tier-2 happened to emit.

`radar_dedup_judge` is explicitly exempt from this requirement: its `reason` field is neither stored for display nor rendered anywhere in the dashboard, so it has no language contract to honor. (This corrects a prior version of this requirement, which incorrectly stated that `radar_dedup_judge` follows the configured language — the shipped prompt and config have always exempted it; only the spec text was out of date.)

#### Scenario: recap over mixed-language summaries

- **WHEN** a recap covers a period whose stored summaries are a mix of languages
- **THEN** the headline, theme titles, and narratives are all written in the configured output language

#### Scenario: dedup judge is unconstrained

- **WHEN** `radar_dedup_judge` evaluates a candidate pair whose stored summaries are in different languages
- **THEN** its `reason` field's language is not required to match the configured output language, the source summaries, or anything else
