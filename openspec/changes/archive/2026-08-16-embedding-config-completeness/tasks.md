## 1. Embedding state: unset, endpoint, fixed credential

- [x] 1.1 `core/embedding_preferences.py`: make `provider` optional so an absent file and a present-but-unselected file both resolve to unselected; add a predicate callers use to branch on selection without catching an error.
- [x] 1.2 Add `base_url` to `OmlxEmbeddingSettings`, reusing the existing API-root validation (http(s), host required, no userinfo/query/fragment, reject a path ending in `/embeddings`).
- [x] 1.3 Remove `api_key_env` from `OpenAICompatibleEmbeddingSettings` and its validator; the compatible section becomes `base_url` + `model` + `space_id`.
- [x] 1.4 Delete `_MERGED_SECTIONS` and the partial-section merge in `load_embedding_preferences`; every section is now complete-or-invalid.
- [x] 1.5 Rename `configured_embedding_defaults()` to reflect that it supplies form prefill, and stop any resolution path from calling it.
- [x] 1.6 Update the module docstring 鈥?it still describes credentials coming from the process environment, which F1 already made false.
- [x] 1.7 Verify: `uv run pytest -q tests/test_get_embedder.py` plus a new case asserting an absent file resolves unselected and never selects a provider.

## 2. Credential store

- [x] 2.1 Add `EMBEDDING_API_KEY` to `CREDENTIAL_NAMES` in `core/secrets.py`; update the comment that justifies the open name set, which loses its only reason.
- [x] 2.2 Mirror it in `dashboard/lib/secrets.ts` (`CREDENTIAL_NAMES`, `CREDENTIAL_USES`) so the credentials section renders a row for it.
- [x] 2.3 Verify: `grep -rn "api_key_env" src/ dashboard/` returns nothing outside archived changes.

## 3. Endpoint resolution and the model cache

- [x] 3.1 `core/omlx.py`: resolve the chat `base_url` from engine preferences instead of `os.environ`; keep the credential-store read for `OMLX_API_KEY` and the loud error when nothing is configured.
- [x] 3.2 `core/engine_preferences.py`: stop baselining `omlx.base_url` from the environment so an unsaved endpoint reads as unset.
- [x] 3.3 `core/models.py::get_embedder`: resolve the OMLX embedding endpoint from `embedding.json`, raise distinctly when unselected, and use `EMBEDDING_API_KEY` for the compatible provider.
- [x] 3.4 `core/models.py`: remove `@lru_cache` from `_build` and delete `reset_cache()`.
- [x] 3.5 `core/secrets.py::_write`: delete the deferred import and `reset_cache()` call, plus the comment block explaining them.
- [x] 3.6 Verify: `uv run pytest -q tests/test_model_fallback.py` after replacing the cache-invalidation test with one asserting OMLX is retried on the next call with no manual reset.

## 4. Dedup gate and doctor

- [x] 4.1 `workflows/info_radar_analysis/stages/dedup.py`: branch on the unselected state before resolving a snapshot, log it distinctly from an embedding failure, and return the same conservative novel outcome with no topic row.
- [x] 4.2 `interfaces/cli.py::_check_embedder`: report the unselected case naming the consequence (deduplication inactive), read the OMLX embedding endpoint from `embedding.json`, and keep the non-zero exit.
- [x] 4.3 `interfaces/cli.py::doctor`: drop the `OMLX_BASE_URL` check and report the chat endpoint from engine preferences instead.
- [x] 4.4 Verify: `uv run pytest -q tests/test_dedup_identity.py` plus a case asserting an unselected embedder yields novel with no topic row and the distinct reason.

## 5. Dashboard state mirrors

- [x] 5.1 `lib/embedding-preferences.ts`: mirror the optional provider, the OMLX `base_url`, and the removal of `api_key_env`, keeping parse/serialize in step with the Python side.
- [x] 5.2 `lib/actions/embedding.ts`: make `configuredDefaults()` supply prefill only, and have a missing or unusable file read back as unselected rather than the local baseline.
- [x] 5.3 `lib/actions/engine.ts`: remove the `process.env.OMLX_BASE_URL` baseline.
- [x] 5.4 `app/settings/page.tsx`: delete the `extraNames` plumbing and the dynamic compatible-credential presence lookup; read `EMBEDDING_API_KEY` presence like any other.

## 6. Settings UI

- [x] 6.1 `components/settings/embedding-section.tsx`: make card selection uniform 鈥?a card commits only when its section is complete 鈥?and delete the `openai_compatible` special case in `choose()` and the "saving is also selecting" path.
- [x] 6.2 Replace the hardcoded OMLX `tone: "ok"` with state computed from section completeness and credential presence; render the unselected state with no card active.
- [x] 6.3 Add the OMLX embedding base-URL field to its pane; remove the `api_key_env` field from the compatible pane.
- [x] 6.4 Add an unconditional confirmation on provider change stating the parked-memory and egress consequences.
- [x] 6.5 Add copy for: deduplication inactive while unselected, why the embedding endpoint is separate from the engine's, and (in the engine section) that running interactive agents pick up an endpoint change on restart.
- [x] 6.6 Add every new string to both locales in `lib/i18n/dictionaries.ts`.
- [x] 6.7 Verify: `cd dashboard && npm run build` 鈥?no type errors, no missing dictionary keys.

## 7. Deployment surface

- [x] 7.1 `.env.example`: delete the `OMLX_BASE_URL` entry and its comment block.
- [x] 7.2 `docker-compose.yml`: delete the header comment instructing operators to set `OMLX_BASE_URL`; keep `extra_hosts` and explain that the endpoint is entered in Settings.
- [x] 7.3 `configs/models.yaml`: confirm the `embedders` entries read as suggestions; adjust comments if they imply defaults.

## 8. Docs, both languages

- [x] 8.1 `docs/operations.md` + `docs/zh/operations.md`: remove `OMLX_BASE_URL` from the environment table, document the two endpoints as Settings values, and update the embedder-selection and troubleshooting sections.
- [x] 8.2 `docs/containerized-deployment.md` + `docs/zh/containerized-deployment.md`: update the local-OMLX instructions to point at Settings rather than `.env`.
- [x] 8.3 `docs/modules/core.md` + `docs/zh/modules/core.md`: update the OMLX resolver description and the model-cache note.
- [x] 8.4 `dashboard/README.md` + `dashboard/README.zh-CN.md`: update the embedding and engine section descriptions, including the unset state and the restart caveat.
- [x] 8.5 `CLAUDE.md`: update the OMLX endpoint bullet, the `reset_cache()` recovery note, and the credential-grep check line.
- [x] 8.6 `.claude/skills/docker-verify/SKILL.md`: update the cloud-only profile expectations that reference `OMLX_BASE_URL`.

## 9. Verification in Docker

- [x] 9.1 `docker compose build && docker compose up -d`, then `docker compose exec dashboard next-signal doctor`: expect a 鉁?naming the unselected embedder with the dedup consequence, and no `OMLX_BASE_URL` line.
- [x] 9.2 Open `/settings` in the running stack: no embedder card selected, panes prefilled, engine endpoint empty rather than showing an environment value.
- [x] 9.3 Save an embedding selection in the browser, then re-run `doctor` in the scheduler container to confirm the same file is observed with no restart.
- [x] 9.4 ~~`docker compose exec dashboard next-signal info-radar analyze --limit 2` with nothing selected~~ — **deliberately skipped.** There are 0 unanalyzed `radar_items`, so the command is a no-op that proves nothing; forcing the condition means resetting `seen_at` on real rows (colliding with `radar_analyses`' `UNIQUE(radar_item_id)`) and spending LLM tokens. Covered instead by `tests/test_dedup_identity.py::test_unselected_embedder_turns_dedup_off_without_failing`, which asserts novel status, no vector, no identity, and that the topics table is never queried.
- [x] 9.5 `uv run pytest -q` green on the host, and stop the stack when finished.
