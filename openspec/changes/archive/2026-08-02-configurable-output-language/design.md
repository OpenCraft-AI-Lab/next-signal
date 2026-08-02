## Context

Every LLM-writing prompt in the repo derives its output language from its input.
That is the wrong default for the actual use case: reading a Chinese digest of an
English article without reading English.

Measurements from this change's investigation, all on the shipped prompts, real
stages, the real `local_structured` profile, in the Docker image, with the
prompt sha256 recorded per run:

| arm | prompt | content → target | `summary` on-target | errors |
|---|---|---|---|---|
| A | shipped | EN → zh | **0/64** | 1/65 |
| B1 | one unconditional line | EN → zh | **63/63** | 2/65 |
| B2 | B1 + field-level clause | EN → zh | 59/59 | **6/65** |
| C | full English prompt | ZH → en | **65/65** | 0/65 |

Arm A also reproduces in production: all 13 real `radar_analyses` rows for
English articles have an English `summary`, across two prompt versions and 13
days. In the same responses `impact` and tier-1 `reason` were Chinese 100%.

`knowledge_frontmatter`, measured separately (13 articles × 3 repeats), has no
language rule at all and fails nondeterministically: 17.9% of titles and 7.7% of
summaries pure English, with individual articles flipping between runs. One
unconditional rule took both fields to 0/39 defects.

Constraints carried in from `CLAUDE.md` and prior decisions: agent behavior
lives in YAML and prompts, not Python; new env vars avoid the `PACA_` prefix;
env is read at call time, never at import; misconfiguration fails loud.

## Goals / Non-Goals

**Goals:**

- One setting decides the output language for every prose field the user reads.
- The two agents with measured defects are fixed, and their prompts stay correct
  even for a caller that does not inject a rule.
- Delivery reaches the ten agents that opt out of shared context, without
  forcing unrelated house rules on them.
- The shared-context payload stops contradicting the setting.

**Non-Goals:**

- Changing `tags`. They stay lowercase English identifiers.
- Translating article bodies. `knowledge_artifact_editor` and
  `knowledge_github_cleaner` are permanently exempt.
- Translating `configs/info_radar/goals.yaml`. Arm C showed an English target
  holds against Chinese goals *and* Chinese content, so goals language and
  output language are independent.
- Per-locale prompt files. One injected rule covers the measured need.
- Unifying with the dashboard's `paca_locale` cookie. That governs UI chrome;
  this governs generated content. They may diverge deliberately.

## Decisions

### D1: Append shared context; deliver language by in-place substitution

Shared context moves from prepend to append, as directed.

The language rule is **not** appended for prompts that can carry it themselves.
A prompt declares `{{OUTPUT_LANGUAGE}}` inside its own Style block and the
loader substitutes the resolved language name. Prompts without the token still
get an appended block, so enabling the setting reaches every agent.

**Position was blamed twice and was not the cause either time.** The record,
because it is the most expensive thing this change learned:

| run | what changed | `impact` chars | truncations |
|---|---|---|---|
| 17 baseline (Jul 30) | — | 774 | 2/165 |
| 20 | language line + rule appended | 1016 (+31%) | 7/165 |
| 21 | language line + token in place | 1020 (+31%) | 6/165 |
| 22 | 21 minus the `# Agent role` wrapper | **767** | 8/165 |

Run 21 was supposed to prove the appended position caused the growth. It
measured 1020 — identical to appending. Splitting by source language then showed
`impact` grew ~30% for Chinese-source items too, whose output language never
changed, so it was never about language or position at all.

The actual cause was a refactor accident: the old loader returned a
`shared_context: false` agent's instructions **bare**, and the rewrite wrapped
every prompt in a `# Agent role` heading. All ten production agents are opted
out, so all ten silently got a prompt they had never seen. Removing the wrapper
put `impact` back to 767 against a 774 baseline.

So **the append-vs-token comparison remains unmeasured.** The token form is kept
on its own merits — a prompt stays readable and correct standalone, and nothing
displaces its closing contract — not because it fixed a measured regression.

Truncations did not follow output length (8/165 at baseline length), and the
baseline run is three days older than the rest; a same-night control on main's
code is the only way to tell prompt effect from machine state.

Alternatives rejected: prepending as a `# System rules` header (never measured,
and 150 lines from the field it governs); token-only with no append fallback
(a new agent silently gets no language control).

### D2: The language gate is independent of the shared-context gate

`extra: {output_language: false}` opts out of the rule; `extra: {shared_context:
false}` opts out of the house-rules block. Neither implies the other.

Coupling them was the obvious design and is wrong. All ten production agents set
`shared_context: false`, so coupling would mean turning shared context *on* for
them to get the language rule — which drags in `00_house_rules.md`. That file
tells every agent to "prefer one sentence over two" and to inline citation URLs.
`radar_tier2_impact` is instructed to write 3-8 paragraphs of `impact`, and its
`summary` feeds a dedup embedding; both directives are actively harmful there.

### D3: The fallback rule is generated in code, not a file in `prompts/_shared/`

The rule text depends on the resolved language, so it cannot be a static file
the way house rules are. It is generated from the setting at build time. This
applies only to the append fallback (D1) — migrated prompts carry their own
sentence and receive just the language *name*.

This is the one place the change puts prompt-ish text in Python, which sits
awkwardly against "agent behavior lives in YAML". The mitigation is scope: the
generated text is a fixed two-sentence template with the language name
substituted — not a tunable prompt. Anything an operator would want to tune
stays in the agent's own `.md`.

### D4: The rule names field *classes*, not field names

"Write prose fields in X; identifier-like fields (tags, slugs, category paths)
stay English; keep proper nouns in their original form."

It has to be class-based because one rule serves agents with different schemas —
the injector does not know that this agent has `summary`/`impact` and that one
has `title`/`summary`/`tags`.

It also must *not* be field-level even where it could be: arm B2 added a clause
naming `summary` specifically, held language equally well, and made output 35%
longer with truncation failures rising 1/65 → 6/65 against the 4096 `max_tokens`
cap. More prompt bought nothing and cost reliability.

### D5: Unconditional phrasing is the actual fix

Arm A's rule already named `summary`, and the goals already were Chinese — it
still failed 64/64. The rule was a conditional ("if goals are in Chinese,
write in Chinese"), which makes the model resolve a predicate before acting.
Removing the predicate fixed it with no other change. Every rule this change
writes, injected or in-prompt, is unconditional.

### D6: Fix the prompts *and* ship the injector

`radar_tier2_impact` and `knowledge_frontmatter` get their measured edits
directly, rather than relying solely on injection. Those two edits are the ones
with numbers behind them, they keep the prompts correct when read on their own,
and they mean the change is still a net improvement if injection is later
reverted.

### D7: Call-time read, and the cache must not freeze it

`paca.core.context.shared_context()` caches its concatenated string in a
module-level `_cached` with a `reload()` hook for the dashboard. The language
rule must not be folded into that cached string, or the first agent build would
freeze the language for the process. The resolved language is read per call and
the rule composed per call; only the static shared files stay cached.

### D8: A token in an opted-out prompt is a hard error

If a prompt declares `{{OUTPUT_LANGUAGE}}` while its YAML sets
`output_language: false`, nothing substitutes it and the literal token reaches
the model. The loader raises instead. This is the only new failure mode the
token introduces, and it is a config mistake, not a runtime condition.

## Risks / Trade-offs

- **The delivery form must be measured, not assumed** → this already bit once.
  Appending the rule after the prompt's closers measured +31% `impact` and
  2 → 7 truncations (see D1). The token form restores the measured position and
  is being re-measured on the holdout set; do not close the change on the
  in-file arm-B1 numbers alone.

- **Tier-2 truncations may be up, cause unknown** → holdout truncations measured
  2/165 (baseline, Jul 30), 2/165 (baseline re-run same night — so *not* machine
  state), and 6-8/165 across three runs of this change. They are premature-EOS
  under xgrammar, not `max_tokens` hits: `models.yaml` records them landing at
  ~100 generated tokens, and they did not track output length here either
  (8/165 at a `impact` length of 767 versus 2/165 at 774). They concentrate on
  the same ~6 fragile items in both baseline and this change — cases 368 and 379
  fail in both — so it may be sampling on a small prone pool rather than a rate
  change. A replicate of the final configuration is the tiebreaker. Production
  impact either way is a retry, not data loss: a tier-2 failure leaves the item
  unseen with no `radar_analyses` row, and the next run picks it up.

- **Dedup embeds the tier-2 `summary`, so its language changes too** →
  `radar_pushed_topics` is never swept and permanently holds 32 English topics
  from before this change. A Chinese summary of an English article is ANN-matched
  against the English embedding of the same story. Measured on 5 such pairs:
  cosine 0.11-0.26 (mean 0.195) against a 0.40 threshold — all pass with margin,
  so cross-language duplicates are still caught. The margin is finite: tightening
  `DEFAULT_THRESHOLD` below ~0.30 would start dropping them.

- **`prompts/` is bind-mounted live into eval containers** → editing a prompt
  while a run is in flight silently mixes two prompt versions into one result
  set. `scripts/lang_probe.py` now records each agent's composed-instruction
  digest at start and refuses to write results if it changed mid-run;
  `radar_eval.py` has no such guard, so do not edit prompts during its runs.

- **The English direction is not clean** → 5.1% of frontmatter titles and
  summaries still came back wholly Chinese under an English target, and the
  failures flip between runs. The Chinese direction is 0/39. Ship with this
  known gap documented; a post-generation language check with one retry is the
  fallback if it matters, and `run_structured` already has a repair loop to hang
  it on.

- **Three agents are folded in without measurement** → `radar_recap`,
  `radar_dedup_judge`, `knowledge_github_summary` carry the same pattern but
  were never run. `radar_recap` in particular should follow for free once tier-2
  summaries change, since it reads them. Verify at least `radar_recap` before
  closing; state plainly in the docs that the other two are unmeasured.

- **Editing house rules touches every future agent** → removing the "match their
  last message" clause is correct for these payload-driven agents but would
  change behavior for a genuinely conversational agent added later. Replace it
  with a clause that defers to the output-language setting rather than deleting
  it outright.

- **A stale `SIGNAL_OUTPUT_LANG` silently changes the wiki** → re-indexing under
  a different value rewrites frontmatter `title`, and the wiki filename derives
  from `title`. Re-index after a language switch can rename files. Call this out
  in the deployment docs; do not attempt automatic migration here.

- **Prompt-only enforcement has no floor** → nothing validates the language of
  what comes back. A regression would be invisible until someone reads the
  dashboard. The probes are the only guard, and they are not in CI.

## Migration Plan

1. Land the mechanism with `SIGNAL_OUTPUT_LANG` unset — behavior is unchanged.
2. Land the two measured prompt edits; they are correct with or without the
   variable.
3. Re-run both probes against the injected form and record the numbers.
4. Set the variable in `.env`, document it, and re-verify with `paca doctor`.

Rollback is unsetting the variable, which disables injection entirely and leaves
the two corrected prompts in place.

## Open Questions

- Should `radar_dedup_judge` follow the setting at all? Its `reason` is internal
  and never rendered; the embedding is computed from tier-2's `summary`, not
  from the judge's output. Including it may be pure cost.
- Should the dashboard surface the active output language, given it already has
  an independent UI locale toggle? Two language controls with different meanings
  is a real confusion risk.
