## Why

A first-time `docker compose up` fails. Container bootstrap runs
`gbrain init --non-interactive`, GBrain refuses to initialise without an
embedding provider credential in its environment, bootstrap exits 1, and both
`dashboard` and `scheduler` gate on `service_completed_successfully` — so the
whole stack is dead on a clean volume.

The cause is a mirror that fell out of step. `4118e50` moved credentials into
the store and taught `next_signal.integrations.gbrain.gbrain_env()` to inject
`OPENAI_API_KEY` through `child_env`. `scripts/container_bootstrap.sh` spawns
GBrain itself, in shell, and its comment says it mirrors that function — but it
copied only the `DATABASE_URL` handling, not the credential injection. GBrain
therefore inherits an environment that, by design, no longer holds any
credential.

It is latent rather than visible on an existing install: bootstrap takes the
`--migrate-only` branch whenever `$GBRAIN_HOME/.gbrain/config.json` exists, and
that branch needs no embedding provider. Only a first-time volume runs the full
init.

This also violates a requirement `core-credentials` already states — that a
spawn must strip and inject rather than inherit, explicitly covering the case
where the external program reads a credential-shaped variable on its own.

Fixing it by injecting the credential would not be enough: a fresh install has
an empty store, because the store is written by the dashboard and the dashboard
cannot start until bootstrap succeeds. Requiring a credential at bootstrap makes
a zero-edit first run impossible.

Nor can bootstrap initialise GBrain *without* an embedding model and leave the
operator to configure one later. GBrain's embedding model **sizes the Postgres
schema**, so it is fixed at `init` time, and a brain initialised with
`--no-embedding` cannot be upgraded in place: `gbrain config set
embedding_model` is a documented no-op on this engine, and `gbrain init --force
--embedding-model <id>` exits 0 while silently leaving the brain deferred.
Initialising early is therefore a one-way door into a permanently search-less
brain. The only initialisation that works is the one that already knows which
model it is for.

## What Changes

- Container bootstrap SHALL NOT initialise GBrain at all when no brain exists,
  and SHALL NOT read, inject, or otherwise handle any credential. It keeps
  creating GBrain's database and keeps running the `--migrate-only` branch for
  an already-initialised brain, so existing installs are unaffected.
- **BREAKING for a fresh install's capabilities, not its startup**: GBrain is
  absent until an operator chooses an embedding model, so knowledge search is
  unavailable until then. The stack itself always starts.
- A new `next-signal knowledge gbrain-init` command SHALL perform the one and
  only initialisation, taking the operator's chosen `<provider>:<model>` and
  injecting whichever credential that provider needs. It SHALL be
  **provider-general** — GBrain supports OpenAI, Voyage, Google, and local
  runners (Ollama, LM Studio, llama-server), and a local provider needs no
  credential at all, only an endpoint.
- The embedding model SHALL be **locked once chosen**. GBrain itself refuses to
  re-template an initialised brain; the command SHALL surface that rather than
  offering a `--force` that cannot work.
- The uninitialised state becomes a **reported state**, not a silent one:
  `next-signal doctor` names it and says what is unavailable, in the same shape
  as the unselected-embedder check. A brain that is initialised but whose
  provider credential is missing SHALL be reported as its own distinct state.
- The stale "mirror `gbrain_env`" comment goes, since bootstrap deliberately no
  longer mirrors the credential half.

Non-goals: a dashboard control for GBrain's embedding model; automatic
initialisation once a key is saved; migrating an already-initialised brain to a
different embedding model; any change to how knowledge ingest reports embedding
failures, which is already loud; configuring a local embedding provider's
endpoint (e.g. Ollama's base URL) — the provider is selectable and its
credential-free path is real (`gbrain-init` injects nothing and succeeds
against an empty store), but nothing here lets an operator point it at a
specific address, so it falls back to GBrain's own default, which is not
guaranteed to resolve inside the container. Left for follow-up work rather than
folded in here, since this change exists to get the stack starting, not to
build endpoint configuration.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `core-credentials`: container bootstrap is brought under the
  spawn-scoping requirement by removing its need for a credential entirely,
  rather than by injecting one; and a spawn's injected credential is scoped to
  the provider actually selected, rather than to one hard-coded provider.
- `core-cli`: the `knowledge` subcommand group gains `gbrain-init`, and `doctor`
  reports whether GBrain is initialised and ready, naming what is unavailable
  while it is not.
- `core-container-verification`: a first-time stack start must succeed with an
  empty credential store, and the expected fresh-stack `doctor` output gains the
  GBrain line.
- `knowledge-search-tool`: searching against an uninitialised GBrain fails
  loudly and names the cause rather than returning empty results.

## Impact

**Scripts** — `scripts/container_bootstrap.sh`: the `gbrain init` invocation and
its surrounding comment.

**Python** — `src/next_signal/interfaces/cli.py`: the GBrain doctor check, and
the new `knowledge gbrain-init` command.
`src/next_signal/integrations/gbrain.py`: an initialised-or-not probe, and
provider-scoped credential injection in `gbrain_env()`.

**Docs, both languages** — `docs/containerized-deployment.md`,
`docs/operations.md`, `docs/modules/knowledge.md`, and their `zh` mirrors: first
run no longer requires a key, and knowledge search needs one explicit
initialisation step, whose model choice is permanent.

**Verification** — a first-time start against an empty credential store and an
empty state volume is the acceptance test, so it needs a throwaway volume rather
than the developer's existing one.
