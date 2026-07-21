## ADDED Requirements

### Requirement: Locale-aware instructions selection

The loader SHALL accept an optional `locale` on `build_from_name(name, locale=...)` (defaulting to the base prompt-file locale `zh` — the language of the unsuffixed `instructions_file`, distinct from the pipeline's runtime default) that selects a per-locale instructions file for the same single agent config. The config's model profile, tools, and `extra` behavior knobs SHALL remain single-source across locales — only the resolved instructions text varies. Resolution SHALL use a naming convention over the config's `instructions_file`: the declared path is the base (default-locale) prompt, and a non-default locale resolves to the same path with a `.<locale>` segment inserted before the extension (e.g. `agents/radar_tier2_impact.md` → `agents/radar_tier2_impact.en.md`). If the locale-specific file does not exist, the loader SHALL fall back to the base file and log the fallback rather than raising.

#### Scenario: locale selects the variant prompt

- **WHEN** `build_from_name("radar_tier2_impact", locale="en")` is called and `prompts/agents/radar_tier2_impact.en.md` exists
- **THEN** the agent's instructions are read from the `.en` variant while model profile, tools, and `extra` come from the single `radar_tier2_impact.yaml`

#### Scenario: default locale uses the base prompt

- **WHEN** `build_from_name("radar_tier2_impact")` is called with no locale
- **THEN** the loader reads the base `prompts/agents/radar_tier2_impact.md`

#### Scenario: missing variant falls back to base

- **WHEN** `build_from_name("some_agent", locale="en")` is called but no `.en` variant file exists
- **THEN** the loader reads the base instructions file and logs that it fell back, without raising
