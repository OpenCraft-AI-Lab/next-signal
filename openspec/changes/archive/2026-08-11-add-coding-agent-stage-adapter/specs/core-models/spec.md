## ADDED Requirements

### Requirement: Production API stages apply live engine settings

For production stages routed to `omlx` or `deepseek`, the model factory SHALL construct the stage model from the appropriate static structured/plain profile while overriding the operator-controlled fields from the job's validated `engine.json`: OMLX base URL, model ID, and parallelism; DeepSeek model ID and reasoning mode. These runtime stage clients SHALL not alter the cached YAML-profile models used by AgentOS. Embedders are outside this requirement's scope: `engine.json` SHALL NOT change which embedder runs or what it emits.

#### Scenario: OMLX selection uses live model and endpoint

- **WHEN** a job starts with `engine.json` selecting OMLX model `M`, endpoint `U`, and parallelism `P`
- **THEN** every LLM stage in that job uses model `M` at `U` under the `P`-slot provider limit while embeddings resolve independently of the LLM engine selection

#### Scenario: DeepSeek reasoning setting is applied

- **WHEN** a job starts with DeepSeek reasoning set to `off`, `low`, or `high`
- **THEN** its stage client disables thinking or supplies the corresponding reasoning effort without changing the Pydantic output contract

### Requirement: OMLX endpoint resolution has one environment reader

Every OMLX model, embedder, live-engine default, and diagnostic SHALL resolve
`OMLX_BASE_URL` / `OMLX_API_KEY` through the centralized core resolver. The
public `next_signal.core.models.omlx_endpoint()` SHALL remain the strict API for
callers that require a configured environment and SHALL delegate to that resolver.

#### Scenario: Live engine default resolves OMLX consistently

- **WHEN** `OMLX_BASE_URL` is set before engine defaults are constructed
- **THEN** engine preferences and the public model endpoint return the same normalized base URL without either duplicating environment access
