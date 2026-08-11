## Context

`get_embedder(profile_name="local")` reads `configs/models.yaml`'s `embedders:`
section, then ignores everything about the resolved profile except `model_id`
and posts at `omlx_endpoint()`. The provider field is `Literal["omlx"]` and the
code says as much. This change adds the missing dispatch, but provider selection
cannot be treated like ordinary scalar configuration because an embedding and
the identity persisted beside it form one correctness unit.

The surrounding constraints:

- **One consumer.** `workflows/info_radar_analysis/stages/dedup.py` is the only
  caller. GBrain embeds through its own CLI and is untouched.
- **One permanent storage site.** `radar_pushed_topics.embedding` is
  `vector(1024) NOT NULL`. Unlike `radar_items`, this table has no sweep and no
  foreign key into the 30-day table.
- **Vectors from different spaces are not comparable.** Matching dimension and
  model-name strings do not establish a shared vector space. Weights, tokenizer,
  pooling, quantization, or output processing can differ behind a generic
  endpoint while its advertised model name stays the same.
- **The current schema has no provenance.** `embedders.local.model_id` has always
  been operator-editable, so migration cannot prove that every historical row
  came from the shipped Qwen default.
- **The current ANN index spans the whole table.** A SQL filter can remove rows
  from the final result, but an approximate index still generates candidates
  from shared centroids before that filter. Mixing spaces therefore affects
  recall even when cross-space rows are not returned.
- **The settings pattern already exists.** `engine.json` plus the Python and
  Dashboard preference loaders provides the shape for live operator state, but
  embedding needs a per-item snapshot rather than independent re-reads.
- **The unattended path matters.** The scheduler is long-running and runs the
  dedup gate with nobody watching. State files can be re-read live; `.env` edits
  cannot change an already-running process environment.

## Goals / Non-Goals

**Goals:**

- Resolve provider, model, endpoint, credential, and vector-space identity once
  per item, with no code change to switch between items.
- Support `omlx`, `openai`, and one generic OpenAI-compatible API root.
- Make every newly stored vector self-describing and prevent every cross-space
  cosine comparison, including during a mid-batch settings change.
- Keep `vector(1024)` stable and preserve every historical row without guessing
  its provenance.
- Keep secrets out of `~/.next-signal/` and out of the browser.
- Make the cost and data-egress consequences of a hosted embedder visible before
  selection.

**Non-Goals:**

- An embedder fallback chain.
- Automatically re-embedding or automatically relabelling historical rows.
- Batch embedding, request-level retries, or a local vector cache.
- Configurable vector dimensions.
- A second embedder consumer.
- Hot-reloading edits to `.env` inside an existing process/container.

## Decisions

### D1. Resolve one immutable embedder snapshot per item

`get_embedder()` returns a `ResolvedEmbedder` containing the resolved provider,
model, stable identity, and an `embed(text) -> list[float]` callable that captures
the endpoint and credential selected for that item. The state file and process
environment are read once when this object is constructed.

The dedup stage uses the snapshot's identity for its vector search and returns
that same identity in `DedupOutcome` beside the vector. The runner passes the
outcome's identity to `insert_topic`; it never re-opens `embedding.json` during
persistence.

This closes the time-of-check/time-of-use gap. If the settings file changes while
one request is in flight, that item finishes search and persistence under its
original snapshot; the next item receives the new selection. A vector can never
be labelled with state read after the vector was produced.

The alternative — returning only a callable and exposing a separate
`active_identity()` helper — looks smaller but makes correctness depend on two
independent live reads. Atomic state-file writes prevent torn JSON, not a valid
old read followed by a valid new read.

### D2. Use an explicit vector-space identity for generic endpoints

Built-in identities are:

- `omlx:<model_id>`
- `openai:<model_id>`

The OpenAI-compatible section additionally requires `space_id`, and its identity
is `openai_compatible:<space_id>`. `space_id` is a user-managed logical name,
validated against `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`. It must change whenever
weights, tokenizer, pooling, quantization, requested dimensions, or other
vector-producing behavior changes.

A generic `model_id` is not enough. Two endpoints can advertise the same name
while producing unrelated vectors; comparing them can create both false misses
and false matches. A false match is the dangerous direction because it can
suppress a genuinely novel item. The explicit id makes that trust decision
visible instead of silently deriving it from an endpoint's claim.

The physical base URL remains outside the identity. Moving one logical service
from `127.0.0.1` to `host.docker.internal` should not park its memory. The
operator retains the same `space_id` for a transport-only move and changes it for
a vector-space change.

### D3. Label unprovable history `legacy:unknown`

Existing rows predate provenance. Although the shipped config names
`Qwen3-Embedding-0.6B-8bit`, `configs/models.yaml::embedders.local.model_id` has
always been editable, so bootstrap cannot prove which model produced an existing
row. Hardcoding the shipped default would mislabel customized installations and
reintroduce the exact cross-space comparison this change is meant to prevent.

Migration therefore adds the column with a temporary `legacy:unknown` default,
backfills all existing rows to that sentinel, then drops the default:

```sql
ALTER TABLE radar_pushed_topics
  ADD COLUMN IF NOT EXISTS embedder TEXT NOT NULL DEFAULT 'legacy:unknown';
ALTER TABLE radar_pushed_topics ALTER COLUMN embedder DROP DEFAULT;
```

No active provider has that identity, so legacy rows are retained but excluded
from automatic dedup. An operator who independently knows the historical model
may explicitly relabel those rows with a documented SQL update; the application
does not guess or offer a one-click migration.

This means a one-time effective-memory reset for pre-change rows. It is the safe
cost of adding provenance after the fact. Rows written after migration remain
parked/restored normally when the operator switches away and back.

### D4. Fix the dimension at 1024 and validate the complete vector

`ResolvedEmbedder.embed()` accepts only a JSON array containing exactly 1024
finite numeric values. It raises `RuntimeError` with an actionable reason for a
wrong length, a non-numeric element, `NaN`, or infinity. It never truncates,
pads, normalizes, or stores a partially valid response.

The `openai` and `openai_compatible` requests send `dimensions: 1024`; OMLX does
not, because the shipped route has no such parameter and the shipped Qwen model
already emits 1024 values.

This keeps the database column stable. It excludes fixed-width incompatible
models such as `text-embedding-ada-002` and local models whose native output is
not 1024. Rewriting the column dimension on a settings click would destroy or
strand history and is out of scope.

### D5. Use exact provider-scoped cosine search at the current scale

`ann_search_topics` is renamed `search_topics`. Its query filters by the resolved
identity and then orders that subset by cosine distance, returning the top five
within the configured threshold. Bootstrap drops the existing
`radar_pushed_topics_embedding_idx` IVFFlat index and creates a normal B-tree
index on `embedder`.

The table is expected to hold hundreds to low thousands of rows. An exact scan
of one identity's subset is cheap at that scale and has perfect recall. It also
makes the central invariant literal: vectors outside the selected space do not
participate in candidate generation at all.

Keeping one IVFFlat index over all identities was rejected. Approximate-index
filtering occurs after candidate generation, so shared centroids let one vector
space affect another's recall. `REINDEX` does not solve that while both spaces
remain in the same index. If this table eventually outgrows exact search, the
future scaling path is list partitioning by identity with an ANN index per
partition, backed by measured recall tests.

### D6. Keep a separate `embedding.json`, with no fabricated generic default

`engine.json` has job affinity and fallback semantics that embedding does not.
Embedding state therefore lives in `~/.next-signal/embedding.json`, independently
written from language, schedule, engine, and coding-agent state.

`configs/models.yaml` remains the baseline for the two providers for which the
repo has real defaults:

- `embedders.local` supplies OMLX's model and the fresh-install selection.
- `embedders.openai` supplies OpenAI's model.

`openai_compatible` has no truthful universal endpoint, model, key-variable
name, or space id. Its section is optional. When absent, the Dashboard renders
an empty configuration pane; the pipeline rejects selecting that provider until
all four fields are saved. Once the section exists it must be complete — there
is no field-level partial merge against invented literals.

For OMLX and OpenAI, a partial state section inherits missing values from the
corresponding `models.yaml` baseline. An entirely absent state file selects the
local baseline.

### D7. Store only an env-var name, and define URL/credential reload semantics

The state file never stores an API key:

- OMLX uses the centralized OMLX resolver.
- OpenAI reads `OPENAI_API_KEY`.
- OpenAI-compatible stores `api_key_env` and reads the named process variable.

The compatible `base_url` is an API root such as `https://host.example/v1`;
the client appends `/embeddings`. Validation uses parsed URL components, permits
only `http`/`https`, requires a host, and rejects username, password, query, and
fragment components so credentials cannot be smuggled into state through the
URL. A value already ending in `/embeddings` is rejected as an endpoint rather
than an API root. `api_key_env` is validated as
`^[A-Z][A-Z0-9_]{0,63}$`.

Credential lookup happens when `get_embedder()` resolves the item snapshot. This
means a missing key does not prevent process startup and a programmatic change to
that process's environment is visible on the next item. It does **not** mean an
edit to `.env` mutates a running process. Host processes must restart and Compose
services must be recreated after `.env` changes; the settings UI and operations
docs state this explicitly.

The Dashboard receives credential presence booleans only. No secret value
crosses the server/client boundary.

### D8. Do not define an embedder fallback

The LLM engine can fall back because its providers' answers are substitutable.
Embedding providers are not: falling back changes vector space and silently
parks the selected provider's dedup memory.

`embed()` therefore raises on missing credentials, transport errors, non-2xx
responses, malformed JSON, or invalid vectors. The existing dedup policy catches
that failure, logs it, persists the analysis as `novel`, and inserts no topic
row. No other provider is attempted.

### D9. Acquire concurrency by the resolved provider

Each snapshot's `embed()` call acquires `ProviderConcurrency` using the provider
captured in that snapshot. OMLX embedding therefore shares the local GPU cap
with OMLX LLM inference. OpenAI and OpenAI-compatible calls use their own keys
and never consume the local slot.

### D10. Mirror the settings interaction without sharing an abstraction

The Embedding section reuses the engine section's provider cards, pane actions,
save hook, and status-dot vocabulary, but does not factor both sections into a
parameterized parent.

OMLX and OpenAI have valid baselines, so their cards commit selection on click
against the last saved pane values. A generic endpoint has no baseline: clicking
an unconfigured card opens its pane but performs no write, and Save atomically
stores the complete section and selects it. Subsequent switches to that saved
provider commit on click like the other cards.

The section displays:

- the exact active vector-space identity;
- credential presence, never the value;
- that switching parks current dedup memory and switching back restores rows
  written under that identity;
- that pre-change `legacy:unknown` rows remain parked unless explicitly relabelled;
- that a hosted provider sends summaries off-machine and may spend money on
  every unattended item.

No new UI primitive is introduced, so `/design` needs no entry.

### D11. Doctor reports configuration, not reachability

`next-signal doctor` resolves the current selection and identity, validates the
state, and reports whether the required credential exists in the current process
environment. It does not make an embedding request. Invalid state is rendered as
a failed check rather than taking doctor down.

The output also uses accurate reload guidance: if a variable was added to
`.env`, restart the host process or recreate the Compose service before expecting
the check or scheduler to see it.

## Risks / Trade-offs

**Existing dedup memory becomes inactive once** → Accepted. The old schema did
not record enough information to label it safely. Rows remain available for an
operator-confirmed manual relabel; no data is deleted.

**A switch starts with little or no memory under the new identity** → Accepted
and stated in the UI. Switching back restores post-migration rows written under
the previous identity.

**Exact search eventually becomes slow** → At the measured table size it is the
simplest correct implementation. Partitioned ANN is the documented future path,
triggered by measurement rather than added speculatively.

**An operator reuses a generic `space_id` after changing the model** → The UI and
docs define when it must change and display it verbatim. The system cannot hash
remote weights it cannot inspect; requiring an explicit logical id is the
strongest enforceable contract.

**A hosted embedder spends money and sends summaries off-machine** → Both effects
are shown before selection, covered in bilingual operations/deployment docs, and
included in the Docker verification cost map.

**A missing hosted key makes every item novel** → Each failure is logged, the
settings section shows credential absence, and doctor fails the check. The docs
also state that `.env` edits require process/service restart.

**A stale `add-coding-agent-stage-adapter` sentence contradicts this change** →
That change's `core-models` delta says embedder identity and dimensionality stay
sourced from `configs/models.yaml`. The task list requires reconciliation before
either change archives.
