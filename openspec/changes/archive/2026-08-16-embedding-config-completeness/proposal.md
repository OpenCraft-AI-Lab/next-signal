## Why

A fresh install silently ships with deduplication switched off. `embedding.json`
defaults to the OMLX provider, the default Docker stack deliberately leaves
`OMLX_BASE_URL` unset, so `get_embedder()` raises on every item, the dedup gate
takes its conservative branch, and every item is stored as novel forever. No
error surfaces: the settings page's OMLX card is hardcoded to report
`configured`, and the only trace is a warning in a log file.

The root cause is that `configs/models.yaml::embedders` — a *form prefill*,
"here is a good model if you pick OMLX" — is read as a *runtime default*, "use
OMLX with this model". Nobody ever chose OMLX; the system chose it on their
behalf and then could not tell them it had not worked.

Two smaller defects share the same cause. `embedding.json::api_key_env` stores
the *name* of a credential, a vestige of the pre-credential-store world where
the value came from the process environment; the dashboard's credentials
section renders rows only for its fixed list, so an operator-chosen name has no
input control anywhere in the UI and the OpenAI-compatible provider cannot be
credentialed at all. And the OMLX embedder endpoint is still an environment
variable, which the dashboard cannot read on behalf of the scheduler — the two
run in separate containers and share only `/state`.

This is F4 of the config-plane roadmap. It is a prerequisite for F5
(onboarding), which cannot honestly report embedder readiness while one of its
inputs lives in a per-container environment variable.

## What Changes

- **BREAKING** An absent or unselected `embedding.json` is a first-class
  *unset* state, not the local baseline. `models.yaml::embedders` becomes form
  prefill only and no longer determines what runs. `EmbeddingPreferences.provider`
  becomes optional; the partial-section merge in `load_embedding_preferences`
  is removed, since there is no baseline left to merge against.
- An unset embedder turns **deduplication off and nothing else**. The radar
  still pulls, scores, and displays; the dedup gate reports "not configured"
  distinctly from "embedding failed", and persists no topic row in either case.
- **BREAKING** All three provider cards become selectable only once complete,
  removing the `openai_compatible` asymmetry and the "saving the pane is also
  the selection" workaround. The OMLX card's hardcoded `ok` status is replaced
  by real computed state.
- **BREAKING** `embedding.json` gains its own `omlx.base_url`, separate from
  `engine.json`'s: an mlx-lm server holds one model per process, so a chat
  model and an embedding model are two endpoints.
- **BREAKING** `OMLX_BASE_URL` is deleted outright. `engine.json` stops
  baselining its endpoint from the environment, and AgentOS static profiles
  resolve the local endpoint from `engine.json` too, so the local endpoint has
  exactly one home per role and both are on the shared state volume.
- **BREAKING** `embedding.json::api_key_env` is removed in favour of one fixed
  reserved credential, `EMBEDDING_API_KEY`, added to `CREDENTIAL_NAMES` on both
  the Python and TypeScript sides. This closes the dead end where a custom name
  had no input control.
- `next-signal doctor` still fails on an unconfigured embedder, reporting
  "no embedder selected" distinctly from a missing credential.
- Switching provider raises an unconditional warning at the moment of the
  click. No migration, relabelling, or re-embedding is offered.
- The `@lru_cache` on `core.models._build` is dropped — a pure deletion of the
  decorator, `reset_cache()`, its deferred-import call in `secrets.py::_write`,
  and the invalidation test. AgentOS builds its agents once at import, so
  interactive agents still need a restart to observe an endpoint change; the
  settings UI says so rather than gaining a file-watcher.

Non-goals: `DEEPSEEK_BASE_URL` keeps its working default and no UI (adding a
field for an override nobody needs is speculative configurability). The
credential staleness in long-lived AgentOS processes is real but pre-existing
and out of scope. No migration path for existing vectors.

## Capabilities

### New Capabilities

None. This change corrects and completes existing capabilities.

### Modified Capabilities

- `core-embedding`: unset becomes a valid resolved state; the local baseline no
  longer auto-selects; `omlx.base_url` joins the state file; `api_key_env` is
  replaced by a fixed credential name; the partial-section merge is removed;
  doctor's reporting gains the unconfigured case.
- `core-models`: the "OMLX endpoint sourced from environment" requirement
  inverts — the endpoint resolves from user state, and no module reads
  `OMLX_BASE_URL`. YAML-profile models are no longer cached.
- `core-credentials`: `EMBEDDING_API_KEY` joins the resolved-by-name set; the
  open-name-set allowance loses its only justification.
- `core-cli`: `doctor` no longer checks `OMLX_BASE_URL` as an env var and
  reports an unselected embedder distinctly.
- `core-container-verification`: the expected fresh-stack `doctor` output
  changes, since `OMLX_BASE_URL` is no longer a check.
- `dashboard-shell`: the embedding section's selection rules, endpoint field,
  credential field, honest card status, and switch warning.
- `info-radar-analysis`: the dedup gate distinguishes an unconfigured embedder
  from a failed one.

## Impact

**Python** — `core/embedding_preferences.py` (unset state, base URL, merge
removal), `core/omlx.py` (resolve from state), `core/models.py` (cache removal,
`get_embedder`, static profile endpoints), `core/secrets.py` (`CREDENTIAL_NAMES`,
`reset_cache` call), `core/engine_preferences.py` (env baseline), `interfaces/cli.py`
(`_check_embedder`), `workflows/info_radar_analysis/stages/dedup.py`.

**Dashboard** — `lib/embedding-preferences.ts`, `lib/actions/embedding.ts`,
`lib/actions/engine.ts`, `lib/secrets.ts`, `components/settings/embedding-section.tsx`,
`app/settings/page.tsx` (the `extraNames` plumbing disappears), i18n dictionaries.

**Deployment** — `.env.example`, `docker-compose.yml`, `configs/models.yaml`.

**Tests** — `test_get_embedder.py`, `test_dedup_identity.py`,
`test_engine_preferences.py`, `test_model_fallback.py` (the cache-invalidation
test goes), plus new coverage for the unset state.

**Docs, both languages** — `docs/operations.md`, `docs/containerized-deployment.md`,
`docs/modules/core.md`, `dashboard/README.md`, their `zh` mirrors, and the OMLX
endpoint and model-cache notes in `CLAUDE.md`.
