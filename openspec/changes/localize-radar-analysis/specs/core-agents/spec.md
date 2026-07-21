## ADDED Requirements

### Requirement: Locale-aware instructions selection

The loader SHALL accept an optional `locale` on `build_from_name(name, locale=...)` (defaulting to the system default locale `en`) that selects a per-locale instructions file for the same single agent config. The config's model profile, tools, and `extra` behavior knobs SHALL remain single-source across locales — only the resolved instructions text varies. Resolution SHALL use a naming convention over the config's `instructions_file`: given the declared stem path, the loader SHALL first look for the sibling `<stem>.<locale><ext>` variant and use it when present; otherwise it SHALL fall back to the unsuffixed `<stem><ext>` base file; if neither exists it SHALL raise. Multi-language agents therefore ship one suffixed file per locale (e.g. `radar_tier2_impact.zh.md` and `radar_tier2_impact.en.md`) with no unsuffixed base on disk, while single-language agents ship only the unsuffixed base (e.g. `knowledge_classifier.md`), which every locale falls back to. The `instructions_file` field names the logical base stem regardless of whether an unsuffixed file physically exists.

#### Scenario: locale selects the variant prompt

- **WHEN** `build_from_name("radar_tier2_impact", locale="en")` is called and `prompts/agents/radar_tier2_impact.en.md` exists
- **THEN** the agent's instructions are read from the `.en.md` variant while model profile, tools, and `extra` come from the single `radar_tier2_impact.yaml`

#### Scenario: each locale resolves its own suffixed file

- **WHEN** `build_from_name("radar_tier2_impact", locale="zh")` is called
- **THEN** the loader reads `prompts/agents/radar_tier2_impact.zh.md` (there is no unsuffixed `radar_tier2_impact.md` on disk)

#### Scenario: single-language agent falls back to the unsuffixed base

- **WHEN** `build_from_name("knowledge_classifier", locale="en")` is called and only the unsuffixed `prompts/agents/knowledge_classifier.md` exists
- **THEN** the loader reads that base file

#### Scenario: neither variant nor base exists

- **WHEN** an agent's `instructions_file` resolves to no `<stem>.<locale><ext>` variant and no unsuffixed `<stem><ext>` base
- **THEN** the loader raises rather than returning empty instructions
