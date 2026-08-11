## REMOVED Requirements

### Requirement: Embedder profiles are OMLX-only

**Reason**: The requirement's central claim — that the only supported embedder
provider is OMLX and that `get_embedder` resolves a named profile from
`configs/models.yaml` — is exactly what this change reverses. Embedders gain a
provider dispatch, a live state file, a fixed-dimension contract, and an
immutable per-item vector/identity snapshot, which is more surface than a single
requirement inside the LLM model factory's spec should carry. Keeping a narrowed
version here would split embedder behavior across two capabilities.

**Migration**: The behavior moves wholesale to the new `core-embedding`
capability, which restates and extends every clause of this requirement:

- Profile resolution → `Requirement: One resolved embedder snapshot owns one
  item's vector and identity` and `Requirement: Real profiles supply baselines
  and generic configuration is explicit`. The `get_embedder(profile_name)`
  parameter is gone; callers use `get_embedder()` and receive a
  `ResolvedEmbedder`. The `embedders:` section survives as the baseline for
  providers with real shipped defaults; generic endpoint state is explicit.
- The OMLX `/v1/embeddings` route and its `omlx_endpoint()` sourcing →
  `Requirement: Three embedding providers are supported`, as one of three
  branches. `Requirement: OMLX endpoint sourced from environment` in this
  capability is unchanged and still governs how that branch resolves its
  endpoint.
- Loud failure on connection errors, non-2xx responses, and malformed bodies →
  `Requirement: Three embedding providers are supported`, unchanged in substance.
- The `ProviderConcurrency` slot per embed call → `Requirement: Embedding uses
  the resolved provider's concurrency slot`, extended to key the slot on the
  provider captured in the item snapshot rather than on a fixed one.
- "The dimensionality is whatever the server returns; callers that persist into a
  fixed-dim column must validate length themselves" is **reversed**:
  `Requirement: Every returned embedding is exactly 1024 finite numbers` moves
  full shape/numeric validation into `embed()` itself, so no caller can store a
  wrong-width or non-finite vector.
- The `KeyError` on an unknown profile name has no successor, because there is no
  profile name to get wrong. Its role is taken by `Requirement: The embedding
  state is strict and cannot carry a secret value` and the unknown-provider
  clause of the provider requirement.
