## Why

The settings page grew by bolting each new setting onto a flat Credentials list with no connection to what it powers, so a new operator can't tell what needs setting up, why `ANTHROPIC_API_KEY` or `GOOGLE_API_KEY` exist (nothing in the shipped configuration uses them), or that choosing an embedding model is a one-way door. The Engine section also misrepresents its own state — OMLX shows as pre-selected and "configured" on a fresh install even though nothing has been saved — which is exactly the class of bug the embedding section's own prior redesign was meant to prevent.

## What Changes

- Settings page reorganizes into domain-scoped, collapsible sections — Engine, Radar Embedding, Knowledge Embedding (new), RSS — each showing its selected option when collapsed and requiring expansion to change it, with credential inputs living inside the section that consumes them instead of a separate flat list.
- **BREAKING**: every settings commit, including which provider/engine is primary (not just a provider's own field values), now requires an explicit Save action. This reverses the current "selecting an already-configured card commits immediately" behavior for Engine provider switching and for switching between already-complete Radar Embedding providers.
- **BREAKING**: Engine section no longer pre-selects OMLX as primary on a fresh install, and its OMLX card status reflects whether a base URL is actually saved instead of a hardcoded "configured" label. This is real parity with Radar Embedding, not just a UI fix: `EnginePreferences.primary` becomes genuinely optional at the Python level (it was previously always `"omlx"` by default), and `agents/stage.py::stage_job()` — the entry point for every production LLM stage job (info-radar analyze, info-radar recap, knowledge ingest) — now raises a distinct `EngineNotSelected` error before any provider call when nothing has been explicitly saved, the same way `get_embedder()` already does for dedup. An install that has never opened Settings → Engine and saved a choice will have its production jobs fail loud (reported by a new `next-signal doctor` check) instead of silently running on OMLX with a DeepSeek fallback as before.
- Radar Embedding and the new Knowledge Embedding section both lock in full once first saved — no switching providers and no editing any field afterward — replacing Radar Embedding's current confirm-dialog-then-switch flow. A changed embedding model breaks vector-space comparability for radar dedup and irreversibly resizes GBrain's Postgres schema for knowledge search.
- New Knowledge Embedding section wires the dashboard to the previously CLI-only `next-signal knowledge gbrain-init`: choose a provider and model, see an explicit irreversibility warning, save to initialize GBrain, and see its three-state readiness (not initialised / initialised-but-credential-missing / ready) instead of only via `next-signal doctor`.
- **BREAKING**: four credentials drop out of the settings UI entirely — `ANTHROPIC_API_KEY` and `GOOGLE_API_KEY` (zero live consumers: the `claude_smart`/`claude_fast`/`gemini` profiles in `configs/models.yaml` are referenced by no agent, workflow, or team config), `GITHUB_TOKEN` and `OMLX_API_KEY` (both read with graceful-degradation semantics — anonymous GitHub access, unauthenticated OMLX requests — not required by any current experience). The now-unreferenced `models.yaml` profiles are left in place, not deleted.
- **BREAKING**: `OPENAI_API_KEY` splits into two independently stored credentials, since it currently and coincidentally names two unrelated consumers. Radar Embedding's copy is renamed to `RADAR_EMBEDDING_OPENAI_API_KEY` (a name next-signal owns). Knowledge Embedding's copy stays `OPENAI_API_KEY` because GBrain's own subprocess reads that literal name from its environment as an external, non-negotiable contract. An operator who had `OPENAI_API_KEY` set for radar dedup must re-enter it under the new name; there is no migration, matching this project's existing no-migration stance on credentials.
- `VOYAGE_API_KEY` and `GOOGLE_GENERATIVE_AI_API_KEY` — already resolved by the Python credential store for GBrain but absent from the dashboard's TypeScript mirror and i18n dictionary, so they render nowhere today — get real inputs inside the new Knowledge Embedding section.
- The end-of-page credential list becomes a plain, read-only, presence-only summary of what the sections above own. It stops being a place credentials are entered or cleared.
- Bug fix folded in because it sits on code this change already touches: the Radar Embedding `openai_compatible` pane currently allows Save with no `EMBEDDING_API_KEY` set (only a soft warning badge), while `get_embedder()` requires that credential unconditionally at call time. Since this pane's save is about to lock the section permanently, the gap closes: the key is required before the save that locks it.

## Capabilities

### New Capabilities

(none — the new Knowledge Embedding behavior is a settings-page section, following the existing pattern where `dashboard-shell` owns every `/settings` section rather than each getting its own capability)

### Modified Capabilities

- `dashboard-shell`: settings-page section structure and collapse behavior, the commit/persistence model (discrete choices no longer commit on click), credentials move from one shared section into per-section ownership, Engine section defaults and status reporting, Radar Embedding's switch-with-confirmation replaced by lock-after-save, and a new settings-page requirement for the Knowledge Embedding section.
- `core-embedding`: the credential name resolved for the radar OpenAI provider, lock-after-first-save replacing the switch-with-confirmation contract, and the compatible provider's credential becoming required before its section can be saved.
- `core-credentials`: the resolved credential enumeration — four names removed, one renamed, and the two GBrain-only names (`VOYAGE_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`) that the spec text was already missing relative to `secrets.py` brought in sync.
- `core-models`: `EnginePreferences.primary` becomes optional and gains a real unselected state, mirroring `core-embedding`'s `EmbedderNotSelected` — discovered during implementation, not scoped at propose time. `stage_job()` now raises `EngineNotSelected` before any provider call when nothing is selected, since a production stage job has no degraded mode to fall back to the way the dedup gate does.
- `core-cli`: `next-signal doctor` gains a check reporting whether an engine is selected, for the same reason it already reports embedder selection.

## Impact

- `dashboard/components/settings/*.tsx` — all section components restructured; new Knowledge Embedding section component
- `dashboard/lib/secrets.ts`, `dashboard/lib/actions/secrets.ts`, `dashboard/lib/i18n/dictionaries.ts` — credential list and copy
- `dashboard/lib/actions/engine.ts`, `dashboard/lib/actions/embedding.ts` — defaults, status computation, lock enforcement
- `dashboard/lib/engine-preferences.ts` — `primary` becomes `Engine | null`
- new dashboard server action wrapping `next-signal knowledge gbrain-init` and GBrain's three-state readiness check
- `src/next_signal/core/secrets.py` — `CREDENTIAL_NAMES` enumeration
- `src/next_signal/core/models.py` — credential name used to resolve the radar OpenAI embedder
- `src/next_signal/core/engine_preferences.py` — `primary` becomes optional, `EngineNotSelected` added
- `src/next_signal/agents/stage.py` — `stage_job()` raises `EngineNotSelected` before any provider call
- `src/next_signal/interfaces/cli.py` — new `_check_engine()` doctor check; fixed two stale `OPENAI_API_KEY`/"Settings → Credentials" references in `_check_embedder()` left over from before this change
- `openspec/specs/core-credentials/spec.md` — sync to the actual resolved set
- Not touched: `next-signal knowledge gbrain-init` itself, the `codex_auth`/`claude_auth` Docker volumes, GitHub-repo-URL ingest routing, AgentOS's interactive-agent model resolution
