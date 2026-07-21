## ADDED Requirements

### Requirement: Recap range is bounded by `analyzed_at` in the radar timezone

A recap SHALL select from `radar_analyses` joined to `radar_items` using `timezone(<radar-tz>, ra.analyzed_at)::date BETWEEN <since> AND <until>`, inclusive on both ends, where the timezone is the same `INFO_RADAR_TIMEZONE` value (default `America/Los_Angeles`) used by the radar day grouping. `published_at` MUST NOT be used to bound the range — it is nullable and would disagree with every other date shown on the radar page. A recap whose `until` precedes its `since` SHALL raise `RuntimeError` before any query.

#### Scenario: range matches the day rows it summarizes

- **WHEN** a recap is generated for `since` = 2026-07-13 and `until` = 2026-07-19
- **THEN** the selected items are exactly those whose `analyzed_at` falls on local dates 2026-07-13 through 2026-07-19 inclusive, matching the seven per-day groups rendered for that span

#### Scenario: inverted range fails fast

- **WHEN** a recap is requested with `since` = 2026-07-19 and `until` = 2026-07-13
- **THEN** the workflow raises `RuntimeError` naming both bounds and makes no LLM call

### Requirement: Quality gate reuses the radar filter semantics

Candidate selection SHALL restrict to `ra.verdict = 'keep'` and apply the same two gates the radar filter bar exposes: `coalesce(ra.score, 0) >= <min_score>` and, when `novel_only` is set, `ra.dedup_status = 'novel'`. Defaults are `min_score = 0` and `novel_only = false`. Items with `verdict = 'drop'` MUST NOT reach the recap agent.

#### Scenario: dropped items are never recapped

- **WHEN** a range contains 50 analyses of which 30 have `verdict='drop'`
- **THEN** only the 20 `keep` rows are eligible, and the dropped rows are absent from both the LLM input and the persisted counts

#### Scenario: novel-only gate excludes duplicates

- **WHEN** a recap is requested with `novel_only` true over a range containing kept items with `dedup_status='duplicate'`
- **THEN** those duplicate-status items are excluded from selection

### Requirement: Selection caps at the top 60 items by score and reports coverage

When more candidates clear the gate than the cap allows, selection SHALL take the highest-scoring 60 (ties broken by `analyzed_at` descending). The recap SHALL persist both `item_count` (rows actually sent to the agent) and `considered_count` (rows that cleared the gate before the cap). When `considered_count` exceeds `item_count`, consumers SHALL surface that the recap covers a subset. The cap MUST NOT be applied silently.

#### Scenario: wide range is capped and coverage is recorded

- **WHEN** a 30-day recap matches 143 items clearing the gate
- **THEN** the top 60 by score are sent to the agent, the persisted row records `item_count=60` and `considered_count=143`, and the reader is told the recap covers 60 of 143

#### Scenario: narrow range is uncapped

- **WHEN** a range matches 18 items clearing the gate
- **THEN** all 18 are sent, and the row records `item_count=18` and `considered_count=18`

### Requirement: Agent input is summaries, not per-item impact analysis

The recap agent SHALL receive, per selected item, only `id`, `title`, `score`, `tags`, and `summary`. `impact_md` MUST NOT be included — it is the per-item deep dive, and the recap's purpose is synthesis across items rather than concatenation of them.

#### Scenario: impact_md is withheld from the prompt

- **WHEN** the recap payload is assembled for items whose analyses carry non-empty `impact_md`
- **THEN** the serialized agent input contains each item's `summary` and omits `impact_md` entirely

### Requirement: Recap agent runs on `local_structured` with constrained output

The recap SHALL invoke a registered agent named `radar_recap`, declared in `configs/agents/radar_recap.yaml` with `model_profile: local_structured` and `extra: {db: false, shared_context: false}`, its prompt in `prompts/agents/radar_recap.md`, invoked through `paca.agents.loader.build_from_name` and `paca.agents.structured.run_structured`. The agent SHALL return a structured output enforced by OMLX json_schema constrained decoding, shaped `RecapOutput{headline: str, themes: list[Theme]}` where `Theme{title: str, narrative: str, item_ids: list[int]}`. The `local_structured` `max_tokens` cap of 4096 MUST NOT be widened for this agent, nor overridden per-agent.

#### Scenario: agent is loaded from config, not constructed inline

- **WHEN** the recap workflow needs its LLM step
- **THEN** it calls `build_from_name("radar_recap")`, and no `Agent(...)` is constructed inline with hardcoded instructions or model id

#### Scenario: token cap is inherited unchanged

- **WHEN** `configs/agents/radar_recap.yaml` is loaded
- **THEN** it references `model_profile: local_structured` and declares no `max_tokens` override, inheriting the documented 4096 cap

### Requirement: Citations are validated, and unciteable output degrades rather than aborts

After the agent returns, the workflow SHALL validate every `item_ids` entry against the set of ids actually sent. Ids outside that set SHALL be dropped with a logged warning. A theme left with zero valid citations SHALL be dropped. If no theme survives validation, the run SHALL be treated as a failure: the recap is recorded with `status='error'` and MUST NOT be recorded as `done`. Theme count SHALL NOT be hard-enforced — a recap returning more or fewer than the requested 3–5 themes is accepted when its themes carry valid citations.

#### Scenario: hallucinated citation is dropped, recap survives

- **WHEN** the agent returns a theme citing ids `[12, 31, 9999]` where 9999 was never sent
- **THEN** 9999 is dropped with a warning, the theme persists citing `[12, 31]`, and the recap completes as `done`

#### Scenario: theme with no valid citations is dropped

- **WHEN** the agent returns four themes and one cites only ids that were never sent
- **THEN** that theme is dropped and the recap persists the remaining three

#### Scenario: total citation failure is an error, not an empty recap

- **WHEN** every theme returned cites only unknown ids
- **THEN** the row is written with `status='error'` and a message, and no `done` recap with zero themes is persisted

### Requirement: Recap identity is `(since, until, min_score, novel_only)`

`radar_recaps` SHALL carry `UNIQUE (since, until, min_score, novel_only)`. A request whose key already exists and is `done` SHALL be served from the stored row without invoking the agent. Regeneration SHALL be explicit and SHALL upsert the same row rather than appending a new one.

#### Scenario: repeat request is served from cache

- **WHEN** a recap for an existing key in `status='done'` is requested without regeneration
- **THEN** the stored headline and themes are returned and no LLM call is made

#### Scenario: differing quality gate is a different recap

- **WHEN** the same date range is requested once with `min_score=0` and once with `min_score=70`
- **THEN** two distinct rows exist, each generated independently

### Requirement: Status lifecycle drives polling and preserves prior content

`radar_recaps.status` SHALL be one of `'running'`, `'done'`, `'error'`. The workflow SHALL write the row with `status='running'` before invoking the agent, then set `'done'` with `headline`, `themes`, `item_count`, `considered_count`, and `max_analyzed_at` populated, or `'error'` with a message on failure. During a regeneration, previously stored `headline` and `themes` SHALL be preserved while `status='running'` and SHALL remain readable if the regeneration ends in `'error'`. A trigger for a key already in `status='running'` SHALL be a no-op rather than starting a second concurrent generation.

#### Scenario: failed regeneration keeps the previous recap readable

- **WHEN** a `done` recap is regenerated and the agent call raises
- **THEN** the row ends in `status='error'` with a message, and its previously stored headline and themes are still present and renderable

#### Scenario: concurrent trigger does not double-run

- **WHEN** a recap trigger arrives for a key whose row is already `status='running'`
- **THEN** no second agent call is started

### Requirement: Staleness is recorded so cached recaps can be labelled

The recap SHALL persist `max_analyzed_at`, the maximum `analyzed_at` among the items that fed it. Consumers SHALL be able to detect that further analyses have landed in the same range and gate since generation, and SHALL present a cached recap as stale rather than silently regenerating it.

#### Scenario: new analyses in a live range mark the recap stale

- **WHEN** a "last 7 days" recap was generated at `max_analyzed_at` = T, and 5 further items in that range are analyzed after T
- **THEN** reading the recap reports it as stale with a count of 5 newer signals, while still returning the stored recap content

### Requirement: An empty range short-circuits before any LLM call

When no items clear the gate for the requested range, the workflow SHALL NOT invoke the agent and SHALL NOT persist a recap row. It SHALL report the empty result to its caller.

#### Scenario: empty range costs no inference

- **WHEN** a recap is requested for a range in which zero items clear the quality gate
- **THEN** no agent is built, no row is written, and the caller receives an explicit empty-result signal

### Requirement: Workflow is a manual entrypoint, not an AgentOS-exposed runnable

The recap SHALL be declared in `configs/workflows/info_radar_recap.yaml` with `expose.agent_os: false` and an `extra.run_now` pointing at the module entrypoint, following the existing info-radar workflow shells. Implementation SHALL live under `src/paca/workflows/info_radar_recap/`, with SQL confined to its `store.py`. Cadence is not part of this contract.

#### Scenario: workflow is reachable manually

- **WHEN** the operator runs `paca run-workflow info_radar_recap`
- **THEN** the config's `extra.run_now` entrypoint is invoked

#### Scenario: workflow is not bound by AgentOS

- **WHEN** AgentOS loads configured runnables
- **THEN** `info_radar_recap` is not exposed as an AgentOS workflow
