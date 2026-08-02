## 1. The setting

- [x] 1.1 Add `output_language()` to `src/paca/core/context.py` (not `config.py` — that module is the YAML→Pydantic loader; the rule this produces is prompt context, same as the shared block): read `SIGNAL_OUTPUT_LANG` at call time, return `None` when unset/empty, return `"zh"`/`"en"` when recognized, raise `RuntimeError` naming the value and the recognized set otherwise
- [x] 1.2 Add `language_rule(lang)` returning the appended rule text — unconditional, prose-fields-only, identifiers exempt, proper nouns preserved; no per-field clauses (design D4, D5)
- [x] 1.3 Test: unset → `None`; `zh`/`en` → resolved; `fr` → `RuntimeError`; changing the env between two calls changes the result (proves call-time read, design D7)

## 2. Loader composition

- [x] 2.1 Change `src/paca/core/context.py` to append rather than prepend, keeping `_cached` covering only the static shared files
- [x] 2.2 Update `_compose_instructions` in `src/paca/agents/loader.py` to order agent instructions → shared context → language rule
- [x] 2.3 Add the `extra: {output_language: false}` gate, independent of `extra: {shared_context: false}` (design D2)
- [x] 2.4 Test the gate matrix: shared-on/off × language-on/off × env set/unset, asserting block presence and order
- [x] 2.5 Test that an agent with `shared_context: false` still receives the language rule and no house-rules block

## 3. Shared-context payload

- [x] 3.1 In `prompts/_shared/00_house_rules.md`, replace the "reply in the language the user wrote in … match their last message" clause with one deferring to the output-language setting; keep a sensible rule for genuinely conversational agents (design risk 4)
- [x] 3.2 In `prompts/_shared/00_house_rules.md`, drop the claim that shared rules take precedence over per-agent instructions — it now trails those instructions and must not override a field contract
- [x] 3.3 In `prompts/_shared/10_user_profile.md`, remove the "Working language: English" line so the profile no longer pins an output language

## 4. Measured prompt fixes

- [x] 4.1 `prompts/agents/radar_tier2_impact.md`: replace the conditional Style line with `Write summary and impact in Chinese, regardless of the language of goals or of the article body` — delete the old two lines, do not add alongside (measured 63/63)
- [x] 4.2 `prompts/agents/knowledge_frontmatter.md`: replace the trailing `Write Chinese fields in Simplified Chinese` line with an unconditional rule naming `title`/`summary` and exempting `tags` (measured 0/39 defects)
- [x] 4.3 Confirm no field-level language clause is introduced in either prompt (design D4: measured 1/65 → 6/65 truncations)

## 5. Remaining agents

- [x] 5.1 `configs/agents/knowledge_artifact_editor.yaml` and `knowledge_github_cleaner.yaml`: set `extra: {output_language: false}` explicitly
- [x] 5.2 `prompts/agents/radar_recap.md`: replace "Match the language of the item summaries" with the unconditional form
- [x] 5.3 `prompts/agents/knowledge_github_summary.md`: remove "default to English for repos with English-only content"
- [x] 5.4 `radar_dedup_judge` **excluded** (`output_language: false`): `radar_analyses` has no column for its `reason` and nothing renders it — only `is_duplicate`/`matched_topic_id` are consumed, so the rule would be prompt cost with no user-visible effect

## 6. Verification

- [x] 6.1 Port `lang_probe.py` / `fm_probe.py` from the session scratchpad into `scripts/`, as `scripts/lang_probe.py`. The rule is now injected rather than pasted into files, so the guard asserts on the **composed instructions** of the built agent (stronger than the prompt sha256 that caught the earlier silent bind-mount failure) and aborts if the block is missing or names the wrong language
- [x] 6.2 Re-run the radar probe against the **injected** rule (not the in-file rule): 10 items per direction (10 EN articles → `zh`, 10 ZH articles → `en`) × 3 repeats. Expect parity with the measured 63/63 (design risk 1)
- [x] 6.3 Re-run the frontmatter probe against the injected rule, same 10 × 2 directions × 3 repeats; record the residual English-direction defect rate. Keep the repeats: frontmatter's defect is *nondeterministic* (the same article flipped language between runs), so a single pass over 10 items has only a ~55% chance of surfacing a 7.7% defect at all, and cannot detect flipping — which needs the same item generated more than once
- [x] 6.4 Verify `radar_recap` output language over a window whose stored summaries are mixed-language
- [x] 6.5 `tags` unchanged under `SIGNAL_OUTPUT_LANG=zh` — radar tags stayed lowercase-English across runs 19/20 (165 generations each) and the frontmatter probe showed 39/39 English tags; none dropped by `_normalize_tags`
- [x] 6.6 `uv run pytest -q` green (368 passed / 13 skipped); runtime checks run in Docker — `paca doctor`, all 10 agents composing under unset/`zh`/`en` with zero token leaks, and `fr` raising. Every eval and probe in this change also executed in-container. **A full `docker compose build` could not be completed**: pulling the base images times out against the registry right now (`DeadlineExceeded`), so the container runs used the source bind-mount rather than a freshly baked image. Re-run `docker compose build` before deploying

## 7. Configuration and docs

- [x] 7.1 Add `SIGNAL_OUTPUT_LANG` to `.env.example` with the recognized values and the unset-means-unchanged behavior
- [x] 7.2 Add a `paca doctor` line reporting the resolved output language, or an explicit "unset" state
- [x] 7.3 Document the re-index rename hazard: switching language and re-indexing rewrites frontmatter `title`, and the wiki filename derives from `title` (design risk 5)
- [x] 7.4 Update `docs/modules/core.md` + `docs/development.md` and both `docs/zh/` mirrors (shared context now appends; the new setting). Not `architecture.md` — shared context is documented in core.md, architecture.md never mentions it
- [x] 7.5 Update `docs/modules/info_filter.md` and `docs/modules/knowledge.md` plus both `docs/zh/` mirrors, stating plainly which agents are measured and which are not
- [x] 7.6 Update `CLAUDE.md`'s shared-context description, which currently says the block is prepended

## 8. Delivery position (found by measurement, after 6.2 started)

- [x] 8.1 Diagnose the run-20 regression: appending the rule after a prompt's own closers measured `impact` 774 → 1016 chars (+31%) and truncations 2/165 → 7/165, versus +5.7% for the same rule written *into* the prompt (arm A → B1). design.md D1's claim that the appended position was "the position it was measured in" was wrong — in arm B1 the rule was the first of three Style bullets
- [x] 8.2 Add `{{OUTPUT_LANGUAGE}}` token substitution in `paca.core.context` + `loader._compose_instructions`, keeping the appended block as the fallback for prompts without the token
- [x] 8.3 Raise `RuntimeError` when a prompt declares the token while its YAML opts out, so the literal token can never reach the model
- [x] 8.4 Migrate all five prose prompts to the token so their own closers land last
- [x] 8.5 Correct design.md D1, add D8, and update `core-output-language` / `core-agents` deltas plus both `docs/modules/core.md` mirrors
- [x] 8.6 Re-measured (run 21): the token form measured `impact` 1020 — **identical to appending**, so the position hypothesis was wrong. Splitting by source language showed the growth hit Chinese-source items too, whose language never changed

## 10. The real regression (found by 8.6 disproving 8.1)

- [x] 10.1 Root cause: the loader rewrite wrapped every prompt in a `# Agent role` heading. The old loader returned a `shared_context: false` agent's instructions **bare**, and all ten production agents are opted out — so all ten silently got a changed prompt
- [x] 10.2 Only add the heading when another block actually follows it
- [x] 10.3 Verified: with `SIGNAL_OUTPUT_LANG` unset, 4 agents compose byte-identically to main and 5 differ only by the intended language lines — no other drift
- [x] 10.4 Regression test asserting bare instructions when nothing trails
- [x] 10.5 Re-measured (run 22): `impact` back to 767 vs baseline 774; language still 0/73 wrong; flips 3 vs baseline 4
- [x] 10.6 Truncation attribution — **unresolved, suggestive, not blocking**. A same-night control on main's code (worktree, digest `0ff989eeb6a0`) also measured 2/165, ruling out machine state. But a replicate of the final config measured 4/165 against the first run's 8/165 — a 2x spread between identical configurations, so the metric is far noisier than baseline's tidy 2/2 implied. Pooled: baseline 4/330 (1.2%), this change 12/330 (3.6%). All are premature-EOS under xgrammar at ~100 generated tokens, not `max_tokens` hits, and they land on the same ~6 fragile items in both arms (cases 368 and 379 fail in baseline too). Settling a rare-event rate this noisy needs far more runs than the four already spent (~3h OMLX); the production cost is a retry, not data loss, so it is recorded and monitored rather than chased
- [ ] 10.8 Post-merge: watch `tier2_error` in the first few `paca info-radar analyze` runs. If it sits materially above ~1%, revisit — the suspect is the tier-2 Style line, the only tier-2 change in the diff
- [x] 10.7 Correct design.md D1 — record that position was blamed twice and was not the cause either time, and that append-vs-token is therefore unmeasured

## 9. Code-review fixes

- [x] 9.1 **Blocker** — `prompts/agents/knowledge_github_summary.md`: the language line covers `title`, contradicting its own field spec ("use the repo's owner/repo identifier as-is; do not invent a Chinese title"). The wiki filename derives from it, so obeying the language line would rename GitHub artifacts. Scope the rule to `summary` only
- [x] 9.2 Refresh the stale module docstrings in `loader.py` and `context.py` — both still say the rule is appended to every agent
- [x] 9.3 Trim the 36-line `_compose_instructions` docstring and the duplicated inline comment; the measurement prose belongs in design.md (CLAUDE.md: docstring 默认一行)
- [x] 9.4 Same for `language_rule`'s docstring
- [x] 9.5 `paca doctor`'s unset message says "each prompt's own default applies"; with the token it resolves to Simplified Chinese
- [x] 9.6 The token-leak `RuntimeError` asserts a cause it has not verified — the token could also come from `prompts/_shared/`
- [x] 9.7 Doc sync: `SIGNAL_OUTPUT_LANG` added to `docs/operations.md` env list + `paca doctor` check list, and `scripts/lang_probe.py` documented in `docs/modules/info_filter.md` — all four with `docs/zh/` mirrors

## 11. Second review pass (the first predated the regression fix)

- [x] 11.1 The `# Agent role` fix, its tests, and the final doc numbers all landed *after* the code review, leaving the highest-risk rewrite unreviewed. Re-reviewed the delta
- [x] 11.2 **Latent bug** — the heading was gated on "anything trailing", so an unmigrated agent (`knowledge_classifier`: no token, `shared_context: false`) gained the heading the moment `SIGNAL_OUTPUT_LANG` was set. That is the same heading measured at +31% tier-2 output. Gated it on the shared block instead, which is the only thing it disambiguates
- [x] 11.3 Two comments in `loader.py` and `context.py` still asserted that appending caused +31% and 2→7 truncations — the diagnosis disproved in 10.1. Corrected; they now point at design.md D1 and state the append-vs-token comparison is unmeasured
- [x] 11.4 Regression test that enabling the setting adds the rule and nothing else
- [x] 11.5 Re-audited every agent under unset/`zh`/`en`: no heading anywhere except `echo` (the only agent with shared context on), zero token leaks, 4 agents byte-identical to main
