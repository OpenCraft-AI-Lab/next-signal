## 1. Prerequisite

- [x] 1.1 Reconcile with `add-coding-agent-stage-adapter` before either archives. Its `core-models` delta asserts that embedder identity and dimensionality remain sourced from `configs/models.yaml`; this change moves selection/identity to `embedding.json` plus a per-item snapshot and makes dimension a runtime contract. Decide archive order and record the reconciliation here before section 2.

  **Resolved.** Archive order: `rename-paca-to-next-signal` → `add-coding-agent-stage-adapter` → this change, which is the order their completion already implies (47/47, 20/20, then this one). Rather than depend on that order, the stale clause was reworded in place inside `add-coding-agent-stage-adapter`'s `core-models` delta: `Requirement: Production API stages apply live engine settings` now says embedders are outside its scope and that `engine.json` cannot change which embedder runs — a non-interference claim that is true both before and after this change. Its first scenario lost the matching "keep their configured embedder model" clause for the same reason. No `core-models` MODIFIED entry is needed here for that requirement, and this change's `core-models` delta keeps only the REMOVAL of `Requirement: Embedder profiles are OMLX-only`.

- [x] 1.2 Confirm no collision with `rename-paca-to-next-signal`: this change deliberately owns its doctor requirement in `core-embedding` because the rename change renames the existing `core-cli` doctor header.

  **Confirmed, with one extra dependency recorded.** `core-cli`: no collision — the rename change owns the `paca doctor` → `next-signal doctor` header rename and this change adds no `core-cli` delta, so the embedder check ships as a `core-embedding` requirement instead. `core-models`: the rename change's delta also carries `Requirement: Embedder profiles are OMLX-only` (a `paca.` → `next_signal.` restatement of the same header this change REMOVES). That makes the order above load-bearing in one direction only: rename must archive **before** this change, otherwise it would re-add a requirement this change deleted. Rename is already 47/47 and its code landed 2026-08-08, so this is a recording, not a blocker.

## 2. Live state and configuration

- [x] 2.1 Add `src/next_signal/core/embedding_preferences.py` with `EmbeddingProvider = Literal["omlx", "openai", "openai_compatible"]`; strict settings models for OMLX (`model`), OpenAI (`model`), and OpenAI-compatible (`base_url`, `model`, `api_key_env`, `space_id`); and a top-level `EmbeddingPreferences` carrying `provider`, the two baseline-backed sections, an optional compatible section, and `updated_at` / `updated_by`.
- [x] 2.2 Validate models against the existing `_MODEL_ID` pattern, `api_key_env` against `^[A-Z][A-Z0-9_]{0,63}$`, and `space_id` against `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`. Parse `base_url` as an API root, require `http`/`https` plus a host, reject URL username/password/query/fragment components, reject a path already ending in `/embeddings`, and normalize one trailing slash before appending the route.
- [x] 2.3 Add `EMBEDDING_PREFERENCES_FILE = STATE_ROOT / "embedding.json"`, `configured_embedding_defaults()`, and `load_embedding_preferences()`. An absent file selects `embedders.local`; OMLX/OpenAI partial sections inherit from their respective `models.yaml` profiles; an OpenAI-compatible section, when present, must be complete; selecting it while absent raises `RuntimeError`.
- [x] 2.4 Add `embedder_identity(prefs)`: OMLX/OpenAI return `<provider>:<model_id>`; OpenAI-compatible returns `openai_compatible:<space_id>`. Keep physical base URLs out of the identity.
- [x] 2.5 Widen `EmbedderProfile.provider` in `core/config.py` from OMLX-only to the supported provider union and rewrite its outdated dimensionality docstring.
- [x] 2.6 Add an `openai` baseline beside `local` under `configs/models.yaml::embedders`. Do not add a fabricated generic endpoint baseline; compatible configuration is optional state and must be supplied by the operator.

## 3. Provider dispatch and resolved snapshot

- [x] 3.1 Add an immutable `ResolvedEmbedder` carrying `provider`, `model_id`, `identity`, and `embed(text) -> list[float]`. Rewrite `get_embedder()` to take no arguments, load preferences and the current process credential once, and return this snapshot.
- [x] 3.2 OMLX snapshot: endpoint/key via `resolve_omlx_endpoint()`, no `dimensions` request field.
- [x] 3.3 OpenAI snapshot: `https://api.openai.com/v1` plus `OPENAI_API_KEY`, with `dimensions: 1024`; a missing key raises `RuntimeError` naming the variable.
- [x] 3.4 OpenAI-compatible snapshot: append `/embeddings` to the validated API root, resolve the configured `api_key_env` from `os.environ`, and send `dimensions: 1024`.
- [x] 3.5 Validate the response as exactly 1024 finite numeric elements. Wrong length, non-numeric elements, NaN/infinity, missing/empty data, or malformed JSON raises `RuntimeError`; never truncate, pad, or normalize.
- [x] 3.6 Acquire `ProviderConcurrency.acquire_sync(snapshot.provider)` around the HTTP request so hosted embedding does not consume the OMLX slot.
- [x] 3.7 Update the `core/models.py` module/section docstrings to describe provider-neutral embedding and the per-item snapshot.

## 4. Database and dedup plumbing

- [x] 4.1 Add `embedder TEXT NOT NULL` to `CREATE_RADAR_PUSHED_TOPICS`. For existing tables, use the idempotent temporary default `legacy:unknown`, then drop the default so future inserts cannot omit provenance.
- [x] 4.2 Drop `radar_pushed_topics_embedding_idx` if present and create `radar_pushed_topics_embedder_idx` as a normal index on `embedder`. Do not create one mixed-space IVFFlat index.
- [x] 4.3 Add `embedder` to `BUSINESS_TABLE_COLUMNS["radar_pushed_topics"]` so doctor catches an un-migrated database.
- [x] 4.4 Add an `embedder` parameter to `analysis_store.insert_topic` and write it.
- [x] 4.5 Rename `analysis_store.ann_search_topics` to `search_topics`; add an `embedder` parameter and perform exact cosine ordering only over `WHERE embedder = %s`, capped by threshold and `k`.
- [x] 4.6 Add `embedder: str | None` to `DedupOutcome`. `dedup.run()` constructs one `ResolvedEmbedder`, embeds and searches with its identity, and returns that identity beside every non-`None` vector. The runner persists only `outcome.embedder`; it never re-reads preferences after embedding.
- [x] 4.7 Preserve the conservative failure path: an embedder raise logs `dedup_embedder_failed`, returns `novel` with `embedding=None` and `embedder=None`, and inserts no topic row.
- [x] 4.8 Document the optional operator-confirmed SQL for relabelling `legacy:unknown` rows. Do not automate or expose a one-click relabel action.

## 5. Doctor

- [x] 5.1 Add an embedder check to `interfaces/cli.py`: report the resolved identity and whether required current-process configuration is present. OpenAI and compatible keys are required; OMLX requires its base URL while its key remains optional. Make no HTTP call.
- [x] 5.2 Render an unusable `embedding.json` as a failed check with its validation message rather than taking doctor down.
- [x] 5.3 When a credential is missing, state accurately that editing `.env` requires restarting a host process or recreating the Compose service; call-time `os.environ` reads do not hot-reload files.

## 6. Dashboard

- [x] 6.1 Add `embeddingStateFile()` to `dashboard/lib/paths.ts`.
- [x] 6.2 Add `dashboard/lib/embedding-preferences.ts` with the same strict contract as Python: baseline-backed OMLX/OpenAI sections, optional all-or-nothing compatible section including `spaceId`, strict unknown-key rejection, parsed URL restrictions, and parse/validate/serialize helpers.
- [x] 6.3 Add `dashboard/lib/actions/embedding.ts`: forgiving read for the repair page, strict atomic write through `writeStateFile`, and defaults derived from the two real `models.yaml::embedders` profiles. Do not invent compatible defaults.
- [x] 6.4 Add `embedding-section.tsx` using the existing provider cards, `PaneActions`, `usePaneSave`, and status-dot vocabulary. Do not refactor the engine section into a shared parent.
- [x] 6.5 OMLX/OpenAI provider cards commit against saved values on click. Clicking an unconfigured compatible card only opens its pane; saving its complete pane atomically stores the section and selects it. Later switches to it commit on click.
- [x] 6.6 Display the exact active identity, explain switch-away/switch-back behavior, and state that `legacy:unknown` rows remain parked unless explicitly relabelled.
- [x] 6.7 Show that hosted embedding sends tier-2 summaries off-machine and may incur per-item cost, including unattended scheduler runs.
- [x] 6.8 Pass credential presence as server-computed booleans. For compatible state, check the named variable; no key value crosses to the client.
- [x] 6.9 Wire the section into `settings-view.tsx`, add the rail item, verify four-section `IntersectionObserver` behavior, and add complete strings to both locales.

## 7. Tests

- [x] 7.1 Rewrite `tests/test_get_embedder.py` around `ResolvedEmbedder`: one happy path per provider, correct identity, fixed dimensions request, missing key, HTTP/non-2xx failure, malformed body, wrong width, non-numeric value, NaN, and infinity.
- [x] 7.2 Add preference tests: absent file selects local; OMLX/OpenAI partial state inherits baseline; compatible selection without a section fails; compatible section is all-or-nothing; unknown keys and invalid model/key/space-id/URL components or an endpoint-shaped `/embeddings` URL fail.
- [x] 7.3 Verify serialization never writes a credential value and rejects URL userinfo/query/fragment as possible secret-bearing state.
- [x] 7.4 Add a race regression test: resolve snapshot A, replace `embedding.json` with B before persistence, and prove search/insert still receive A's identity while the next item resolves B.
- [x] 7.5 Add database tests proving exact search returns only the requested identity, legacy rows are excluded, and switching back finds the earlier identity again.
- [x] 7.6 Update runner/store tests for `DedupOutcome.embedder`, `insert_topic(embedder=...)`, and `search_topics(embedder=...)`.

## 8. Docs (bilingual — both sides in this change)

- [x] 8.1 `README.md` + `README.zh-CN.md`: remove the local-only embedder claim and explain provider selection at a high level.
- [x] 8.2 `docs/architecture.md` + `docs/zh/architecture.md`: add `embedding.json`, per-item snapshots, and identity ownership.
- [x] 8.3 `docs/containerized-deployment.md` + Chinese mirror: cloud embedding path, data egress, hosted cost, and Compose recreate requirement after `.env` edits.
- [x] 8.4 `docs/modules/core.md` + Chinese mirror: provider-neutral embedder, fixed 1024 contract, concurrency, and state/env split.
- [x] 8.5 `docs/modules/info_filter.md` + Chinese mirror: exact provider-scoped search, `embedder` column, legacy sentinel, and switching behavior.
- [x] 8.6 `docs/operations.md` + Chinese mirror: provider configuration, `OPENAI_API_KEY`, compatible URL/key/space id, optional legacy relabel SQL, doctor output, restart semantics, data egress, and cost.
- [x] 8.7 `dashboard/README.md` + `dashboard/README.zh-CN.md`: the new settings section and unconfigured-compatible Save behavior.
- [x] 8.8 `CLAUDE.md`: update model/embedding and database guidance; `.env.example`: document embedder use and restart semantics.
- [x] 8.9 `.claude/skills/docker-verify/SKILL.md`: hosted embedding is a paid/off-machine call in the cost map.

## 9. Verification

- [x] 9.1 `openspec validate switchable-embedding-provider --strict` passes and no stale requirement preserves the mixed-space IVFFlat index, hardcodes historical Qwen provenance, derives generic identity from model id, or promises `.env` hot reload.
- [x] 9.2 `uv run pytest -q` passes.
- [x] 9.3 `docker compose build` then `docker compose run --rm dashboard next-signal doctor`; the embedder check reports the selected identity without making a model request.
- [x] 9.4 Confirm bootstrap is idempotent, pre-column rows become `legacy:unknown`, the old IVFFlat index is absent, and the `embedder` index exists.
- [x] 9.5 Open `/settings`, exercise all provider transitions, confirm an unconfigured compatible card cannot write an invalid selection, and verify only `embedding.json` changes with no key value present.
- [x] 9.6 Run `next-signal info-radar analyze --limit 2` against local OMLX last; confirm new topic rows carry the resolved identity and provider-scoped search works. This verification spends model tokens.

  **Verified against live OMLX.** The first two items were both tier-1 drops, so the gate never ran; a second pass over the remaining ten produced `tier1_kept=1 tier2_ok=1 dedup_novel=1`. The topic row it wrote (id 396) carries `omlx:Qwen3-Embedding-0.6B-8bit` — the identity captured in the snapshot, matching all 385 rows. Provider-scoped search on that row's stored 1024-dim vector: `omlx:Qwen3-Embedding-0.6B-8bit` → `[(396, 0.0)]`; `openai:text-embedding-3-small` → `[]`; `legacy:unknown` → `[]`. The filter excludes other spaces on live data, not just in tests.
