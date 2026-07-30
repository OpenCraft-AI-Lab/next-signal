## Why

info-radar systematically ranked academic papers above industry events, so the
things the user most wanted to see were the things least likely to surface. On
the 505-item corpus, `paper`-tagged items averaged 79.9 and `release`-tagged 60.2;
one business feed contributed 32% of all input and 4.8% of everything visible at
the dashboard's default threshold; a frontier open-weights launch that moved US
chip equities produced nine articles, of which exactly one was visible.

Measurement located three independent causes, none of which was the one
originally suspected:

1. The `score` field opened with *"anchored on EVIDENCE quality"*, which rewards
   methodological rigor — a property papers have and news does not. Seven
   attempts to fix this by rewriting the band definitions underneath that
   sentence had no measurable effect.
2. The local model's training cutoff predates the feed, so it scored genuinely
   new launches as fabrications — one was tagged `fiction` / `misinformation` and
   scored 0 / 15 / 15 across three repeats.
3. `fetch.py` labelled a paywalled publisher's 164-character lede as
   `content_status='full'` (113 of those characters were a single `<img>` tag),
   and one feed's article bodies were 91% markup, so the 16k truncation fed
   tier-2 roughly 1,400 characters of actual prose.

On an independently-labelled 55-item held-out set — labelled by agents that read
only `goals.yaml`, forbidden from reading the prompts — the paper-versus-industry
mean score gap moved from **−25.2** (papers 83.0, industry 57.8) to **+3.8**
(papers 58.7, industry 62.5).

## What Changes

- **`configs/info_radar/goals.yaml`** — add a fourth goal, `science_breakthrough`,
  so major non-AI science and medicine milestones score on their own merit. It
  carries a disqualifier checklist (animal/cell subjects, hedged conclusions, no
  already-taken clinical or engineering action) so routine mechanism papers do
  not ride in with it.
- **`prompts/agents/radar_tier2_impact.md`** — re-key `score` from evidence
  quality to consequence, with rigor explicitly demoted to something reported in
  `impact` rather than added to the score. Add a mechanical "what can an outsider
  obtain right now?" step that sets a floor for non-paper items. Replace the
  three-axis ±3 adjustment with a concrete anchor table plus an explicit ordering
  constraint. Add a standing instruction that feed contents postdate the model's
  training data and are real. Add guidance for scoring lede-only content.
- **`src/paca/workflows/info_radar_analysis/stages/fetch.py`** — flatten feed
  HTML to text before truncation, and stop reporting `content_status='full'` for
  a body that contains less than 200 characters of prose. **BREAKING** for the
  documented `content_status` contract: a successful fetch that returns only a
  lede now reports `fallback`.
- **Removed**: the three-axis ±3 within-band adjustment. Measured span is ±9,
  identical to the run-to-run sampling spread, and 36% of observed scores fell on
  values that arithmetic cannot produce — the model was never executing it.
- **Supporting tooling, outside the runtime contract**: `scripts/radar_eval.py`
  (offline eval harness), three labelled eval sets under `configs/info_radar/`,
  and `.claude/skills/radar-prompt-tuning/SKILL.md`.

Deliberately **not** included: the tier-1 filter prompt. A rewrite of its drop
categories raised held-out false keeps from 4 to 16 while the guardrail bucket
showed no regression, and it has been reverted. That is recorded here so the next
attempt does not repeat it.

## Capabilities

### New Capabilities

None. The eval harness is a development script, not part of the AgentOS
capability surface, and adds no agent, tool, workflow, or CLI subcommand.

### Modified Capabilities

- `info-radar-analysis`: the tier-2 fetch requirement changes — content is
  flattened to text before the 16k truncation, and `content_status` reflects
  whether a real article body was obtained rather than merely a non-empty
  response. The tier-2 agent requirement gains a scoring-semantics constraint.
- `core-database`: records that the `radar_eval_*` tables are created by the eval
  script and deliberately **not** provisioned by `scripts/bootstrap_db.py`, so a
  future reader does not "fix" bootstrap to create dev-only tables in production.

## Impact

- **Code**: `stages/fetch.py` (HTML flattening, length threshold),
  `tests/test_info_radar_analysis_fetch.py` (three fixtures were shorter than the
  new article threshold; two cases added).
- **Behaviour**: every future `paca info-radar analyze` run. The existing 505
  analysed rows are frozen — `radar_analyses` is `UNIQUE(radar_item_id)` with
  `ON CONFLICT DO NOTHING` and `mark_seen` fires before fetch, so this change
  cannot retroactively rescore them.
- **Dashboard**: none required, but note that industry items now average 62.5
  against a `DEFAULT_MIN_SCORE` of 65, so the ordering fix lands just under the
  visibility line. A threshold sweep on held-out data is included in design.md;
  changing the default is a separate decision.
- **Docs**: `docs/modules/info_filter.md` documents the ±3 band arithmetic and the
  ≤65 ceiling and must be updated, together with its Chinese mirror
  `docs/zh/modules/info_filter.md`.
- **Dependencies**: none added. The HTML flattening uses `re` and `html.unescape`.
