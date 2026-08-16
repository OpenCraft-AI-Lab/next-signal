## Context

See `proposal.md` — Why. Three facts about the current code shape the approach:

- `configs/models.yaml::embedders` is read at *resolution* time, so a value
  meant as a suggestion becomes the running configuration.
- `embedding.json` has no endpoint field; the OMLX embedder resolves
  `OMLX_BASE_URL` from the process environment. Dashboard and scheduler are
  separate containers sharing only `/state`, so the environment is per-container
  while every other setting is shared.
- `core.models._build` is `@lru_cache`d on profile name alone, which is sound
  only while every input is immutable for the process lifetime.

This is F4 of the config-plane roadmap and a prerequisite for F5 (onboarding),
which needs every readiness input to be a file on the shared volume.

## Goals / Non-Goals

**Goals:**

- One home per configuration value, all on the shared state volume.
- "Not configured" is representable, distinguishable from "configured and
  broken", and reportable without attempting a request.
- Every credential the system can require has a place to be entered.

**Non-Goals:**

- Re-embedding, relabelling, or any vector migration.
- Fixing credential staleness in long-lived AgentOS processes (pre-existing;
  its own change).
- A UI for `DEEPSEEK_BASE_URL`.
- Onboarding surfaces — F5 owns those.

## Decisions

### Unset is a state, not a sentinel default

`EmbeddingPreferences.provider` becomes optional. Absent file, or present file
with no provider, both resolve to unselected. `get_embedder()` raises on
unselected; a separate query answers "is one selected" so callers branch on
state rather than parsing an error.

*Alternatives:* default to OpenAI — a fresh install has no OpenAI key either, so
the same silence with an added surprise bill. Keep the OMLX default and let F5's
banner explain it — rejected once F4 and F5 were split, because F4 must be
honest standing alone.

*Consequence:* the partial-section merge (`_MERGED_SECTIONS`) is deleted. With
no baseline to merge against, a section is either complete or invalid. This also
removes the OMLX/OpenAI vs `openai_compatible` asymmetry: all three providers now
follow "complete before selectable", which collapses `choose()`'s special case
and the "saving the pane is also the selection" workaround in the UI.

### Embedding owns its own OMLX endpoint, separate from the engine's

`embedding.json` gains `omlx.base_url`. It does not read `engine.json`.

*Rationale:* an mlx-lm server hosts one model per process, so a chat model and
an embedding model are genuinely two endpoints. Separate fields describe reality
rather than duplicating a value.

*Alternatives:* embedding reads `engine.json` — couples two state files, breaks
the one-writer-per-section discipline, and contradicts the snapshot contract
that `get_embedder()` reads the embedding preferences. A shared `omlx.json` —
a third state file and a migration for two fields.

The settings page may still present both under one "local models" heading;
storage layout and UI grouping are independent.

### `OMLX_BASE_URL` is deleted, and static profiles read engine state

`resolve_omlx_endpoint()` takes the chat endpoint from `engine.json` and the key
from the credential store. AgentOS's static YAML profiles resolve through the
same path, so nothing reads the environment variable and it leaves `.env`,
Compose, and the docs.

*Alternative:* keep the variable for the AgentOS path only. Rejected — the local
endpoint would have two homes depending on which entry point you came through.

*Consequence:* an unset chat endpoint raises, which OMLX profiles already handle
through `fallback_profile`. A fresh install with no local server therefore runs
interactive agents on the cloud fallback with no new code.

### One fixed credential name replaces `api_key_env`

The compatible endpoint's credential becomes `EMBEDDING_API_KEY`, added to
`CREDENTIAL_NAMES` in both `core/secrets.py` and `dashboard/lib/secrets.ts`.

*Rationale:* the name field existed because the value came from the process
environment, where the name had to match what the operator exported. The store
is ours, so we choose the name. Deleting the field also fixes a live defect: the
credentials section renders rows only for the fixed list, so a custom name had
no input control anywhere.

*Consequence:* the resolved-name set closes. `extraNames` plumbing in
`app/settings/page.tsx` and the dynamic presence lookup are deleted; name
validation stays.

*Alternative:* keep the name field and render a credential input inside the
embedding pane. More UI, more surface, no benefit once the store is authoritative.

### Drop the model cache; do not add a watcher

Remove `@lru_cache` from `_build`, then `reset_cache()`, its deferred-import
call in `secrets.py::_write`, and the invalidation test.

*Rationale:* the cache key is the profile name, which stops determining the
result once endpoints live in mutable state. Removal is a net deletion and
brings this path in line with the two that already resolve live — stage models
per job, embedders per item. It also removes a confusing failure mode where a
fallback model is cached under the *original* profile's name.

*Honest limitation:* `os_app.py` builds runnables at module import, so AgentOS
holds its agents — and their models — for the process lifetime. Dropping the
cache does **not** make a running AgentOS observe an endpoint change. It is
still worth doing on the grounds above, and the settings UI states the restart
caveat.

*Alternatives:* key the cache on the state file's mtime — machinery covering
only the files someone remembers to include. Resolve the endpoint lazily inside
the model — fights agno's constructor contract. An AgentOS file watcher — a real
feature, deferrable, and not what this change is about.

### The switch warning is unconditional

Confirmation on provider change does not query `radar_pushed_topics` to decide
whether to warn. A database read on the settings page to choose between two
messages buys accuracy nobody acts on, and the consequence statement is true
either way.

## Risks / Trade-offs

**An install with a working `OMLX_BASE_URL` loses embedding on upgrade** → its
implicit selection becomes unselected, so dedup goes off until the operator sets
the endpoint in Settings. Accepted: `doctor` fails loudly naming the unselected
state, and the settings page shows nothing selected, so it is visible rather
than silent. This repo's `.env` has no value set, so no live deployment here is
affected. If it ever matters, container bootstrap can seed a selection from the
variable once — the same read-path-stays-pure pattern `goals.yaml` uses — but
seeding a *selection* on an operator's behalf partly undoes this change's point.

**Seven spec deltas is a wide blast radius for one change** → unavoidable: the
config plane is described across seven capabilities, and leaving any of them
stale is exactly the drift the project's doc-sync rules exist to prevent.

**Removing the merge makes previously-tolerated state files invalid** → a
hand-written partial section now raises instead of silently completing.
Intentional, and consistent with the project's loud-failure rule; the settings
page still renders and repairs.

**Two OMLX endpoint fields invite mis-set duplicates** → mitigated in copy: the
embedding pane states why the endpoint is separate from the engine's.

## Migration Plan

No data migration. Vectors, `radar_pushed_topics.embedder` values, and
`legacy:unknown` rows are untouched.

State files migrate by shape, not by script:

- `embedding.json` absent → reads as unselected. Nothing to do.
- `embedding.json` present with a provider and no `omlx.base_url` → the OMLX
  section is incomplete and raises when selected; the operator completes it in
  Settings. Loud, not silent.
- `embedding.json` present with `api_key_env` → rejected by `extra="forbid"`;
  the settings page renders the repair path. The named credential already in the
  store is unaffected and can be re-entered as `EMBEDDING_API_KEY`.
- `engine.json` absent → the chat endpoint reads as unset, and OMLX profiles
  take their configured cloud fallback.

Rollback is reverting the deployment: no schema change and no destructive write.
