## Context

Nine measured rounds went into this change. Most of the intuitive fixes were
wrong, and the record of *what failed* is as load-bearing as the final diff — it
is what stops the next attempt from repeating it. The measurements come from an
offline harness (`scripts/radar_eval.py`) that replays the real tier-1 and tier-2
stages over hand-labelled subsets of `radar_items` and writes to dedicated
`radar_eval_*` tables, because production rows are write-once
(`UNIQUE(radar_item_id)` + `ON CONFLICT DO NOTHING`, and `mark_seen` fires before
fetch).

Three label sets exist. `focus` (36 items) sits entirely on the decision boundary.
`v1`/`v2` (60 items) are adversarial — deliberately stacked with known failures.
`holdout` (55 items) was labelled by three independent agents that read only
`goals.yaml` and were forbidden from reading the prompts or any existing label
set; only unanimous items were kept. **`holdout` is the only set with any claim to
being unbiased, and it must never be tuned against.**

The scoring agent is sampled, not deterministic: `local_structured` runs at
temperature 0.2, and re-running an identical item with an identical prompt moves
its score by ~9 points on average, up to 63 in the worst observed case. Every
number below is a mean over three repeats.

## Goals / Non-Goals

**Goals:**

- Stop ranking academic papers above industry events. Target metric is the
  paper-versus-industry mean score gap on `holdout`, which was −25.2.
- Keep the change attributable: one behavioural change per measured run, so a
  regression can be traced to a specific edit.
- Leave behind the measurement apparatus and the failure record, so the next
  person tuning these prompts starts from evidence rather than intuition.

**Non-Goals:**

- **Score resolution.** Correlation between system score and independent labels
  was 0.544 before this work and 0.520 after — unchanged. The score does not
  carry reliable fine-grained ordering information and this change does not fix
  that. Doing so needs a different output contract (coarse buckets, or ranking a
  batch relatively), which is a separate change.
- **The tier-1 filter prompt.** Attempted and reverted; see Decisions.
- **The `DEFAULT_MIN_SCORE = 65` dashboard threshold.** The ordering fix lands
  industry items at a 62.5 mean, just under the visibility line. Re-basing the
  threshold is a real follow-up but it is a product decision, not part of this
  change.
- **Rescoring the existing 505 rows.** They stay frozen. Adding a `--reanalyze`
  path was scoped and deliberately dropped as unnecessary machinery for a
  one-time backfill.

## Decisions

### Re-key `score` from evidence quality to consequence

The `score` field opened with *"anchored on EVIDENCE quality, not how interesting
it sounds"*. That sentence rewards methodological rigor, which is a property
papers have and news does not, and it defeated seven consecutive attempts to fix
the bias by rewriting the band definitions beneath it. Changing the framing
sentence — and explicitly demoting rigor to something reported in `impact` —
moved the worst single offender from 87 to 78 and the gap from −3.6 to −0.5.

*Alternative considered*: keep the evidence framing and add a separate consequence
axis. Rejected — the earlier ±3 three-axis experiment showed added axes are below
the sampling noise floor and simply are not executed.

**Generalised lesson, recorded because it cost seven rounds**: when a patch does
not take, look upward in the prompt for a framing sentence that contradicts it.

### Add a mechanical "what can an outsider obtain right now?" step

Papers scored with *zero* variance across repeats (72/72/72) while industry items
swung up to 63 points (15/58/78). The model holds a stable internalised prior for
"conference paper" and none for "a founder tweeted support", so industry scores
were effectively sampled. A forced four-option question that sets a floor cut mean
spread from 11.6 to 9.8 and flipped the gap positive (+1.9).

*Alternative considered*: describe the industry categories more richly. Rejected
on evidence — richer category prose failed three times in the tier-1 work, while
a mechanical ordered step succeeded immediately. On this model under xgrammar
constrained decoding, **an ordered procedure beats a rule with exceptions.**

### Replace the ±3 three-axis adjustment with an anchor table

The removed mechanism could move a score by at most ±9, identical to the sampling
spread, and 36% of observed scores fell on values its arithmetic cannot produce —
the model was never running it. Concrete anchors at named score points, plus an
explicit ordering constraint ("a flagship release outranks a narrow paper"), give
a relative reference instead of another abstract axis.

### Flatten feed HTML, and stop calling a lede "full"

Two sub-fixes with *opposite* measured effects, which is why they are documented
separately: flattening markup was **+1.0**, while honestly marking thin content
`fallback` was **−5.3**. The second is harmful alone because the prompt then had
no instruction for how to score thin content — telling an evidence-graded rubric
"you do not have the full article" just hands it a reason to mark down. The two
ship together with a companion prompt clause ("what is missing is length, not
evidence"), and the +3.8 held-out result was measured with both present. They
must not be split.

*Threshold*: 200 characters of flattened prose. The separation is clean — the
paywalled feed's items measure 51–75 characters of text, real articles 2,700–6,200
— with nothing near the boundary in 60 sampled items.

### Ship a fourth goal rather than patch the prompts for science coverage

`science_breakthrough` was requested for major non-AI milestones. It is
configuration, not contract, so it needs no spec delta. It rescued items that
tier-1 had been dropping consistently (a Fields Medal item went from three-of-three
drops to 92). Its cost is measured and accepted: three biomedical mechanism papers
leak as keeps on `holdout`, all scoring ≤50, i.e. below the dashboard threshold.

*Note on a trap this re-opened*: `render_goals_block` splices each goal's
`description` verbatim into **tier 1**, which has no score field. A first
formulation of the disqualifier list stated "these belong in the 0-44 band", and
tier 1 began quoting it as a drop reason. Any score-shaped instruction written
into `goals.yaml` will degrade into a drop instruction at tier 1.

### Remove goal 1's score cap instead of rewriting tier 1

Two ways existed to stop tier 1 dropping flagship releases. Both were measured on
`holdout`, and they are not equivalent:

| | industry items reaching tier 2 | held-out gap | held-out false keeps |
| --- | --- | --- | --- |
| rewrite tier-1 drop categories | 12/12 | +1.9 | **15** |
| remove goal 1's cap, tier 1 untouched | **12/12** | **+9.3** | **9** |

The second is strictly better and touches one sentence instead of a whole prompt
section. The mechanism: `render_goals_block` splices each goal's `description`
verbatim into tier 1, which has no score field, so `命中也不得 ≥70` degraded into a
drop instruction — and `产品与资本通稿（…集成发布，即便来自顶级实验室）` was
explicit licence to drop an Anthropic or Moonshot launch. Removing both rescued
AMD's 2nm launch (→88), Kimi K3's capacity story (→83), Ling-3.0 (→64) and the
chip-selloff story (→58) **without loosening a single drop rule.**

The lesson generalises: when tier 1 is over-dropping, look in `goals.yaml` before
touching the filter prompt. A score-shaped sentence there is a drop instruction
there.

### Do not ship the tier-1 filter rewrite

Rewriting tier-1's drop categories around event type rather than headline diction
looked like a clear win on the adversarial set — false drops fell and the
guardrail bucket held at 16/17 throughout. On `holdout` it raised false keeps from
4 to 16 and cut the pass rate from 75% to 40%.

The guardrail was the failure: 17 items of gold prices, Fed commentary, celebrity
divorce and Java release notes. It never failed, so it measured nothing. The real
drop distribution is vendor PR that looks like a launch and mechanism papers that
look like breakthroughs.

Reverting tier-1 while keeping the tier-2 work recovered most of it: false keeps
15 → 10, gap still positive at +3.8. The residual 3 are the science goal's known
cost. **The two layers are separable, and only the tier-2 half generalised.**

### Keep the eval tables out of `bootstrap_db.py`

They carry no runtime behaviour, so production has no reason to hold them. Written
into `core-database` as an explicit requirement so nobody later "fixes" bootstrap
to create them.

## Risks / Trade-offs

**The gap is now +3.8 but the noise floor is ~9** → The ordering fix is real on
the mean but any individual item's placement is not reliable. Do not promise
per-item behaviour. Re-measure with `--repeats 3` minimum after any further edit.

**Held-out pass rate is 65% against production's 75%** → Precision is genuinely
worse than the original prompts, driven by 10 false keeps. Mitigated by the fact
that only 3 of them clear score 65 and reach the user; at the dashboard threshold
the new prompts surface 11 industry signals against production's 10. The trade is
+1 industry signal for +3 sub-threshold noise rows. If that proves unacceptable in
use, the science goal is the cheapest thing to drop (3 of the 10).

**Papers were compressed as a class, not just narrow ones** → The paper mean fell
83.0 → 58.7, which also demotes good papers. Held-out visible paper signals went
2 → 1. Accepted deliberately: the user's stated preference is industry landing
evidence over methodological quality.

**One prompt clause never took effect** → "A paper may not exceed 58 unless
someone outside the author list used it" had no measurable effect across three
variants; the worst offender stayed at 78–79. It is retained because it is
harmless and states intent, but it must not be relied on. A hard gate belongs in
`_apply_ceilings` in `stages/tier2.py`, not in prose.

**Dedup is score-blind and FIFO** → `radar_pushed_topics` is claimed by whichever
item is processed first (oldest `published_at`), and 8 of 21 existing duplicate
rows already outscore the item that claimed their topic. Rescuing more items makes
this more visible. Out of scope here; a separate fix would promote the
higher-scoring row on a duplicate verdict.

**Prompt length grew** → `goals.yaml` alone went from ~3,046 to ~4,096 characters
in the rendered block, and it is prepended to every tier-1 batch call. Measured no
regression on the shared 54 items when the fourth goal was added, but this budget
is finite on a 4096-token-capped structured agent.

## Migration Plan

Ship and verify in three stages rather than one commit. Shipping together makes a
keep-rate anomaly indistinguishable between layers.

1. **`goals.yaml`** — add the fourth goal. Measure keep rate against the ~40%
   baseline and confirm the Fields Medal / neural-prosthesis items now survive
   tier 1.
2. **`prompts/agents/radar_tier2_impact.md`** — the scoring rewrite. Measure the
   paper-versus-industry gap on `focus`, then validate on `holdout`.
3. **`fetch.py` + tests** — HTML flattening and the `content_status` threshold,
   with the companion prompt clause already in place from stage 2. Requires a
   fresh `--label-set` if the old content is to be kept as a control.

Rollback is per-file: each stage is an independent text or code change with no
schema migration and no data rewrite. The existing 505 analysed rows are unaffected
by any stage.

## Open Questions

- **Should `DEFAULT_MIN_SCORE` rise from 65 to 70?** Note the direction — earlier
  in this work the answer looked like *lowering* it to 60, because the scoring
  rewrite alone pushed the whole distribution down. Removing goal 1's cap moved
  the industry mean the other way, 57.8 → 67.7, so the useful cut point moved up
  instead. At 65 the shipped config surfaces 11 industry / 1 paper against
  production's 10 / 2 with 4 noise rows; at 70 it surfaces 10 industry against
  production's 6, with 3 noise rows. 70 is the strongest operating point and it is
  not the current default. Needs the user's judgement and belongs in a dashboard
  change — do not bundle it here.
- **Is the score worth keeping as a 0-100 integer?** Correlation with independent
  labels is 0.53 and the reliable resolution is roughly three buckets. A coarse
  label mapped to numbers in code would match output granularity to actual
  reliability.
- **Should the paper ceiling move into `_apply_ceilings`?** It would then bind,
  but tag vocabulary is free text (`list[str]`, no enum) and the model already
  violates the existing `opinion` / `frontier-voice` exclusivity in 3 of 7 cases,
  so a code gate keyed on tags is only as reliable as the tagging.
