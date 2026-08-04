## 1. Popover primitive

- [x] 1.1 Add `@radix-ui/react-popover` to `dashboard/package.json` and install. (Via `pnpm add` — the dashboard is a pnpm workspace; `npm install` fails on a pre-existing `knip` peer conflict.)
- [x] 1.2 Create `dashboard/components/ui/popover.tsx` exporting `Popover`, `PopoverTrigger`, `PopoverContent`, styled to the existing design tokens and matching the menu surface the `Select` content already uses (`bg-elevated`, `rounded-lg`, `shadow-menu`, the same open/close animation classes).
- [x] 1.3 Register the primitive on `/design` (`dashboard/app/design/page.tsx`) alongside the other `components/ui` entries, per the standing rule that a new primitive lands in the catalogue in the same change.

## 2. Content-language plumbing (`dashboard/lib/actions/language.ts`)

- [x] 2.1 Add `getContentLanguage(): Promise<Locale>` reading `languageStateFile()`: returns the file's `content_language` when recognized; falls back to `DEFAULT_LOCALE` and `console.error`s on a missing, unreadable, corrupt, or unrecognized value (deliberate asymmetry with `paca.core.language`, which raises — see design.md D3).
- [x] 2.2 Leave `setContentLanguage` and `ensureContentLanguage` as they are; only the caller changes.

## 3. Settings panel

- [x] 3.1 Create `dashboard/components/settings-panel.tsx`: a gear-icon trigger opening a `Popover` whose body holds the content-language control, with self-labelled language names (`English` / `中文`) and the active value marked.
- [x] 3.2 Label the control by what it governs — generated content (radar analyses, wiki frontmatter) — not "language", so it reads as distinct from the adjacent UI-locale picker. Add a short helper line stating it does not affect the interface language.
- [x] 3.3 Accept the current value as a prop rather than fetching on open, so the panel paints its active state on first render.
- [x] 3.4 Wire the change handler to `setContentLanguage`; surface a failed write via `toast.error` and revert the optimistic value; do not touch the `paca_locale` cookie.
- [x] 3.5 Add `settings.*` keys to both dictionaries in `dashboard/lib/i18n/dictionaries.ts` (English and Chinese). Also relabelled `language.label` to "Interface language" / "界面语言" so the two controls read as distinct.

## 4. Nav + layout wiring

- [x] 4.1 `dashboard/app/layout.tsx`: `await getContentLanguage()` beside the existing `getLocale()` call (via `Promise.all`) and pass it to `<Nav />`.
- [x] 4.2 `dashboard/components/nav.tsx`: accept `contentLanguage` and render `<SettingsPanel>` in `nav-tools`, next to `LanguageToggle` / `ThemeToggle`.

## 5. `LanguageToggle` narrows to UI chrome

- [x] 5.1 Remove the `setContentLanguage` import and the fire-and-forget call from `onValueChange`; it writes only the `paca_locale` cookie and refreshes.
- [x] 5.2 Replace the "deliberately the same control" comment with one stating the opposite invariant: this picker is UI chrome only, and the content language is owned by the settings panel.

## 6. Agent policy flip

- [x] 6.1 `configs/agents/knowledge_frontmatter.yaml`: `output_language: same_as_source` → `global`; rationale comment rewritten (index entry written for the reader, not preserved source text).
- [x] 6.2 `configs/agents/knowledge_github_summary.yaml`: same flip, same rationale.
- [x] 6.3 Verified both prompts' `{{OUTPUT_LANGUAGE}}` sentences read correctly under `global`; wording left byte-identical — no measured phrasing shifted.
- [x] 6.4 Fixed `scripts/lang_probe.py`, which the flip broke: it built `knowledge_frontmatter` with a `same_as_source` per-call override and only patched `global_language` for the radar path, so a `--agent frontmatter` run would have hit the harness's own `ABORT: … instructions never name …` guard. Both probed agent sets now resolve `global` through one patched `global_language`; dropped the orphaned `language=` parameter from the two helpers and noted in the docstring that the `same_as_source` cleaners need a different fixture.

## 7. Pipeline wiring

- [x] 7.1 `stages/knowledge_ingest/artifact_editor.py::write_frontmatter`: dropped the `language=artifact.detected_language` argument; docstring now says the frontmatter step resolves `global`.
- [x] 7.2 Left `_run_editor`'s `language=` override, `fetch()`'s detection call, and `KnowledgeArtifact.detected_language` untouched — the cleaners are still the consumers.

## 8. Tests

- [x] 8.1 `tests/test_knowledge_artifact_editor.py`: renamed and inverted the frontmatter case — it now asserts the agent is built with `language=None`.
- [x] 8.2 Checked `tests/test_agent_loader.py` / `tests/test_language.py`: their `same_as_source` cases use synthetic configs, not the shipped agents, so none needed changing.
- [x] 8.3 Added `test_ingest_agents_split_between_source_and_setting` — parametrized over the four shipped ingest agents, loading the real YAML: under a `zh` override and an `en` preference, the cleaners resolve Chinese and the frontmatter agents English. Locks the split against an accidental policy flip.
- [x] 8.4 `uv run pytest -q` → 406 passed, 14 skipped (402 before the schema-contract tests in 11.5).

## 9. Docs (bilingual — both languages in this change)

- [x] 9.1 `docs/modules/core.md` + `docs/zh/modules/core.md`: policy list updated (frontmatter → `global`, only the two cleaners on `same_as_source`), the "what the output is, not which module" dividing line, the bilingual-file consequence, and the dashboard/pipeline failure-mode asymmetry.
- [x] 9.2 `docs/modules/knowledge.md` + `docs/zh/modules/knowledge.md`: replaced the prose with a per-step policy table, restated the archive/index split, and rewrote the re-index hazard note (see 10.5). Also corrected the "Measured" caveat, which claimed the numbers came from a superseded mechanism — that mechanism is the one now in force again, so the numbers apply directly.
- [x] 9.3 `docs/operations.md` + `docs/zh/operations.md`: the preference file is written by the settings panel, not the locale toggle; the two settings are independent.
- [x] 9.4 `CLAUDE.md`: rewrote the output-language paragraph around the same dividing line.
- [x] 9.5 (added) `dashboard/README.md` + `README.zh-CN.md`: new "Content language" section beside the existing "UI language" one.

## 10. Verification

- [x] 10.1 `docker compose build dashboard` + `up -d dashboard`. The registry was unreachable for ~40 min (`DeadlineExceeded` on base-image metadata for `oven/bun:1`, `ghcr.io/astral-sh/uv`, `python:3.11-slim-bookworm`), so the first pass used the docker-verify skill's hot-patch escape hatch. Once it recovered, built clean (exit 0) and recreated: image id `8f5852a9b184` == container image id. Everything below was then re-verified against the real image, not the hot patch.
- [x] 10.1a Image content confirmed: `@radix-ui/react-popover` present in `/app/dashboard/node_modules`, `paca.core.language` importable, both frontmatter YAMLs read `output_language: global`.
- [x] 10.2 Visual check: settings panel opens, shows the persisted value on first paint, both controls sit correctly in the nav, verified in dark and light, and the `/design` Popover entry opens.
- [x] 10.3 Confirmed selecting a content language writes `/state/language.json` (`content_language` + `updated_at` change) and that switching the UI locale leaves the file byte-identical.
- [x] 10.4 No LLM-spending commands were run. `paca doctor` reports `✔ content language  en (from /state/language.json)`; DATABASE_URL / Postgres / configured agents / registered tools all ✔ (exit 1 is the expected cloud-only-profile behavior).
- [x] 10.12 (added) Cleaner conformance run, 10 items per direction x 3 repeats, with the `global` setting pointed at the *opposite* language each time. Chinese source under an `en` setting: body 0/30, mean CJK 0.909, no flipping, retention 0.98. English source under a `zh` setting: body 0/30, mean CJK 0.000, no flipping, retention 0.90. (Final figures; re-measured after 11.2/11.3.) Plus a per-item prompt-level assertion that the composed rule targets the detected language and never the setting. `docs/modules/knowledge.md` + zh mirror updated with the combined four-row table.
- [ ] 10.13 (out of scope, flagged) `knowledge_artifact_editor` compressed the corpus's one long article (41k chars) to ~0.31 retention on all three repeats — under `_MIN_LONG_TEXT_RETENTION` (0.6), so `_check_summarized` would reject that ingest loudly. Every other item measured ≥0.88. Pre-existing cleaner-quality behavior, untouched by this change and orthogonal to language (the output was still correctly English); documented in `docs/modules/knowledge.md` rather than fixed here.
- [x] 10.11 `_run_frontmatter` now truncates at production's `artifact_editor._MAX_MARKDOWN_CHARS` (64000) instead of the probe's own 16000, so the harness's stated "same `write_frontmatter` input shape" is finally true. All four directions re-measured on it; the only visible shift is the en→zh title CJK floor rising 0.070 → 0.156 (proper-noun-dense podcast titles render more completely when the model sees the whole article). Defect counts unchanged at 0/30.
- [x] 10.10 (added) First cleaner run aborted on my own guard, and the guard was wrong, not the code: `language_rule()` always ends with "tags, slugs, category paths stay lowercase English", so a bare `"English" in instructions` check reports a leak on every Chinese-targeted prompt. Rephrased against the rule's directive clause (`... your output in <name>`). Second run then surfaced a real metric bug of mine — retention was computed against the full body while only the probe's 16k frontmatter cap was sent, making a 41k-char article read as summarized to 0.15 against a 0.38 ceiling. Now truncates at the production cleaner's own 64k cap and measures retention against the text actually sent.
- [x] 10.9 (added) Extended `scripts/lang_probe.py` with an `--agent cleaner` mode so the `same_as_source` half is measurable at all — it replays `_run_editor`'s real input shape, takes each item's `detect_language()` result as the per-row expectation, and points `global_language` at the *opposite* language so a body drifting toward the operator's preference registers as a defect rather than passing silently. `_report`'s defect test now reads a per-row `expected` (falling back to `--target`), and retention is reported beside the ratio because a collapsed body moves the language ratio for unrelated reasons.
- [x] 10.8 (added) LLM conformance run via `scripts/lang_probe.py`, 10 real `radar_items` per direction x 3 repeats, on the local `Qwen3.5-122B` (no cloud spend — OMLX reachable, `DEEPSEEK_API_KEY` unset so there is no silent fallback). English source → `zh` setting: title 0/30, summary 0/30, no flipping. Chinese source → `en` setting: title 0/30, summary 0/30, no flipping. Inspected the lowest-CJK titles by hand to confirm the 0-defect reading is not the metric hiding proper-noun-dense output. `docs/modules/knowledge.md` + the zh mirror updated with the fresh table, replacing the stale "reverse direction stays imperfect, 2/30" claim.
- [x] 10.7 (added) End-to-end proof, model-free: with the setting at `zh` and a detected source language of `en`, `_compose_instructions` on the four shipped ingest agents yields — frontmatter → "Write `title` and `summary` in Simplified Chinese" (the setting), github_summary → "Write `summary` in Simplified Chinese" (the setting), and both cleaners → "Write every prose field of your output in English" (the source). The dashboard write and the pipeline read were confirmed to round-trip through `/state/language.json` in the same container.
- [x] 10.5 (added) Fixed a nav overflow this change exposed: at 1280px the English labels already overflowed by 44px, and the new gear button took it to 82px, clipping the settings and theme controls. `.nav-tools > * { flex-shrink: 0 }` + a shrinkable, clipping chip wrapper makes the status chips the only thing that gives. Verified overflow 0 with all controls at full size at 1024 and 1280.
- [x] 10.6 (added) Applied the branch's pending `radar_analyses.title` migration to the running database — `/radar` was 500ing on `column ra.title does not exist` because the stack had never re-run `scripts/bootstrap_db.py` since that column shipped. Pre-existing on this branch, not introduced here.

## 11. Second review round (blockers + suggestions + the DB gap)

- [x] 11.1 **Blocker** — `--agent cleaner` silently lost the mid-run prompt-drift guard: `agents` was `[]` for that mode, so `cmd_run`'s digest loop iterated nothing, and `_assert_names_only` only ran on `rep == 0`. Seeding `digests` is impossible here (`_instruction_digest` builds with no override, which a `same_as_source` agent rejects), so the per-item assert now runs on **every** repeat instead — the agent is rebuilt per call anyway.
- [x] 11.2 **Blocker** — the retention figure was `len(cleaned)/len(body)` while production's `_check_summarized` uses `_content_length` (whitespace-stripped UTF-8 bytes), so the docs compared a probe metric against a production threshold. Now imports and uses `_content_length`; re-ran and restated. Item 3 measures 0.32 on the matching metric (was 0.31 on the mismatched one), still under the 0.6 guard, so the conclusion survives but is now properly grounded.
- [x] 11.3 **Suggestion** — `_run_frontmatter` now truncates at production's 64000 cap (see 10.11).
- [x] 11.4 **Suggestion** — cleaner result files are named `cleaner_<items>_vs_<target>.json`; `<items>2<target>` read as a direction, which is false when `target` is the adversary.
- [x] 11.5 **Suggestion** — the clipped status chips get a `mask-image` fade instead of a hard cut, so a truncated chip reads as "there is more" rather than a rendering bug.
- [x] 11.6 **Doc sync** — added two rows to `.claude/skills/code-review/SKILL.md`'s doc-sync map: an agent policy/rename change must check the measurement harnesses (this change broke `lang_probe.py` and the first review missed it), and a business-table DDL change must check the runtime schema contract.
- [x] 11.7 **DB migration** — the mechanism was never broken (`bootstrap` is idempotent and gated on Postgres health, and it runs on every `up`); what failed was a stale image, and nothing reported it. Added `paca.core.db.BUSINESS_TABLE_COLUMNS` + `missing_business_columns()` as the runtime schema contract, asserted by `scripts/bootstrap_db.py` right after its DDL and reported by `paca doctor` as a `business schema` check. Verified both ways in-container: green against the real database, and against an empty one it names all five tables including `radar_analyses.title` — the exact column whose absence produced a 500 with a healthy-looking doctor.
- [x] 11.8 Fixed a stale claim in `.claude/skills/docker-verify/SKILL.md`: it listed six business tables including `knowledge_tag_labels`, which exists in no DDL, no query and no database. Five, and pointed at the contract as the source of truth.
- [x] 11.9 `uv run pytest -q` → 406 passed, 14 skipped; `ruff check src scripts/lang_probe.py scripts/bootstrap_db.py` clean; `openspec validate --all` 23/23.
