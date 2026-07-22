## ADDED Requirements

### Requirement: Knowledge preview localizes chrome by the item's stored locale

The `/knowledge` preview SHALL localize an artifact's chrome by the artifact's own recorded `locale` frontmatter field (NOT the `paca_locale` UI cookie), so each item renders as a self-consistent whole. Specifically the preview SHALL:

- render frontmatter **key** labels (`title`, `source_type`, `status`, `freshness`, `source_url`, `published`, `author`, …) via a static key→label map keyed by the item locale, while leaving the stored YAML keys unchanged;
- render enum-valued frontmatter **values** (`status`, `freshness`, `source_type`, `converter`) via a static value→label map keyed by the item locale, while leaving non-enum values (dates, URLs, digest) raw;
- swap the auto-generated `## Summary` and `## Related` body headings to the item locale at render (in `MarkdownText`);
- render `source_url` / `published` / `author` as labelled rows using the localized provenance labels;
- render each tag chip using its `knowledge_tag_labels` display label for the item locale, falling back to the English tag key when no label row exists;
- show the localized `title` while keeping `source_title` available for reference.

When an artifact has no `locale` field (legacy), the preview SHALL fall back to the UI locale. The `paca_locale` cookie continues to drive only the app shell and the locale stamped on new ingests; toggling it SHALL NOT change how an already-ingested item renders.

#### Scenario: a zh-stamped item renders fully Chinese under an English UI

- **WHEN** the UI cookie is `en` and the operator opens an artifact whose frontmatter `locale` is `zh`
- **THEN** its frontmatter key labels, enum value labels, `## Summary` / `## Related` headings, provenance labels, tag chips, and title all render in Chinese, and the Chinese summary prose is shown — no English labels over Chinese content

#### Scenario: enum values are localized but stored tokens are unchanged

- **WHEN** an item with `status: clean`, `freshness: evolving`, `source_type: markitdown` renders under `locale: zh`
- **THEN** the panel shows localized Chinese labels for those values, while the underlying `.md` frontmatter still stores the English tokens `clean` / `evolving` / `markitdown`

#### Scenario: tag chip uses the display label with key fallback

- **WHEN** a tag `multimodal` has a `zh` label in `knowledge_tag_labels` and a tag `deepseek` does not
- **THEN** rendering a `zh`-locale item shows the localized label for `multimodal` and falls back to the `deepseek` key

#### Scenario: headings swap without a stored change

- **WHEN** a `zh`-locale artifact whose stored `.md` contains canonical `## Summary` and `## Related` headings is previewed
- **THEN** the preview displays the Chinese equivalents of those headings while the stored file keeps the English headings

#### Scenario: UI toggle does not retranslate an item

- **WHEN** the operator toggles the UI language while viewing a `zh`-stamped item
- **THEN** the item continues to render in Chinese (its stored locale); only the surrounding app shell changes language
