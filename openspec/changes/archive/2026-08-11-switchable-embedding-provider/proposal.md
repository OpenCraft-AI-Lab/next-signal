## Why

`next_signal.core.models.get_embedder` is hardwired to OMLX: the profile schema
declares `provider: Literal["omlx"]`, the function ignores that field and posts
straight at `omlx_endpoint()`, and its own comment concedes there is no dispatch
because there is nothing to dispatch to. The repo already carries an
`OPENAI_API_KEY`, so the operator is one config field away from a hosted
embedder and cannot reach it.

That matters more than "one more provider" suggests. Embedding is the only leg
of the info-radar dedup gate with no cloud path — when the local box is down or
busy, `get_embedder` raises, the gate conservatively reports `novel`, and every
item in the batch is pushed as new. The LLM half of the same pipeline has had a
selectable engine with a fallback since the stage adapter landed; the embedder
is the last piece of the analysis chain the settings page cannot steer.

## What Changes

- `get_embedder` dispatches on provider. Three are supported: `omlx` (the
  current local path), `openai` (hosted, `OPENAI_API_KEY`), and
  `openai_compatible` (an operator-supplied OpenAI-shaped API root, with a
  caller-named API-key env var and an explicit vector-space id).
- The live selection is a new user-editable state file,
  `~/.next-signal/embedding.json`, resolved once per item — the same
  relationship `engine.json` has with `configs/models.yaml`. The `embedders:`
  section of `models.yaml` stays as the baseline for the shipped OMLX and
  OpenAI providers. A generic endpoint has no honest repo-wide default, so its
  complete section is required before it can be selected.
- The state file never holds a secret. For `openai_compatible` it stores the
  *name* of the environment variable to read (`api_key_env`), and the value is
  resolved from `os.environ` when the item starts. Its `base_url` is a plain API
  root: credentials in URL userinfo/query/fragment are rejected.
- `get_embedder()` returns one immutable resolved snapshot containing the
  provider, model, identity, and embedding callable. The dedup outcome carries
  that same identity through persistence, so a settings write between the HTTP
  response and the database insert cannot mislabel a vector.
- **Vectors are stamped with the embedder that produced them.**
  `radar_pushed_topics` gains `embedder TEXT NOT NULL`. OMLX and OpenAI use
  `<provider>:<model_id>`; `openai_compatible` uses
  `openai_compatible:<space_id>`, because a generic model name does not prove
  two endpoints serve the same weights/tokenizer/pooling. Historical rows are
  conservatively labelled `legacy:unknown`: the old schema did not record which
  operator-configurable model produced them, so guessing would recreate the
  cross-space comparison bug during migration.
- **Every embedder must emit 1024-dimensional vectors**, enforced by checking
  that every element is a finite number, and raising `RuntimeError` otherwise.
  The `openai`/`openai_compatible` request sends `dimensions: 1024`, which the
  `text-embedding-3-*` family supports natively. This keeps the stored column at
  `vector(1024)` with no vector rewrite. **BREAKING** for any embedder that
  cannot produce 1024 dims (e.g. `text-embedding-ada-002`), which is rejected
  loudly at call time.
- The provider filter is applied before an **exact** pgvector cosine search.
  The existing mixed-space IVFFlat index is dropped and replaced with a normal
  index on `embedder`; at the table's measured hundreds-to-low-thousands scale,
  exact search is cheap and avoids approximate-index candidate generation being
  polluted by rows from another vector space.
- `/settings` gains an **Embedding** section built from the existing settings
  primitives: provider cards that commit on click, a per-provider pane that
  commits on Save, a credential-presence status dot, and a note that switching
  parks the current dedup memory rather than translating it. The generic card
  cannot become active until its complete pane has been saved. Hosted cards
  state that summaries leave the local machine and can incur per-item cost.
- `next-signal doctor` reports the selected embedder and whether its credential
  is present — the scheduler embeds unattended at 08:00, and a hosted embedder
  with a missing key conservatively turns everything into `novel`; the failures
  are logged, but an unattended run has nobody watching those logs live.

Deliberately **not** in scope: an embedder fallback chain (auto-switching
provider means silently switching vector space — worse than the loud failure the
dedup gate already handles); re-embedding history on switch; batch/multi-input
embedding requests; and any embedder consumer beyond the dedup gate (GBrain does
its own embedding behind its CLI and is untouched).

## Capabilities

### New Capabilities

- `core-embedding`: provider-neutral embedding. Owns the `embedding.json` state
  file and its validation, the `configs/models.yaml` baseline it overrides, the
  three-provider dispatch, the fixed 1024-dimension contract, the stable
  vector-space identity that makes a stored vector self-describing, the
  per-item resolved snapshot, the call-time credential lookup, the no-fallback
  policy, and the `next-signal doctor` read-back of the active selection.

  The `doctor` line lives here rather than in a `core-cli` delta on purpose:
  `core-cli`'s doctor requirement is already being renamed by the unarchived
  `rename-paca-to-next-signal` change, and a second delta on the same header
  would make the archive order load-bearing. The requirement is about the
  embedder being observable, which this capability owns either way.

### Modified Capabilities

- `core-models`: the `Embedder profiles are OMLX-only` requirement is removed —
  embedders leave the model factory's spec entirely and become `core-embedding`.
- `core-database`: `radar_pushed_topics` gains `embedder TEXT NOT NULL`,
  with pre-column rows labelled `legacy:unknown`. The mixed-space IVFFlat index
  is removed and a B-tree index on `embedder` supports exact provider-scoped
  search. The existing claim that switching embedders requires a vector-column
  migration becomes false.
- `info-radar-analysis`: the dedup gate performs an exact cosine search only
  within rows produced by the resolved embedder snapshot, and a new topic row
  records that snapshot's identity. The bootstrap requirement's `vector(1024)`
  rationale is restated as a contract rather than as a property of one model.
- `dashboard-shell`: the settings page gains an independent Embedding section,
  under the same section-independence rule the page already carries.

## Impact

**New code**

- `src/next_signal/core/embedding_preferences.py` — the `embedding.json` schema,
  baseline derivation, and strict loader (shaped like `core/engine_preferences.py`)
- `dashboard/lib/embedding-preferences.ts` — the shared parse/validate/serialize
  contract, mirroring `lib/engine-preferences.ts`
- `dashboard/lib/actions/embedding.ts` — server actions over the state file
- `dashboard/components/settings/embedding-section.tsx` — the settings section

**Modified**

- `src/next_signal/core/models.py` — `get_embedder()` loses its profile-name
  argument, resolves an immutable per-item snapshot, dispatches on provider,
  and validates vector shape/numeric values
- `src/next_signal/core/config.py` — `EmbedderProfile.provider` widens from
  `Literal["omlx"]`; the docstring's OMLX-only claim goes
- `src/next_signal/workflows/info_radar_analysis/stages/dedup.py`,
  `.../store.py` — carry the snapshot identity through `DedupOutcome`, exact
  `search_topics`, and `insert_topic`
- `scripts/bootstrap_db.py` — the `embedder` column plus its idempotent
  `legacy:unknown` backfill, removal of the mixed-space IVFFlat index, and the
  provider identity index
- `src/next_signal/core/db.py` — `BUSINESS_TABLE_COLUMNS["radar_pushed_topics"]`
  gains `embedder`, so `doctor` catches an un-migrated database
- `src/next_signal/interfaces/cli.py` — the `doctor` embedder check
- `configs/models.yaml` — an `openai` baseline entry beside `local`
- `dashboard/lib/paths.ts` (`embeddingStateFile()`),
  `dashboard/lib/i18n/dictionaries.ts` (both locales),
  `dashboard/components/settings/settings-view.tsx` (rail entry + section)
- `tests/test_get_embedder.py` — rewritten around live state and dispatch

**Dependencies**: none added. The OpenAI path reuses the existing `httpx` call
shape rather than pulling in the `openai` SDK for one POST, and the dashboard
section reuses `Input`, `Segmented`, and the engine section's pane pattern — no
new UI primitive, so no `/design` entry.

**Docs** (bilingual pairs, both sides in this change): `README.md`,
`docs/architecture.md`, `docs/containerized-deployment.md`,
`docs/modules/core.md`, `docs/modules/info_filter.md`, `docs/operations.md`
(including data egress, cost, env restart semantics, and the doctor check),
`dashboard/README.md`, their `README.zh-CN.md`, `docs/zh/`, and dashboard
`.zh-CN.md` mirrors, plus `CLAUDE.md`'s 模型与 OMLX and 数据库 sections and
`.env.example`.

**Cost safety**: selecting a hosted embedder makes the dedup gate — and
therefore the unattended 08:00 scheduler run — spend money per item.
`.claude/skills/docker-verify/SKILL.md`'s LLM-cost map currently treats
embedding as free local inference and must say otherwise.

**Credential reload semantics**: state-file edits steer the next item without a
restart. Credentials still come from the process environment; editing `.env`
requires restarting a host process or recreating its Compose service before the
new value exists in `os.environ`.

**Interaction with in-flight changes**: `add-coding-agent-stage-adapter`'s
`core-models` delta asserts "Embedder profile identity and dimensionality SHALL
remain sourced from `configs/models.yaml`". That sentence is superseded here and
must be reconciled before either change archives.
