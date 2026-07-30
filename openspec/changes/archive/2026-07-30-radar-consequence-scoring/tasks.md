## 1. Stage 1 — goals.yaml (configuration, no spec delta)

- [x] 1.1 Confirm `configs/info_radar/goals.yaml` carries the fourth goal `science_breakthrough` with its disqualifier checklist, and that **the fourth goal's text** states no score band or numeric cap — `render_goals_block` splices the description verbatim into tier 1, which has no score field and will read a band instruction as a drop instruction. *(Caught a real one: the disqualifier list said "就是 0-44 档". Reworded to name no band.)*
- [x] 1.5 Remove goal 1's score cap and its top-lab product-PR exclusion (scope extended on the user's call after 2.4/2.5 showed the tier-1 revert dropped exactly the flagship cases the change exists to fix). One edit: dropped `命中也不得 ≥70`, its duplicate `<70 上限` on line 21, and `产品与资本通稿（…集成发布，即便来自顶级实验室）`; added an explicit statement that a flagship model/chip/agent release is itself top-value for this goal. `radar_tier1_filter.md` untouched
- [x] 1.6 Measure the goal-1 edit on `focus`: IND-surface 5/12 → **9/12**, scored-item pair count 28 → 48 (all 12 industry items now reach scoring), 644 → 88, 134 → 83, 645 → 64, 152 → 58. Cost: NEG-vendor 6 → 5, PAP-drop 1 → 0
- [x] 1.7 Validate the goal-1 edit on `holdout`: false keeps **9** (production 4, tier-1-rewrite variant 15), false drops 2, industry mean 57.8 → **67.7**, paper mean 83.0 → **58.4**, gap **+9.3**. At threshold 65 this surfaces 11 industry / 1 paper against production's 10 / 2; at 70, 10 industry against production's 6. First configuration to beat production on signal rather than trade against it
- [x] 1.2 Verify the file loads: `load_goals()` returns four goals and both radar agents build from name
- [x] 1.3 Run the eval on `focus` and confirm the science items behave. *Result: keep side passes (611 → 82, 55 → 86). Drop side is marginal — 10 drops cleanly, but 53 reaches 58, 165 reaches 55 and 54 reaches 35 on the repeats where they leak. PAP-drop 1/4.*
- [x] 1.4 *(5afa46f)* Commit stage 1 alone, referencing this change

## 2. Stage 2 — tier-2 scoring prompt

- [x] 2.1 Confirm `prompts/agents/radar_tier2_impact.md` opens the `score` field with consequence framing, not `anchored on EVIDENCE quality`, and states that rigor belongs in `impact`
- [x] 2.2 Confirm the mechanical "what can an outsider obtain right now?" step is present with its four floor options, the anchor table is present with the explicit ordering constraint, and the removed three-axis ±3 adjustment is gone
- [x] 2.3 Confirm the knowledge-cutoff instruction is present and the `content_status='fallback'` scoring guidance is present (the latter is required for stage 3 — without it, honest thin-content labelling measured −5.3)
- [x] 2.4 Run the eval on `focus` with `--repeats 3`. *Result: inversions 6/28 (21%), gap +6.5, overall 21/36. **But the pair count fell from 48 to 28** because only 7 of 12 industry items survive the original tier-1 — the gap metric improves partly by dropping weak industry items before they can be scored, so +6.5 is not comparable to the tuned-tier-1 +1.9 over 12 survivors.*
- [x] 2.5 Validate on `holdout` with `--repeats 3`. *Result: gap +3.8 (production −25.2), false keeps 10 (production 4), pass 36/55 vs production 41/55. The tier-2 scoring gain survives without the tier-1 loosening — hypothesis confirmed on two independent sets.*
- [x] 2.6 *(dbfd15c)* Commit stage 2 alone

## 3. Stage 3 — fetch content handling

- [x] 3.1 Confirm `stages/fetch.py` flattens feed HTML to text before any length test or truncation, and returns `fallback` when flattened prose is under `_MIN_ARTICLE_CHARS`
- [x] 3.2 Confirm `tests/test_info_radar_analysis_fetch.py` covers markup stripping and the lede-only case, and that the three pre-existing fixtures were lengthened past the threshold rather than the threshold lowered to accommodate them
- [x] 3.3 Run `uv run pytest -q` — expect all green with only the usual integration skips
- [x] 3.4 Sanity-check real content lengths per feed after the change; the paywalled feed should now report `fallback` and the markup-heavy feed should deliver more prose within the 16k cap
- [x] 3.5 *(de778a7)* Commit stage 3 alone

## 4. Supporting tooling (not part of the runtime contract)

- [x] 4.1 Confirm `scripts/radar_eval.py` provides `init` / `load` / `run` / `report`, reuses the real `tier1.run_batch` / `fetch.run` / `tier2.run`, and skips the dedup gate (it writes `radar_pushed_topics`, which is shared production state, and does not affect verdict or score)
- [x] 4.2 Confirm the three label sets are present: `eval_cases.yaml` (adversarial, 60), `eval_cases_focus.yaml` (decision boundary, 36), `eval_cases_holdout.yaml` (independently labelled, 55)
- [x] 4.3 Confirm `eval_cases_holdout.yaml` carries the note that it must never be tuned against
- [x] 4.4 Confirm `.claude/skills/radar-prompt-tuning/SKILL.md` exists and its numeric claims match this change's measurements
- [x] 4.5 *(45d3f2a; docs in 494957d)* Commit tooling

## 5. Documentation sync (English canonical, both languages in this change)

- [x] 5.1 Update `docs/modules/info_filter.md:76` — it describes the two-step rubric as "adjust within ±3 bands across three dimensions", which no longer exists. Replace with the consequence framing, the obtainability floor step, and the anchor table
- [x] 5.2 Update the same file's description of the `content_status` contract to cover the 200-character prose threshold and HTML flattening
- [x] 5.3 Mirror both edits into `docs/zh/modules/info_filter.md:65-66`
- [x] 5.4 Add the eval harness and its three label sets to the module doc's tooling section in both languages, including the rule that `holdout` is never tuned against
- [x] 5.5 Record in the module doc, in both languages, that the tier-1 filter prompt rewrite was measured and rejected, so the next attempt does not repeat it

## 6. Close out

- [x] 6.1 Re-read the doc-sync map. *Eight rows walked; one real drift found and fixed: CLAUDE.md said business-table DDL lives in `bootstrap_db.py`, which the eval tables' deliberate exception contradicts (commit follows). Rows N/A: no tool/integration, no new module under `src/paca/` (the harness is a script), no `configs/agents|workflows|teams` change, no CLI subcommand (deliberately — a script avoids that contract), no env var, no dependency (stdlib `re` + `html`). Test count 338 → 340 and CLAUDE.md states no hard number.*
- [x] 6.2 Run `uv run pytest -q` and `openspec status --change radar-consequence-scoring` one final time
- [x] 6.3 Report to the user which changes had a measured effect, which had none (the paper ceiling clause never bound), and which regressed — a ruled-out suspect is a finding, not something to omit
- [x] 6.4 Run `/opsx:archive` to fold the two spec deltas into `openspec/specs/`
