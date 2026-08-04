## Why

The nav's language picker currently does two unrelated jobs in one click: it swaps
the UI dictionaries *and* rewrites `~/.next-signal/language.json`, the preference
every pipeline agent's `global` policy reads. That coupling shipped as a deliberate
simplification ("the same control, not two independent settings"), but it means a
user who only wants to read the interface in Chinese silently redirects every
future radar analysis into Chinese — an expensive, invisible side effect of a
chrome-level choice, and one they cannot decline without also giving up the UI
language they wanted.

Second, wiki frontmatter is on the wrong side of the line. `title` and `summary`
follow the *article's* detected language, so a reader who has set their content
language to English still gets Chinese titles and summaries in their own knowledge
index. Frontmatter is prose written **for the reader**, not preserved source text —
it belongs with the setting, the same as radar summaries.

## What Changes

- **New settings popover.** A gear button joins `nav-tools`, opening a Radix
  Popover panel. The content-language control lives there, labelled as what it
  governs (pipeline output), separate from the UI-chrome picker beside it. No new
  route; built from the existing design-system primitives and tokens.
- **`LanguageToggle` narrows to UI chrome only.** Its `onValueChange` drops the
  fire-and-forget `setContentLanguage` call and writes only the `paca_locale`
  cookie. The two settings become genuinely independent and may disagree — that
  is now the point, not a drift bug.
- **`knowledge_frontmatter` and `knowledge_github_summary` move from
  `same_as_source` to `global`.** Wiki `title`/`summary` follow the content-language
  setting instead of the source article. **BREAKING** for the knowledge pipeline's
  observable output: newly ingested docs produce frontmatter in the configured
  language rather than the source's. Already-written wiki files are untouched —
  `reindex_wiki` only re-embeds existing markdown into GBrain and never re-runs the
  frontmatter agent — so a library ingested under the old behavior stays as it is
  unless a source is ingested again.
- **Body cleaners stay `same_as_source`.** `knowledge_artifact_editor` and
  `knowledge_github_cleaner` emit the article body itself; translating it would
  destroy the only copy of the source text the wiki holds. `detect_language` and
  the per-item detection thread therefore stay, now serving two agents instead of
  four.
- **The container-start seed hook stays.** It still creates the preference file
  from `DEFAULT_LOCALE` when absent; it just is no longer the locale picker's
  downstream partner.

## Capabilities

### New Capabilities

None. The settings panel is a surface for an existing capability, specified under
`dashboard-shell` alongside the other nav-level controls.

### Modified Capabilities

- `dashboard-shell`: the "Bilingual UI via a locale cookie" requirement drops the
  clause making the locale picker drive `content_language`, and a new requirement
  covers the settings popover that owns that control instead.
- `core-output-language`: the requirement asserting frontmatter agents use
  `same_as_source` narrows to the two body-cleaning agents; the `global` policy's
  description of who writes the preference file changes from the locale picker to
  the settings panel.
- `knowledge-pipeline`: "Frontmatter prose fields follow the configured output
  language" inverts — `title`/`summary` resolve `global`, not the detected source
  language. Detection narrows to the body-cleaning step alone.

## Impact

- **Dashboard**: `components/nav.tsx`, `components/language-toggle.tsx`, a new
  settings-panel component, `lib/i18n/dictionaries.ts` (both locales), and possibly
  a `Popover` primitive under `components/ui/` if one does not already exist. A
  server action must read the current `content_language` so the panel can render
  its active value — `lib/actions/language.ts` grows a getter beside its writer.
- **Agent configs**: `configs/agents/knowledge_frontmatter.yaml`,
  `configs/agents/knowledge_github_summary.yaml` (policy + rationale comments).
- **Prompts**: both agents already carry `{{OUTPUT_LANGUAGE}}`, so their text needs
  only the surrounding rationale checked, not restructured.
- **Pipeline code**: `stages/knowledge_ingest/artifact_editor.py::write_frontmatter`
  stops passing `language=`; `fetch.py`'s detection and
  `KnowledgeArtifact.detected_language` remain for the cleaners.
- **Tests**: `tests/test_agent_loader.py`, `tests/test_knowledge_artifact_editor.py`,
  and the language tests covering which agents resolve which policy.
- **Docs (bilingual, same change)**: `docs/modules/core.md`,
  `docs/modules/knowledge.md`, and their `docs/zh/` mirrors.
- **No database, CLI, or migration impact.** `paca doctor`'s content-language check
  reads the same file and needs no change.
