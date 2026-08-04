## Context

`core-output-language` (archived change `2026-08-02-configurable-output-language`) shipped one resolution mode: `SIGNAL_OUTPUT_LANG` (env var) → `output_language()` → `language_rule()`/token substitution, gated per-agent by `extra.output_language: false`. That mechanism is correct and stays unchanged — this change does not touch the injector, the phrasing, or the token-substitution logic. What's wrong is that every agent in the system is forced through the *same* resolution source, and two of the three real use sites need a different one:

- info-radar wants one operator/user-wide preference, changeable at runtime from the dashboard.
- knowledge ingestion wants the *source article's own* language, which varies per item and cannot come from a global setting at all.
- `tags` want a fixed value regardless of either.

Traced during exploration and confirmed against current code:

- `radar_analyses` has no `title` column; the dashboard reads `radar_items.title` verbatim (`dashboard/lib/radar/queries.ts`). `Tier2Analysis` (`workflows/info_radar_analysis/schemas.py`) has `summary`/`impact`/`score`/`tags` — no `title`.
- `knowledge_frontmatter`/`knowledge_github_summary` currently resolve the *same* `SIGNAL_OUTPUT_LANG` as info-radar (`agents/loader.py::_compose_instructions` → `output_language()`), with no source-language detection anywhere in the repo (`langdetect`/`langid`/`fasttext`/`lingua` all absent from `pyproject.toml`).
- `knowledge_artifact_editor`/`knowledge_github_cleaner` carry `output_language: false` and receive no rule at all — the "preserves source language" behavior is an inherited default, never independently measured the way `radar_tier2_impact`/`knowledge_frontmatter` were.
- `openspec/specs/info-radar-analysis/spec.md`'s "Downstream radar agents do not re-derive language" requirement currently claims `radar_dedup_judge` follows the configured language. The shipped prompt (`prompts/agents/radar_dedup_judge.md`) and YAML (`output_language: false`) have always exempted it — this was an open question in the archived design ("Should `radar_dedup_judge` follow the setting at all?... Including it may be pure cost") that was resolved as "no" in the code but never reflected back into the spec.
- The dashboard container shares the same `/state` volume and `PACA_STATE_DIR` as every pipeline container (`docker-compose.yml`, `dashboard: <<: *app`), and already has a locale mechanism (`dashboard-shell`'s "Bilingual UI via a locale cookie" requirement: `paca_locale` cookie, `LanguageToggle` component, `dashboard/lib/i18n/dictionaries.ts::DEFAULT_LOCALE`).

## Goals / Non-Goals

**Goals:**

- One resolver (`core/language.py`) serves all three use sites, each declaring a policy in its own agent YAML — no per-site bespoke plumbing.
- info-radar's `title`, `summary`, `impact`, and tier-1 `reason` are consistent in the same, user-selectable language.
- Knowledge ingestion's body, title, and summary preserve the source article's own language, explicitly and deterministically, not as a side effect of the model's default behavior.
- The dashboard can change the info-radar language live, without a container restart, using its *existing* locale control — no new settings UI.
- The system works correctly with zero dashboard interaction ever having happened (fresh clone, `.env` never touched, dashboard container never started).
- `tags` behavior is provably unchanged.

**Non-Goals:**

- Changing the injector: phrasing, token substitution, unconditional wording, and the shared-context/output-language gate independence (D1–D8 of the archived design) all carry forward untouched.
- Folding `tags` into the general policy mechanism. D4 of the archived design already measured that a field-specific injected clause costs reliability (35% longer output, truncations 1/65 → 6/65); tags keep their existing bespoke, hardcoded-English prompt instruction.
- A new dashboard settings page. The existing locale toggle is the control.
- Storing the live preference in Postgres. It's one scalar with no query pattern over it; `~/.next-signal/` is the project's established home for exactly this shape of thing (`knowledge_ingest_manifest.json` is the existing precedent).
- LLM-based language detection.
- Supporting languages beyond `zh`/`en` in this change. The detection interface and the policy model are built to make that a localized addition later, not a redesign — but no third language ships here.

## Decisions

### D1: Policy is a small enum on the existing `extra.output_language` key, not a new key

`off | global | same_as_source | fixed:<lang>`. Reuses the field every agent config already has; a bare `false` still means `off` (zero-churn for `radar_dedup_judge`'s existing config). Default when absent is `global`, identical to today's default-on behavior — agents nobody touches in this change (`radar_tier1_filter`, `radar_tier2_impact`, `radar_recap`) need no YAML edit for the policy itself.

Alternative rejected: a separate centralized YAML mapping agent → policy. Rejected because it duplicates information that's more useful sitting next to the rest of an agent's own `extra` flags (`shared_context`, `db`), and because CLAUDE.md's own convention is that an agent's tunable behavior lives in its own file, not a side table a reader has to cross-reference.

### D2: `core/context.py` stays scoped to shared static context; the language resolver moves to a new `core/language.py`

`context.py`'s own docstring already scopes it to "shared static context and the output-language setting." That setting is about to grow a policy dispatcher, a state-file reader/writer, and a detection interface — enough new surface that it no longer reads as "context," and `context.py` shrinks back to just `shared_context()`/`reload()`. `agents/loader.py` imports from `core/language.py` instead.

### D3: The live global preference is a JSON file under `STATE_ROOT`, not `.env` and not Postgres

`~/.next-signal/language.json` (`STATE_ROOT / "language.json"`): `{"content_language": "zh", "updated_at": ..., "updated_by": "dashboard"}`. Written atomically (temp file + `os.replace`).

Rejected: `.env`. An env var's value is fixed for the container's lifetime — `docker-compose`'s `env_file: .env` is read at container creation, not on file change — so it structurally cannot serve a "user changes this at runtime, takes effect on the next run" requirement. Keeping it as a *second*, independent input into the same resolution (state file OR env var, whichever is set) was considered and rejected too: it creates a silent-override risk where an operator sets `SIGNAL_OUTPUT_LANG` expecting it to matter and a dashboard click silently overrides it. One live mechanism, one static code fallback (D4) is simpler and has no ordering ambiguity.

Rejected: Postgres table. This is a single scalar with no relational shape and no query pattern — a new table + DDL in `scripts/bootstrap_db.py` is more ceremony than the data warrants. The file approach also means the dashboard needs no new DB write path for this feature; it already shares the `/state` volume with every pipeline container.

### D4: The ultimate fallback is a hardcoded constant in code, not an env var default

`DEFAULT_LANGUAGE = "en"` in `core/language.py`, matching the dashboard's own `DEFAULT_LOCALE`. Resolution order for the `global` policy: state file (if it exists) → this constant. A fresh `.env` — copied from `.env.example`, with or without a language field — can never leave the system unconfigured, because `.env` is no longer part of the chain at all. Headless deployments that never run the dashboard (so the state file is never created by the sync hooks in D5) and want non-English output can hand-edit `language.json` directly — the same mechanism the dashboard uses, not a second one.

### D5: Dashboard sync is two hooks, not per-request polling

1. A one-time process-start hook (`dashboard/instrumentation.ts`, Next.js's `register()`) creates `language.json`, seeded from `DEFAULT_LOCALE`, if it doesn't already exist.
2. The existing locale-toggle server action (`dashboard-shell`'s "operator changes language" scenario, which already writes the `paca_locale` cookie) is extended to also write `language.json` in the same action.

Rejected: checking on every page render. There is no other code path that changes the cookie, so a per-request reconciliation check would do file I/O for zero benefit. The two hooks above cover both real cases: "state file doesn't exist yet" only happens once per container lifetime (hook 1), and "state file disagrees with the current locale" only happens at the exact moment a user changes the locale (hook 2) — there's no third moment where drift could be introduced.

### D6: Source-language detection is a deterministic heuristic behind a swappable interface, not an LLM call

`core/language_detect.py` exposes `detect_language(text: str) -> str`. First implementation: count Unicode codepoints in the CJK ranges against total alphabetic codepoints, threshold-based `zh`/`en` classification. No new dependency, no network call, no sampling.

Rejected: an LLM-based detection agent. This would reintroduce the exact failure mode this whole change exists to fix — `knowledge_frontmatter` with no rule at all was measured flipping languages across repeat runs on identical input (17.9%/7.7% defect rate, archived design.md). Using an LLM to decide *what* language to target has the same sampling-variance exposure as using one to decide how to *write* in it.

Rejected (for now): pulling in `langdetect`/`lingua`. Justified once the language set grows past `{zh, en}` or real mixed-script/short-text failures show up in practice; not justified for a two-way classification where a simple script-ratio check is already close to the ceiling. The interface is written so this swap touches one module, not call sites.

Detection runs once per ingested item, primarily against the item's **title** rather than its full raw body. A title is short but reliably natural-language prose — unlike, say, a GitHub README's body, which can be dominated by code fences and Markdown syntax with only sparse natural-language signal — so it gives the heuristic a much cleaner input to classify. When no title is available, detection falls back to the fetched raw body text. Because the title is available immediately at fetch time and doesn't change during cleaning, one detection pass per item is sufficient — there's no need to re-run detection after `clean_step` sees the cleaned body.

The resolved value threads as the `language=` override through both `clean_step` (`knowledge_artifact_editor`/`knowledge_github_cleaner`) and `enrich_step` (`knowledge_frontmatter`/`knowledge_github_summary`).

### D7: Body-cleaning agents move from implicit exemption to explicit `same_as_source`

Today `output_language: false` means "no rule reaches this agent at all"; the source-language-preserving behavior is real but was never measured independently of the frontmatter agents. Moving them to `same_as_source` costs nothing new (D6's detection step already exists for the frontmatter agents on the same item) and closes the one remaining place in the system where output language is an implicit side effect of the model's default tendency rather than an explicit instruction — which was the whole principle motivating this change in the first place.

### D8: info-radar `title` is a new field on the existing tier-2 call, not a new agent or a new stage

`Tier2Analysis` gains `title: str`; the source title (already passed into the tier-2 prompt as input context) becomes something the model is asked to rewrite/translate, under the same `global` resolution as `summary`/`impact`. `insert_analysis()` and `radar_analyses` gain a `title` column; the dashboard query (`getItemsForDay`, `getDayGroups`, `getItemDetail` in `dashboard/lib/radar/queries.ts`) reads it from `radar_analyses` instead of joining `radar_items.title`. No new call, no new stage — one more field on an already-measured, already-reliable prompt.

## Risks / Trade-offs

- **BREAKING: `SIGNAL_OUTPUT_LANG` stops doing anything** → any deployment currently relying on it silently loses effect the moment this ships, with no error (it's simply no longer read). Mitigation: call this out prominently in the migration plan and in `.env.example`.
- **`radar_analyses.title` is a schema change on a table with existing rows** → historical rows have no title. Mitigation: `title` is nullable; the dashboard falls back to `radar_items.title` when `radar_analyses.title IS NULL`, so old rows keep rendering (in their original, untranslated language) rather than showing blank.
- **The Unicode-ratio heuristic still needs a fallback for titleless items** → detection is keyed to the item's title precisely because it's a small, reliable, prose-only signal (see D6); the residual case is an item with no title at all (rare, but possible for some source types), which falls back to the raw body and inherits whatever signal-density problems the title was chosen to avoid. Mitigation: tune the threshold against a small real sample before shipping, and treat this as a bounded, correctable parameter rather than an architectural risk — the swappable interface (D6) makes a stronger classifier a contained follow-up if it proves insufficient.
- **File-based state under concurrent access** → the dashboard writes, and in principle a second dashboard instance or a hand-edit could race it. Mitigation: atomic temp-file-plus-rename write, same pattern used elsewhere in the codebase; last-write-wins is an acceptable outcome for a human-driven, low-frequency toggle.

## Migration Plan

1. Land `core/language.py` and `core/language_detect.py` alongside the existing `core/context.py` mechanism, unused by any agent yet — no behavior change.
2. Switch `agents/loader.py` to the policy-based resolver; update the three info-radar agent YAMLs to explicit `global` (no-op, matches current default) and `radar_dedup_judge` to explicit `off` (no-op, matches current value) — first deploy step is behavior-neutral by construction.
3. Add the `radar_analyses.title` column and the tier-2 schema/prompt change; verify against the same holdout-style check the archived change used before trusting it in production.
4. Switch the four knowledge-ingestion agents to `same_as_source`; wire the detection step into `fetch_step`/`clean_step`/`enrich_step`.
5. Ship the dashboard hooks (`instrumentation.ts`, extended locale action) and the dashboard query change to read `radar_analyses.title`.
6. Remove `SIGNAL_OUTPUT_LANG` from `.env.example` and update bilingual docs.

Rollback: each step is independently revertible; the highest-risk step is 4 (knowledge ingestion's language behavior actually changes for the first time), which can be rolled back alone by reverting those four YAML files to their prior policy without touching anything else.

## Open Questions

None outstanding. The two questions this design started with are resolved: detection runs once per item, keyed primarily to the title (D6) rather than re-checked after cleaning; and no `paca doctor` check is being added for a stray `SIGNAL_OUTPUT_LANG` — the migration-plan and `.env.example` callouts are the agreed mitigation for that risk.
