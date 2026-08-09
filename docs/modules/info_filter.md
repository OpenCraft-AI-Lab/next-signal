# Module: info_filter (information collection and filtering)

> **English** · [中文](../zh/modules/info_filter.md)

## What it solves

Collect external information streams and filter them down to signal. The current
instance is **info-radar**: periodically pull the Folo / source CLIs and write
`radar_items`; then a two-tier local-LLM analysis scores relevance and impact and
deduplicates according to `configs/info_radar/goals.yaml`, writing
`radar_analyses` / `radar_pushed_topics`. The dashboard `/radar` page handles
reading and manual triggering.

## Where the code lives

`src/next_signal/collectors/info_radar/` — the LLM-free collector, source CLI →
`radar_items`.
`src/next_signal/integrations/info_radar/` — provider adapters (Folo, YouTube subtitles).
`src/next_signal/workflows/info_radar_pull.py` — the collector's manual-run thin shell.
`src/next_signal/workflows/info_radar_analysis/` — the two-tier LLM analysis pipeline.
`src/next_signal/workflows/info_radar_recap/` — range-scoped recap synthesis.

## Agents

| Agent | Model profile | Used for |
|---|---|---|
| `radar_tier1_filter` | local_structured | Batched tier-1 relevance filter; keep/drop against the goals |
| `radar_tier2_impact` | local_structured | Per-item full-content impact summary / score / tags |
| `radar_dedup_judge` | local_structured | LLM duplicate/novel verdict after pgvector candidate retrieval |
| `radar_recap` | local_structured | Clusters a date range of kept items into 3-5 themed narratives with citations |

## Tools

- info-radar collector: `uv run next-signal info-radar pull [--source NAME]`.
- info-radar analysis: `uv run next-signal info-radar analyze [--limit N] [--source NAME]`.
- info-radar recap: `uv run next-signal info-radar recap --since D --until D [--min-score N] [--novel-only] [--regenerate]`.
- Folo subscriptions inventory: `uv run next-signal info-radar subscriptions --json`.

## External systems

- **Folo CLI** (`next_signal.integrations.info_radar.folo`) — info-radar source, full
  content, subscriptions, and unread counts. Defaults to `npx --yes folocli@0.0.5`,
  overridable with `FOLO_CLI_ARGV`. The subscriptions inventory merges two
  commands: `subscription list` carries no unread field, so `unread list` supplies
  the per-feed counts, joined on `feedId`. The dashboard's `/radar` Ingest first pulls the full text
  with `folocli entry get <source_id>` and stages it as HTML under
  `NEXT_SIGNAL_AGENT_TMP_DIR` before handing off to the knowledge pipeline; non-Folo
  sources still go through `radar_items.url`.
- **YouTube native subtitles** (`next_signal.integrations.info_radar.youtube_subs`) —
  audio-free subtitle enrichment for YouTube items.

## Where data lives

- info-radar raw items: Postgres `radar_items`
- info-radar analyses: Postgres `radar_analyses`
- info-radar dedup memory: Postgres `radar_pushed_topics` (pgvector, 1024-dim)
- info-radar recaps: Postgres `radar_recaps`, one row per
  `(since, until, min_score, novel_only)`
- info-radar goals: `configs/info_radar/goals.yaml` (editable from the dashboard
  `/goals` page)
- info-radar sources: `configs/info_radar/sources.yaml`

## Invariants

- `radar_items.seen_at` is written **only** by the analysis layer; the collector
  writes raw items only.
- `radar_analyses.radar_item_id` is a unique key. Analysis only processes rows
  where `seen_at IS NULL`, and writes `seen_at` only after the analysis row is
  committed — which is what keeps reruns idempotent at any cadence.
- When `configs/info_radar/goals.yaml` is missing or invalid, analysis fails loud.
- If a tier-1 batch response does not match the expected structure, fall back to
  single-item processing; one failing item must never block the batch.
- Items that fail tier-1 or tier-2 get no analysis row and no `seen_at`, leaving
  them for the next run. (Given the unique key on `radar_analyses` and the
  absence of a reanalyze command, writing an empty row would freeze a transient
  failure permanently.)
- Tier-2 `score` measures **consequence** — how much an item should change the
  reader's judgment or actions — explicitly not evidence quality. Methodological
  rigor (ablations, adversarial tests, conference acceptance) is reported in
  `impact` as a reason to trust the numbers and never raises the score on its own.
  The rubric is: a mechanical "what can an outsider obtain right now?" step that
  sets a floor for non-paper items, then an anchor table of named score points
  with an explicit ordering constraint (a flagship release outranks a single-lab
  narrow-task paper regardless of rigor). The ≤65 ceiling for the `opinion` tag is
  backstopped in code (`stages/tier2.py::_apply_ceilings`), and high-signal
  individuals named in the goals are exempted via a prompt-driven `frontier-voice`
  tag.
- No within-band numeric adjustment finer than the sampling spread. A previous
  three-axis ±3 mechanism was removed: it could move a score by at most ±9, which
  is the run-to-run spread at the `local_structured` temperature, and 36% of
  observed scores landed on values its arithmetic cannot produce — the model was
  never executing it.
- The tier-2 prompt tells the agent that feed items postdate its training data and
  are real. Without this, unfamiliar model names and future-looking dates get
  scored as fabrication — one frontier launch was tagged `misinformation` and
  scored 0 / 15 / 15 across three repeats.
- `content_status` reflects whether a real article body was obtained, not merely a
  non-empty response. Feed bodies are flattened to plain text before any length
  test or truncation (one feed measured 91% markup, so the 16k cap was delivering
  ~1,400 characters of prose), and a body under 200 characters of flattened text
  reports `fallback` — a paywalled publisher's lede is not an article. The tier-2
  prompt has a companion clause telling the agent that thin content is missing
  length, not evidence; without it, honest labelling measured −5.3 points because
  an evidence-graded rubric reads absent detail as absent evidence. **The two must
  ship together.**
- When dedup embedding fails, treat the item conservatively as novel — never
  silently drop it.
- A recap is identified by `(since, until, min_score, novel_only)`. A repeat
  request is a cache hit; regeneration upserts that row rather than appending.
- Recap ranges are bounded by `analyzed_at` in the radar timezone, inclusive —
  the same convention the day groups use, so a 7-day recap covers exactly the
  seven day rows beneath it. `published_at` is never used (nullable, and it
  would disagree with every other date on the page).
- The recap agent receives `summary`, never `impact_md`: the recap synthesizes
  across items, and the per-item deep dive would triple prompt size for content
  the themes exist to abstract away.
- Selection caps at the top 60 by score. Both `item_count` and
  `considered_count` are persisted so the reader is told when a recap covers a
  subset — the cap is never applied silently.
- Recap citations to unknown ids are dropped; a theme left with no valid
  citation is dropped; if no theme survives, the run is an error and nothing is
  stored as `done`. A regeneration that fails keeps the previous recap readable.
- `radar_recaps` holds **no** foreign key to `radar_items` — citation ids live
  in the `themes` JSONB so a recap survives the 30-day sweep. Readers render a
  citation whose source is gone as plain text.
- A stale recap (further analyses landed in its range) is **labelled**, never
  auto-regenerated: regenerating on load would turn every visit to a live range
  into a minute of local inference.
- Never dump a whole provider dict into the logger.

## Output language

The `global` language policy (see [core.md](./core.md#output-language))
decides the language of every prose field the reader sees — tier-2 `title`,
`summary` and `impact`, the tier-1 `reason`, and the recap headline / theme
narratives — independent of the article's language and of `goals.yaml`.
`title` is a later addition: it used to pass through untouched from the
source, which left it in a different language than `summary`/`impact` on the
same card; it now goes through the same tier-2 call and the same policy as
the other two. The resolved language comes from the dashboard's live
preference file, falling back to a hardcoded default — not from an env var
(the retired `SIGNAL_OUTPUT_LANG` mechanism).

**Measured** (13 items x 5 repeats, real stages, prompt digests recorded):
tier-2 `summary` came back English 0/64 against Chinese goals with English
articles under the old conditional rule, and 63/63 under the unconditional one.
`impact` and the tier-1 `reason` were already 100% correct in the very same
responses — the field that failed was the one whose spec carried no language
cue. An English target held 65/65 with 0 errors against Chinese goals *and*
Chinese articles.

Post-fix, on the 55-item holdout with a same-night baseline control: English
articles under a Chinese target went from **12/12 English summaries to 0/12**,
with `impact` length, verdict flips and mean score all inside baseline's own
run-to-run range. `scripts/lang_probe.py` measured tier-2 `summary` / `impact`
and the tier-1 `reason` at **0/30 defects in both directions**, no flipping.
`radar_recap` over a window holding 22 English and 153 Chinese summaries
returned Chinese.

**Not measured**: whether tier-2 truncations rose. Baseline measured 2/165
twice; this change measured 8/165 and 4/165 — a 2x spread between identical
configurations, so the metric is too noisy to call at this sample size. They are
premature-EOS under xgrammar, land on the same ~6 fragile items in both arms, and
cost a retry rather than data (a tier-2 failure leaves the item unseen). `radar_dedup_judge` is deliberately exempt — its `reason` is neither
stored nor rendered.

Do not restore a conditional phrasing, and do not add a per-field language
clause: a variant that named `summary` specifically held language equally well
while making output 35% longer and raising truncation failures from 1/65 to 6/65
against the 4096 `max_tokens` cap.

### Dedup and the mixed-language embedding space

The dedup gate embeds the tier-2 `summary`, so what gets embedded now follows
the `global` language policy too. `radar_pushed_topics` is never swept — nothing deletes
from it — so it permanently holds 32 English topics frozen from before the
output-language change, alongside 210 Chinese ones. A Chinese summary of an
English article is therefore ANN-searched against the English embedding of the
same story.

Measured on 5 such pairs (the stored English topic vs the Chinese summary the
same item now produces): cosine distance 0.11–0.26, mean 0.195, against a 0.40
threshold. All pass with margin, so cross-language duplicates are still caught.

Two things follow. The margin is real but finite — anyone tightening
`DEFAULT_THRESHOLD` below ~0.30 should know the space contains cross-language
pairs sitting at 0.26. And `radar_dedup_judge` now sees a Chinese `new_summary`
against possibly-English candidates; it is exempt from the language rule (its
`reason` is neither stored nor rendered) and only ever judges candidates that
already cleared the ANN gate.

## Tuning and evaluation

Scoring behaviour is measured, not adjusted by feel. `scripts/radar_eval.py`
replays the real tier-1 and tier-2 stages over hand-labelled subsets of
`radar_items` and writes to `radar_eval_cases` / `radar_eval_runs` /
`radar_eval_results`. Those tables are created by the script's own `init`
subcommand and deliberately **not** by `scripts/bootstrap_db.py` — they carry no
runtime behaviour. The dedup gate is skipped, because it writes shared production
state and does not affect verdict or score.

Article content is snapshotted at `load` time and replayed, so a variant
comparison is attributable to the prompt rather than to whether folocli answered
that day. Each run records a `prompt_digest` — a hash of both prompts plus
`goals.yaml` — so a set of numbers always traces to the text that produced it.

`scripts/lang_probe.py` is the companion harness for output *language* rather
than score. It replays the same stages plus `knowledge_frontmatter`, writes only
JSON under `NEXT_SIGNAL_AGENT_TMP_DIR/lang-probe/`, and reports the share of
generations that came back in the wrong language. Repeats are mandatory there:
frontmatter's defect is nondeterministic — the same article flipped language
between runs — so a single pass can pass while the bug is present.

Two guards exist because both failures actually happened: the probe asserts the
built agent's composed instructions really name the target language (a bind
mount that silently did not apply once made a fix look like a no-op), and it
refuses to write results if an agent's instructions change mid-run (`prompts/`
is bind-mounted live, so editing a prompt during a run mixes two versions into
one result set). `radar_eval.py` has no such guard — do not edit prompts while
it is running.


Three label sets live in `configs/info_radar/`:

| set | items | purpose |
| --- | --- | --- |
| `eval_cases.yaml` | 60 | adversarial; stacked with known failures |
| `eval_cases_focus.yaml` | 36 | decision boundary only |
| `eval_cases_holdout.yaml` | 55 | independently labelled — **never tune against this** |

The holdout set was labelled by three agents that read only `goals.yaml`, were
forbidden from reading `prompts/` or any existing label set, and only unanimous
items were kept. It is the only set with a claim to being unbiased. The one time
tuning was validated solely on the sets it was tuned against, four rounds climbed
from 26/54 to 38/60 while measuring 40% on holdout against production's 75%.

Process rules, with the measurement that justifies each, are in
`.claude/skills/radar-prompt-tuning/SKILL.md`. Read it before editing any radar
prompt.

**Measured and rejected — do not retry without reading the record:** rewriting
the tier-1 drop categories around event type rather than headline diction. It
looked like a clear win on the adversarial set and its guardrail bucket never
regressed, but on holdout it raised false keeps from 4 to 16 and cut the pass rate
from 75% to 40%. The guardrail was the failure: 17 items of gold prices, Fed
commentary, celebrity divorce and Java release notes, which never failed and so
measured nothing. The real drop distribution is vendor PR that looks like a launch
and mechanism papers that look like breakthroughs.

Also note that the primary metric matters more than it looks: bucket pass rates
were used for seven rounds and did not align with the reader's experience. What
did align was sweeping the dashboard threshold and counting visible signal versus
leaked noise at each cut point — a false keep scoring 35 never reaches the reader.

## Specs and status

Specs: [`openspec/specs/info-radar/`](../../openspec/specs/info-radar/),
[`openspec/specs/info-radar-analysis/`](../../openspec/specs/info-radar-analysis/),
[`openspec/specs/info-radar-recap/`](../../openspec/specs/info-radar-recap/),
[`openspec/specs/dashboard-radar-reader/`](../../openspec/specs/dashboard-radar-reader/).

Current status: info-radar pull, analysis, recap, the dashboard reader, the
goals editor, and the Folo subscriptions table are all in place. There is no background
scheduler — both pull and analysis are **manually triggered**, via
`next-signal info-radar pull|analyze`, `next-signal run-workflow <name>`, or the dashboard
`/radar` page's Pull + Analyze.

The dashboard's `Pull + Analyze` shows **live analyze progress**: after pulling,
the action writes the unanalyzed-item count (the denominator) plus an
`analyzeRunning` flag into `~/.next-signal/radar-state.json`, then spawns
`info-radar analyze` as a **tracked** (not detached) child, flipping
`analyzeRunning` back to false when it exits. The page drives a `done/total`
progress bar from `GET /api/radar/run` (~1.5s polling, where `done` is the
`radar_analyses` row count since the most recent analyze), and throttles
refreshes while running so the `TodayTracker` counts tick live. The bar's running
state is read from `radar-state.json` at page load, so a refresh resumes it. This
covers dashboard-triggered runs only (CLI runs show no progress bar), and
restarting the dashboard can leave an in-flight `analyzeRunning` set until the
next run — best-effort, with the child process and DB writes unaffected.

The `/radar` **Recap** panel picks a range (last 7 days / last 30 days / custom
from–to, presets resolved in the radar timezone) and inherits the filter bar's
score threshold and novel-only setting as its quality gate, so the recap and the
item list describe the same population — and a different gate is a different
cached recap. Generation spawns `next-signal info-radar recap` detached and polls
`GET /api/radar/recap` for the row's `status`; on `running` → `done` the client
calls `router.refresh()` so the server-rendered panel picks up the result.
Failures surface the stored error rather than polling forever. The panel is
omitted entirely under `?export=1`.
