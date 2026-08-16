## RENAMED Requirements

- FROM: `### Requirement: OMLX endpoint sourced from environment`
- TO: `### Requirement: OMLX endpoint sourced from user state`

- FROM: `### Requirement: OMLX endpoint resolution has one environment reader`
- TO: `### Requirement: OMLX endpoint resolution has one state reader`

## REMOVED Requirements

### Requirement: Saving a credential invalidates cached models

**Reason**: There is no model cache to invalidate. `get_model` now builds each
call, so a corrected credential reaches the next model use without any
invalidation step — the property this requirement protected is now structural
rather than maintained.

**Migration**: None. The behaviour it guaranteed is subsumed by "Built models are
not cached across calls", which is strictly stronger: it also covers endpoint
changes, not only credential changes.

## MODIFIED Requirements

### Requirement: OMLX endpoint sourced from user state

The OMLX `base_url` for LLM profiles SHALL be read from the engine preferences
in user state (`engine.json`), not from the process environment. No module SHALL
read an `OMLX_BASE_URL` environment variable; that variable SHALL NOT be part of
the system's configuration surface.

The OMLX `api_key` SHALL be resolved from the credential store at call time by
the same resolver, so the endpoint is assembled from one place even though its
two halves have different sources. `OMLX_API_KEY` remains optional — a local
OMLX server usually has none.

Every consumer of a local LLM endpoint — static YAML profiles used by AgentOS,
live engine stages, and diagnostics — SHALL resolve it from engine preferences,
so the local chat endpoint has exactly one home. The embedding capability owns
its own OMLX API root separately, because one local model server hosts one
model.

#### Scenario: missing endpoint configuration fails loud

- **WHEN** engine preferences record no OMLX base URL
- **THEN** endpoint resolution raises `RuntimeError`, which an OMLX profile
  handles through its configured `fallback_profile`

#### Scenario: environment is not an endpoint source

- **WHEN** `OMLX_BASE_URL` is set in the process environment
- **THEN** it has no effect, because no module reads it

#### Scenario: OMLX key comes from the store

- **WHEN** `OMLX_API_KEY` is present in the credential store
- **THEN** endpoint resolution returns it, and it is not read from the process
  environment

### Requirement: OMLX endpoint resolution has one state reader

Every OMLX model, live-engine default, and diagnostic that needs the local chat
endpoint SHALL resolve it through the centralized core resolver reading engine
preferences and the credential store. The public
`next_signal.core.models.omlx_endpoint()` SHALL remain the strict API for
callers that require a configured endpoint and SHALL delegate to that resolver.

#### Scenario: Live engine default resolves OMLX consistently

- **WHEN** engine preferences record an OMLX base URL
- **THEN** engine defaults and the public model endpoint return the same
  normalized base URL without either duplicating state access

### Requirement: Production API stages apply live engine settings

For production stages routed to `omlx` or `deepseek`, the model factory SHALL construct the stage model from the appropriate static structured/plain profile while overriding the operator-controlled fields from the job's validated `engine.json`: OMLX base URL, model ID, and parallelism; DeepSeek model ID and reasoning mode. Embedders are outside this requirement's scope: `engine.json` SHALL NOT change which embedder runs or what it emits.

#### Scenario: OMLX selection uses live model and endpoint

- **WHEN** a job starts with `engine.json` selecting OMLX model `M`, endpoint `U`, and parallelism `P`
- **THEN** every LLM stage in that job uses model `M` at `U` under the `P`-slot provider limit while embeddings resolve independently of the LLM engine selection

#### Scenario: DeepSeek reasoning setting is applied

- **WHEN** a job starts with DeepSeek reasoning set to `off`, `low`, or `high`
- **THEN** its stage client disables thinking or supplies the corresponding reasoning effort without changing the Pydantic output contract

### Requirement: Automatic fallback when OMLX unreachable

When an OMLX-backed profile fails to construct (`RuntimeError`) and the profile declares a `fallback_profile`, `get_model` SHALL transparently return the fallback profile's model.

#### Scenario: fallback to DeepSeek when OMLX is down

- **WHEN** OMLX is unreachable and the profile lists `fallback_profile: deepseek_smart` (as `local` does in `configs/models.yaml`)
- **THEN** `get_model` returns the `deepseek_smart` model and logs the substitution

#### Scenario: cache must be reset to retry OMLX

- **WHEN** OMLX recovers after a fallback occurred
- **THEN** the next `get_model` call returns the OMLX model again, because
  nothing is cached and no reset step exists

## ADDED Requirements

### Requirement: Built models are not cached across calls

`get_model(profile_name)` SHALL construct a model each time it is called. The
profile name SHALL NOT be treated as a cache key, because the endpoint and
credentials a model is built from now live in user state that can change while
a process runs, so the name no longer determines the result.

No cache-invalidation entry point SHALL exist for built models, and saving a
credential SHALL NOT need to clear one.

A caller that retains a constructed model — notably AgentOS, which builds its
agents once at startup — continues to use the endpoint and credential captured
at construction. Interfaces that let an operator change those values SHALL state
that already-running interactive agents pick up the change on restart. Paths
that resolve per job or per item — production stages and embedding — are
unaffected and observe changes immediately.

#### Scenario: a profile is rebuilt on each request

- **WHEN** `get_model` is called twice for the same profile with different
  endpoint settings saved in between
- **THEN** the second call returns a model built against the second endpoint

#### Scenario: recovery needs no manual reset

- **WHEN** an OMLX profile fell back to its cloud profile while the local server
  was unreachable, and the server later recovers
- **THEN** the next `get_model` call for that profile builds OMLX again without
  any cache-clearing call

#### Scenario: retained models keep their construction-time settings

- **WHEN** an operator changes the local endpoint while AgentOS is running
- **THEN** its already-constructed interactive agents continue against the
  previous endpoint until the process restarts, and the settings interface says so
