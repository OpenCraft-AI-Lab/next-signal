## MODIFIED Requirements

### Requirement: Tier 2 fetches full content via folocli entry get

The tier-2 impact stage SHALL fetch full article content using `folocli entry get <source_id>` for each tier-1-kept item before invoking the tier-2 agent. The fetched content MUST be read from the JSON envelope at `data.entries.content`.

The fetched body MUST be flattened to plain text before any length test or truncation: `<script>` and `<style>` blocks are dropped whole, block-level closing tags and `<br>` become newlines, all remaining tags are removed, and HTML entities are unescaped. Feed bodies are raw publisher markup and have measured as high as 91% tags, which both wastes the content budget and pushes real prose past the truncation point.

If the fetch raises, times out, returns `ok: false`, yields empty content, **or yields fewer than 200 characters of flattened text**, the workflow SHALL fall back to title+description and tag the resulting analysis row with `content_status='fallback'`. `content_status='full'` SHALL be set only when the flattened text reaches 200 characters. A paywalled publisher's lede is not a full article, and reporting it as one makes the tier-2 agent read an absence of detail as an absence of evidence.

Before being sent to the tier-2 agent, content (fetched or fallback) MUST be truncated to the first 16000 characters.

#### Scenario: full content available

- **WHEN** `folocli entry get` returns `ok: true` with a body whose flattened text is at least 200 characters
- **THEN** the tier-2 agent receives the flattened text and the resulting `radar_analyses` row sets `content_status='full'`

#### Scenario: markup is stripped before the tier-2 agent call

- **WHEN** the fetched body contains image tags, entities, and `<script>` blocks around its prose
- **THEN** the tier-2 agent receives only the prose with paragraph boundaries preserved as newlines, and no tag, tracking URL, or script text remains

#### Scenario: lede-only body reports fallback

- **WHEN** `folocli entry get` returns `ok: true` but the body flattens to fewer than 200 characters of text
- **THEN** the workflow uses title+description and writes the analysis row with `content_status='fallback'`

#### Scenario: fetch failure falls back to description

- **WHEN** `folocli entry get` raises a timeout or returns `ok: false`
- **THEN** the workflow logs the failure, calls the tier-2 agent with title+description only, and writes the analysis row with `content_status='fallback'`

#### Scenario: oversized content is truncated before the tier-2 agent call

- **WHEN** flattened content exceeds 16000 characters
- **THEN** only the first 16000 characters are included in the tier-2 agent's input

## ADDED Requirements

### Requirement: Tier 2 `score` measures consequence, not methodological rigor

The `radar_tier2_impact` prompt SHALL define `score` as how much the item should change the user's judgment or actions, and SHALL NOT define it as a measure of evidence quality. Methodological strength — controlled ablations, adversarial tests, conference acceptance, multi-institution authorship — SHALL be reported in `impact` as a reason to trust the item's numbers and MUST NOT raise `score` on its own.

The prompt SHALL state an ordering constraint that a flagship model, chip, or agent release from a frontier lab or major vendor outranks a single-lab narrow-task paper, regardless of which is more rigorous.

The prompt SHALL NOT contain a within-band numeric adjustment finer than the model's run-to-run sampling spread, which measured ±9 points at the `local_structured` temperature. A previous three-axis ±3 adjustment was removed for this reason: 36% of observed scores fell on values its arithmetic cannot produce.

#### Scenario: rigor is reported without inflating the score

- **WHEN** the tier-2 agent analyses a single-lab paper with a clean controlled ablation that no third party has reproduced or adopted
- **THEN** the ablation quality is described in `impact` and does not by itself place the item above a flagship release in `score`

#### Scenario: an unverifiable first-party number still scores on consequence

- **WHEN** a frontier lab publishes open weights with self-reported benchmark numbers that nobody has yet reproduced
- **THEN** `score` reflects the consequence of the weights being available and `impact` states who reported the numbers and how an outsider could check them

### Requirement: Tier 2 treats feed contents as real despite the model's training cutoff

The `radar_tier2_impact` prompt SHALL instruct the agent that feed items postdate its training data and that product names, version numbers, companies, dates, and benchmark names appearing in a feed item are real and already happened. The agent MUST NOT tag an item `fiction`, `rumor`, or `misinformation`, argue in `impact` that it contradicts known reality, or reduce `score`, on the basis that a name or date is unfamiliar. Factual scepticism SHALL be reserved for publisher-self-reported figures that no outside party can check.

#### Scenario: an unrecognised model name is not treated as fabrication

- **WHEN** an item announces a model release whose name and date fall after the agent's training cutoff
- **THEN** the agent scores it on consequence, and neither tags it as fabricated nor cites unfamiliarity as a reason to score it down
