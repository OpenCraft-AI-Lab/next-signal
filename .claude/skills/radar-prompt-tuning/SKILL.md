---
name: radar-prompt-tuning
description: Measure-first workflow for changing info-radar's scoring behaviour — the tier-1 filter prompt, the tier-2 impact prompt, or configs/info_radar/goals.yaml. Use this skill whenever the user says the radar is scoring things wrong (too many papers, missing industry news, noise getting through, a score that looks too high or too low), asks to tune / adjust / improve any radar prompt or the goals file, or wants to evaluate whether a prompt change actually helped. Also use it before shipping any edit to those three files. Do NOT hand-edit radar prompts without it — every intuitive fix tried without measurement in this project made things worse.
license: MIT
metadata:
  author: paca
  version: "1.0"
---

# Tuning info-radar's scoring (measure first)

Changing these three files changes what the user sees every day, and the
feedback loop is invisible without measurement — a prompt edit that reads
obviously-correct routinely makes the system worse. This skill exists because
nine rounds of tuning were done here the hard way, and most of the intuitive
moves were wrong. The rules below are each backed by a number from that run.

The files under management:

- `prompts/agents/radar_tier1_filter.md` — keep/drop, title + description only
- `prompts/agents/radar_tier2_impact.md` — summary / impact / score / tags
- `configs/info_radar/goals.yaml` — spliced **verbatim into both tiers** by
  `render_goals_block`

Write reports to the user in Chinese (this project's maintainer works in
Chinese) unless they switched to English.

## Iron rules

**1. Never ship a prompt change measured only on the set you tuned against.**
The one time this was skipped, four rounds of tuning climbed from 26/54 to 38/60
on the tuned set while measuring 40% on held-out against production's 75%, with
false keeps rising 4 → 16. Hold out a labelled set before the first change, not
after the fourth.

**2. Label the held-out set independently of whoever wrote the prompts.**
Spawn several agents that read *only* `goals.yaml` and the items, explicitly
forbidden from reading `prompts/` (circular) or existing eval label sets
(anchoring). Keep only items where they agree; surface disagreements to the user
rather than deciding for them.

**3. Establish the noise floor before interpreting any delta.**
`local_structured` runs at temperature 0.2. Re-running an identical item with an
identical prompt moves its score by **~9 points on average, up to 63**. Any
rubric mechanism finer than that is unmeasurable — the old "three axes of
±3" scoring machinery was deleted for exactly this reason after seven rounds
showed no measurable effect. Always run `--repeats 3` minimum and report the
spread alongside the result.

**4. One change per run.** Bundled changes cannot be attributed. Two sub-parts
of a single "fix" here had opposite effects: stripping HTML in `fetch.py` was
+1.0, while honestly marking thin content `fallback` was −5.3. Shipped together
they read as "no effect" and the good half would have been thrown away.

**5. Guardrails must be hard negatives.** A drop-bucket made of gold prices,
Fed commentary, celebrity divorces and Java release notes held at 16/17 through
every round and proved nothing — the real drop distribution is vendor PR that
looks like a launch, and mechanism papers that look like breakthroughs. If the
guardrail never fails, it is not measuring anything.

**6. Measure what the user actually sees.** Bucket pass rates were the primary
metric for seven rounds and they did not align with the user's experience. The
metric that did: sweep the dashboard threshold (`DEFAULT_MIN_SCORE`, currently
65 in `dashboard/lib/radar/filter-shared.ts`) and count, at each cut point, how
many gold-keep items are visible versus how many gold-drop items leak. A "false
keep" scoring 35 never reaches the user; counting it as a failure overstates the
harm. Report signal-vs-noise at several thresholds, and report composition
(industry vs paper) not just totals — a single threshold can invert the
conclusion.

## Workflow

### 1. Reproduce the complaint as a number

Query the existing corpus before touching anything. Mean score by tag, by feed,
and the funnel (`items → keep → score ≥ threshold`) usually locate the problem
in one query. Confirm the user's report is real and quantify it — the original
complaint here ("too many papers") measured as `paper` 79.9 vs `release` 60.2,
and one feed contributing 32% of input but 4.8% of visible output.

### 2. Read the mechanism, including goals.yaml

`render_goals_block` splices each goal's `description` **verbatim into tier 1**,
which has no score field. A sentence like "命中也不得 ≥70" therefore degrades
into a drop instruction. Check `goals.yaml` before blaming the prompts — it was
the deepest root cause here, and the same trap was re-introduced later by a
disqualifier list that tier 1 began quoting as its drop reason.

### 3. Build a focused set, then a held-out set

Keep the focused set small and entirely on the decision boundary. Trivially
correct drops are padding. Do not include items you cannot confidently label —
if two items are structurally identical at title level and you would rule them
differently, neither belongs in the set.

Bucket names drive the report. `IND-surface` and `PAP-low` activate the
pairwise industry-vs-paper ordering metric in `scripts/radar_eval.py`.

### 4. Iterate, one change per run, checking the guardrail first

Read the guardrail bucket before the target bucket. A target-bucket gain bought
with a guardrail regression is not a gain.

### 5. Validate on held-out before recommending anything

Compare against production's existing `radar_analyses` rows — the baseline is
free, because production already scored every item. Then run the threshold
sweep. Recommend shipping only if held-out holds up.

## Known traps in this codebase

**A framing sentence beats any number of patches below it.** Seven rounds failed
to move paper scores because the `score` field opened with *"anchored on EVIDENCE
quality"*. Rewriting the band definitions underneath it did nothing; changing
that one sentence to *"分数衡量的是这件事该多大程度改变用户的判断或行动"* moved the
worst offender from 87 to 78 and flipped the paper-vs-industry gap from −25.2 to
positive. When a patch does not take, look upward for a sentence contradicting
it.

**Mechanical steps work; exception clauses do not.** On this model under
xgrammar constrained decoding, "mentally delete the venue suffix" and a
carve-out for "named product with a model number" both failed three times.
Restating them as a numbered Step 0 that runs *before* the categories worked
immediately. Prefer an ordered procedure over a rule with exceptions.

**Prefer a required question over a category description.** Papers scored with
*zero* variance across repeats while industry items swung up to 63 points — the
model has a stable internalised prior for "conference paper" and none for
"a founder tweeted support". Giving industry items a forced mechanical question
("what can an outsider obtain right now?" → four options → a floor score) cut
mean spread from 11.6 to 9.8 and flipped the gap positive.

**The model's knowledge cutoff predates the feed.** Unfamiliar model names and
future-looking dates get scored as fabrication — one frontier model launch was
tagged `fiction` / `misinformation` and scored 0 / 15 / 15 across three repeats,
with the impact text arguing it contradicted known reality. Any tier-2 prompt needs
the standing instruction that feed contents are real and the model's job is
significance, not existence.

**Paywalled publishers return a lede, not an article.** One feed's "full
content" measured 164 characters, 113 of them a single `<img>` tag, and was
labelled `content_status='full'`. Check actual fetched lengths per feed before
concluding the prompt is at fault.

**Score ceilings expressed as prose get rationalised around.** "A paper may not
exceed 58 unless someone outside the author list used it" never once took effect
across three variants. Hard gates belong in code (`_apply_ceilings` in
`stages/tier2.py`) or as a disqualifier checklist, not as a preference.

**tier-1 drops are the only irreversible loss** — `mark_seen` fires before
fetch, and `radar_analyses` is `UNIQUE(radar_item_id)` with
`ON CONFLICT DO NOTHING`. But do not over-correct: on a representative sample,
false keeps outnumbered false drops 4:1, so loosening tier 1 is expensive.

## Commands

Run everything through Docker (per CLAUDE.md), bind-mounting the source so
prompt edits take effect without a rebuild:

```bash
M=(-v "$PWD/scripts:/app/scripts:ro" -v "$PWD/configs:/app/configs:ro" \
   -v "$PWD/prompts:/app/prompts:ro" -v "$PWD/src:/app/src:ro")

docker compose run --rm --no-deps "${M[@]}" dashboard \
  python scripts/radar_eval.py init                        # once
docker compose run --rm --no-deps "${M[@]}" dashboard \
  python scripts/radar_eval.py load --cases eval_cases_focus.yaml
docker compose run --rm --no-deps "${M[@]}" dashboard \
  python scripts/radar_eval.py run --variant NAME --label-set focus --repeats 3
docker compose run --rm --no-deps "${M[@]}" dashboard \
  python scripts/radar_eval.py report --variant NAME
```

Existing label sets: `focus` (36 items, decision boundary), `v1`/`v2` (60 items,
adversarial, v2 has post-fetch-fix content), `holdout` (55 items, independently
labelled — **do not tune against this one**).

Constraints:

- **Never run two evals concurrently.** OMLX's concurrency cap is per-process,
  so two runs put four requests on a two-slot server and trip the 507/timeout
  path, polluting results. Chain them instead.
- Article content is snapshotted at `load` time and replayed, so a variant
  comparison isolates the prompt. Changing `fetch.py` requires a fresh
  `--label-set` to keep the old content as a control.
- `prompt_digest` on each run row is a hash of both prompts plus `goals.yaml` —
  use it to prove which text produced which numbers. Two runs with the same
  digest differ only in sampling.
- A run of 36 items × 3 repeats takes roughly 25–30 minutes; 60 items, 35–50.

## Before shipping

- Adding a goal to `goals.yaml` is normal user configuration — no OpenSpec
  change needed.
- Changing agent behaviour or a documented contract **is** non-trivial: run
  `/opsx:propose`. Known tripwires — the `opinion` ≤65 clamp is a spec scenario
  (`openspec/specs/info-radar-analysis/spec.md`), and so is
  `content_status='full'` on any successful fetch.
- Doc sync: `docs/modules/info_filter.md` documents the ceiling and the band
  arithmetic, and its Chinese mirror `docs/zh/modules/info_filter.md` must move
  in the same change.
- Report honestly. State which changes had no measurable effect and which
  regressed. A round that produced no improvement is a finding, not a failure to
  hide — ruling out a suspect (tier-1 batch size was measured irrelevant) is
  worth as much as a fix.
