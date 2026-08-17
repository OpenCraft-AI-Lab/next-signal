## Context

See `proposal.md` — Why. Four constraints shape the approach:

- Bootstrap is a **shell script**. It cannot call `child_env()` or
  `gbrain_env()`, which is how it came to hold a hand-copied "mirror" of those
  helpers that silently fell behind when `4118e50` added credential injection.
- Bootstrap runs **before any credential can exist**. The store is written by
  the dashboard; the dashboard gates on `service_completed_successfully`. A
  bootstrap that needs a credential is unreachable on a first run.
- GBrain's embedding model **sizes the Postgres schema**, so it is chosen at
  `init` and cannot be changed afterwards. Initialising with `--no-embedding` is
  a one-way door: the resulting brain cannot be upgraded in place (see
  *Resolved Questions*).
- The failure is **invisible on an initialised volume**, because the
  `$GBRAIN_HOME/.gbrain/config.json` check routes existing installs to
  `--migrate-only`, which needs no provider. Only a first-time volume runs the
  full init, so any verification must use a throwaway volume.

## Goals / Non-Goals

**Goals:**

- A first-time `docker compose up` succeeds against an empty credential store.
- Bootstrap holds no credential logic that can drift out of step again.
- GBrain's uninitialised state is visible, not discovered by a search that
  quietly returns nothing.
- The one initialisation that happens is correct for any provider GBrain
  supports, including local runners that need no credential.

**Non-Goals:**

- A dashboard control for GBrain's embedding model.
- Automatic initialisation once a credential is saved.
- Migrating an already-initialised brain to a different embedding model.
- Any change to knowledge *ingest*'s failure behaviour, which is already loud.

## Decisions

### Defer initialisation rather than initialising without a model

Bootstrap creates GBrain's database and runs `--migrate-only` for an existing
brain, but performs **no `gbrain init`** when no brain exists. It never reads the
store, never branches on whether a key exists, and never exports a provider
variable. Initialisation moves to an explicit operator command that already
knows which model it is for.

*Rationale:* the durable property is "this script handles no credentials", which
cannot drift. Any injection — even a correct one — puts credential handling back
into a file that has no access to the helpers that define how credentials work,
recreating the exact drift that caused this bug. Deferring is what makes that
possible without stranding the brain, because initialising early would fix the
model choice before anyone can make it.

*Alternatives:* initialise with `--no-embedding` and configure later — rejected
on evidence, because there is no working "later" (see *Resolved Questions*).
Inject `OPENAI_API_KEY` from `/state/secrets.json` in shell — fixes the leak but
still fails on a fresh install, since the store is empty then, and reintroduces
shell-side credential handling. Inject when present and defer when absent — the
conditional is credential handling by another name, and it would bind the model
choice to whichever key happened to be saved first.

*Consequence:* a fresh stack has no brain at all until an operator runs one
command. Accepted: an absent brain is honest, and a wrongly-sized one is
permanent.

### Initialisation is provider-general, not OpenAI-shaped

`next-signal knowledge gbrain-init --embedding-model <provider>:<model>
[--embedding-dimensions <N>]` performs the init through `gbrain_env()`, which
injects the credential **the selected provider** needs rather than a hard-coded
`OPENAI_API_KEY`.

*Rationale:* GBrain supports `openai:`, `voyage:`, `google:`, and local runners
(`ollama:`, LM Studio, llama-server). A local provider needs no credential at
all — only an endpoint — so `gbrain-init` can succeed against an empty
credential store. Hard-coding one provider's variable would make that path
unreachable regardless and silently mis-scope the others.

*Endpoint is explicitly out of scope here.* A local runner also needs to know
*where* to connect, and that address is deployment configuration, not a
credential — it would belong in user state, the way the radar embedder's
endpoint already is, never in `.env` or the credential store. But nothing in
this change builds that path: no state file, no read side, no settings field.
`gbrain-init` against a local provider succeeds and injects nothing, which is
real and tested, but the resulting brain then falls back to GBrain's own
default endpoint, which is not guaranteed to resolve inside the container.
Credential-free is proven; reachable is not. See `proposal.md` Non-Goals.

*`--embedding-dimensions` is optional.* GBrain derives a default from the model,
and that default is right for some models and surprising for others — it sizes
`openai:text-embedding-3-large` at 1536 rather than the model's native 3072. The
flag exists as an override because the value is baked into the schema
permanently, not because the operator should normally supply it.

*No `--skip-embed-check`.* GBrain probes the endpoint at init, but the probe is
non-fatal and fast, and its warning names precisely what is missing. Passing the
flag through would add configurability that buys nothing.

### The embedding model is locked once chosen

The command initialises exactly once. Asked to run against an initialised brain,
it refuses and names the model already in the schema. It offers no `--force`.

*Rationale:* GBrain enforces this itself — `gbrain init --force` with different
dimensions exits 1 with "Refusing to silently re-template existing brain" and
prints the destructive migration it would require. Our surface should state that
truthfully rather than offer a flag whose only outcomes are a no-op or data
loss. Recorded in the spec so that a future dashboard surface inherits the same
semantics: a one-time choice before init, read-only after.

### GBrain readiness has three states, not two

`_check_gbrain` reports: not initialised; initialised but the selected
provider's credential is missing; ready. The first two are failed checks naming
knowledge search as unavailable.

*Rationale:* a brain can be initialised and still unable to embed — GBrain
writes `embedding_model` and reports "configured but not ready" when the key is
absent. Collapsing that into "initialised" would report a healthy GBrain whose
searches return nothing. `doctor` already exits non-zero on a fresh stack by
documented contract, so this adds detail rather than a new failure mode.

*Why our own probe:* `gbrain doctor --fast` cannot be used for this. It reports
"Overall health score: 90/100. All checks OK" and exits 0 against a brain that
does not exist.

### Search must fail loudly, not return nothing

`search_knowledge` raises when GBrain is not initialised.

*Rationale:* an empty result list is indistinguishable from "the knowledge base
has nothing on this". This is not a theoretical risk: `gbrain query` and `gbrain
search` both print `No results.` and exit 0 against a brain that does not exist,
so the silent-degradation path is the *default* behaviour unless we guard it.

## Risks / Trade-offs

**A fresh install has no brain at all** → previously the stack refused to start;
before that it worked only if a key was in `.env`. Absent-and-reported is better
than dead, and better than a permanently search-less brain. Documented in both
languages as a first-run step.

**Initialisation is a CLI step, against the UI-first goal** → accepted for now
and recorded as a follow-up rather than hidden. The alternative is a dashboard
surface, which is a larger change than unblocking a dead stack warrants. The
lock semantics are specified so that surface can be added without re-deciding
them.

**The model choice is permanent and easy to get wrong** → particularly the
dimension default. Mitigated by making the choice explicit rather than implicit,
documenting the override, and refusing silently-destructive re-inits. Not
mitigated further: GBrain's own migration path is the recovery.

**Two pending changes modify the same requirements** → both this change and
`embedding-config-completeness` carry deltas for
`core-cli::next-signal doctor self-checks the environment` and
`core-container-verification::Health-check exit code semantics`. This change's
deltas are written **on top of** the other's text, so
`embedding-config-completeness` must be archived first. Archiving in the other
order will drop the embedding change's edits to those two requirements.

**Verification needs a throwaway volume** → the developer's `pstate` volume is
already initialised and would take `--migrate-only`, proving nothing. Tasks use
a named alternative project so the existing volume is never destroyed.

## Resolved Questions

### The "configure later" path does not work — RESOLVED, and it decided the design

The original decision assumed a brain could be initialised without an embedding
model and completed later. Task 5.4 established that it cannot, and follow-up
testing established why. Measured against gbrain 0.42.58.0 (pinned
`GBRAIN_REF=a25209bbb`) in a throwaway compose project:

| Action | Result |
| --- | --- |
| `gbrain config set embedding_model <id>` | exit 1 — "a file-plane field that sizes the schema… setting it in the DB has no effect (silent no-op)" |
| `gbrain init --force --embedding-model <id>` on a `--no-embedding` brain | **exit 0 but silently still deferred** — `embedding_disabled` stays `true`, no model written; `EMBEDDING_MODEL` in the environment does not override it either |
| `gbrain init --embedding-model ollama:nomic-embed-text` on a **fresh** brain | exit 0, model and dimensions written, **no credential present** |
| `gbrain init --force` with different dimensions on an initialised brain | exit 1 — "Refusing to silently re-template existing brain", prints the destructive migration SQL, config unchanged |

So `--no-embedding` is **sticky**: it is not a deferral, it is a permanent
choice. Meanwhile a first init that names its model works, and works without any
credential when the provider is local. That inverts the original trade-off —
deferring *initialisation* is cheap, deferring *the model* is impossible — and
is why the design now defers the whole init rather than performing a partial
one.

Two further behaviours were measured and are relied on above:

- `gbrain query` / `gbrain search` return `No results.` with **exit 0** both when
  embedding is disabled and when no brain config exists.
- `gbrain doctor --fast` reports **90/100, "All checks OK", exit 0** with no
  brain config at all.

Both mean GBrain cannot report this state on our behalf, so the doctor predicate
and the search guard are load-bearing rather than defensive.

## Migration Plan

None for existing installs: an initialised GBrain keeps its configured embedding
model and continues taking the `--migrate-only` path, which this change does not
touch.

A first-time install gains an explicit step before knowledge search works —
choose an embedding provider and model, save that provider's credential in
**Settings → Credentials** if it needs one, then run `next-signal knowledge
gbrain-init --embedding-model <provider>:<model>`. `next-signal doctor` names
whichever part is outstanding.

Rollback is reverting the script and the command: no schema change on our side,
and a brain that was never initialised leaves nothing to undo.
