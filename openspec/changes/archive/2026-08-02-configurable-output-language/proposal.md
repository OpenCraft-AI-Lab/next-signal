# Configurable LLM output language

## Why

Every LLM-writing prompt in the repo tells the model to follow the language of
its *input*. The user's goal is the opposite: read a Chinese digest of an
English article without knowing English. Measured on the shipped prompts
(13 items × 5 repeats, real stages, real `local_structured` profile, prompt
digests verified per run):

- `radar_tier2_impact.summary` came out English **0/64** on-target with Chinese
  goals and English articles — and **13/13** in the real `radar_analyses` rows
  already in the database, across two prompt versions and 13 days. `impact` and
  tier-1 `reason` were Chinese **100%** in the *same* LLM calls, because
  `impact` carries a field-level language cue and `summary` carries none.
- `knowledge_frontmatter` has no language rule at all and fails
  **nondeterministically**: 17.9% of titles and 7.7% of summaries came out pure
  English on English articles, with the *same article* flipping between runs.
  A single test pass can miss this entirely.

`summary` is the primary scan text on the radar signal card, so the field that
fails is the field the user actually reads. The fix is small and measured — an
unconditional rule fixed radar 63/63 and frontmatter 0/39 defects — but today
that rule would have to be pasted into every prompt by hand, with no single
place to change the target language.

## What Changes

- Add one setting, `SIGNAL_OUTPUT_LANG` (`zh` | `en`), read at call time. An
  unset value keeps today's behavior; an unrecognized value raises
  `RuntimeError` rather than silently defaulting.
- The agent loader appends a generated output-language rule to an agent's
  instructions. The rule names *prose* fields only and explicitly exempts
  identifier-like fields, so it cannot fight the tag contract.
- **BREAKING**: shared context moves from **prepend** to **append**. Safe in
  practice — all ten production agents currently set
  `extra: {shared_context: false}`; only the `echo` demo agent consumes it — but
  it is a stated spec behavior and therefore a contract change.
- The language rule rides the same append path on its **own** independent gate
  (`extra: {output_language: false}` to opt out), not on `shared_context`.
  Otherwise the ten opted-out agents could only receive it by also swallowing
  the house-rules block, which tells structured-output agents to "prefer one
  sentence over two" and to inline citation URLs.
- Reconcile the shared-context payload, which currently contradicts the fix:
  `00_house_rules.md` says "reply in the language the user wrote in … match
  their last message" *and* claims precedence over per-agent instructions;
  `10_user_profile.md` pins "Working language: English". Neither has a referent
  for these agents — their input is a JSON payload holding an article, not a
  user message.
- Replace the conditional language line in `radar_tier2_impact` and add the
  missing one to `knowledge_frontmatter`, so both are correct even for a caller
  that opts out of injection.
- `tags` are **unchanged**. They stay lowercase English identifiers, enforced in
  code by `_normalize_tags`, which silently drops any tag containing CJK.

Deliberately out of scope: `knowledge_artifact_editor` and
`knowledge_github_cleaner` clean the article body itself — translating it
destroys the original. They opt out permanently.

## Capabilities

### New Capabilities
- `core-output-language`: the `SIGNAL_OUTPUT_LANG` setting, its valid values and
  fail-loud contract, the generated rule text, and which classes of field the
  rule governs versus exempts.

### Modified Capabilities
- `core-agents`: the "Shared context prepended to instructions" requirement
  becomes append, and the loader gains a second, independently gated block that
  appends the output-language rule.
- `info-radar-analysis`: tier-2 `summary` and `impact` acquire a stated output
  language rather than following the article body.
- `knowledge-pipeline`: frontmatter `title` and `summary` acquire a stated
  output language; the existing lowercase-English `tags` contract is restated
  as deliberately exempt.

## Impact

- `src/paca/core/context.py` — append instead of prepend; the module-level
  `_cached` string must not freeze a call-time env read.
- `src/paca/agents/loader.py` — `_compose_instructions` gains the language block
  and its gate.
- `prompts/_shared/00_house_rules.md`, `prompts/_shared/10_user_profile.md` —
  remove the input-mirroring language clauses.
- `prompts/agents/radar_tier2_impact.md`, `prompts/agents/knowledge_frontmatter.md`
  — the two measured prompt edits.
- `configs/agents/*.yaml` — opt-outs for the two body-cleaning agents.
- `.env.example` and the deployment docs — document the new variable.
- Docs are bilingual and must move together: `docs/architecture.md`,
  `docs/modules/info_filter.md`, `docs/modules/knowledge.md` and their
  `docs/zh/` mirrors.
- Not covered by measurement yet: `radar_recap` (cascades off tier-2
  summaries), `radar_dedup_judge`, `knowledge_github_summary`. Their prompts
  carry the same input-mirroring pattern and are folded into this change, but
  only radar tier-2 and frontmatter have numbers behind them.
