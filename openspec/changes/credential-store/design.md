## Context

See proposal.md — Why. The constraints that shaped this design, discovered while
surveying the current code:

- **Credential consumers come in three shapes**, and only the first is a
  mechanical substitution:
  1. *Our Python reads the value* — `DEEPSEEK_API_KEY`, `OPENAI_API_KEY` (embedder),
     `GITHUB_TOKEN`, `OMLX_API_KEY`.
  2. *agno reads it inside the SDK* — `_build_claude`, `_build_openai`, and
     `_build_gemini` never pass `api_key`, and each agno class falls back to its
     own `getenv` when constructed without one.
  3. *A child process reads it from its own environment* — all three
     `subprocess.run` calls in `integrations/info_radar/folo.py` omit `env=`, so
     `folocli` receives `FOLO_TOKEN` purely by inheriting ours.
- **`dashboard` and `scheduler` are separate containers** off one image. A
  process's environment is fixed at fork, so nothing one container does can alter
  another's `os.environ`.
- **`_build` is `lru_cache`d**; `get_stage_model` is not. A cached model holds
  whatever credential it was constructed with.
- **`configs/coding_agents.yaml` sets `inherit_env: []`** for both providers, and
  the `stage` profile pairs that with `tool_access: none` — a deliberate wall
  between production LLM stages and credentials.
- **`dashboard/lib/state-file.ts` cannot produce `0600`** — it writes with
  `writeFile(tmp, payload, "utf-8")` (mode `0644`) and `rename` preserves that.
- **`/root/.folo` is backed by no volume** in `docker-compose.yml`, and
  `folocli login` cannot complete inside a container regardless: it serves its
  own callback with `server.listen(0, "127.0.0.1")` and hands Folo a
  `cli_callback` pointing at that ephemeral port, which resolves to the host —
  not the container — in the operator's browser.
- **Folo issues no API token.** Its credential is a better-auth session value
  (`better-auth.session_token`), obtained by exchanging a one-time token at
  `/better-auth/one-time-token/apply` or `/verify`. There is no page that mints
  one, so the only manual routes are copying a browser cookie or reading a local
  `folocli` config file.

## Goals / Non-Goals

**Goals:**

- One module owns credential persistence, so a later move to a real secret
  manager touches one file.
- The rule "no credential is read from the environment" is enforceable by grep
  rather than by review judgment.
- A credential saved in the dashboard is in effect on the next use in every
  process, with no restart.
- A credential reaches a subprocess only where a call site named it.

**Non-Goals:**

- Encryption at rest. The store is plaintext on the state volume, the same threat
  model as `.env`; this was decided on UX grounds with the trade-off understood.
- Any migration, import, or environment fallback — see Decision 2.
- Per-credential validation against the provider. Nothing here issues a network
  request to check whether a key works; that stays with the code that uses it.
- The readiness banner (F5) and the embedding configuration rework (F4).

## Decisions

### 1. Read at call time; never materialize into `os.environ`

**Chosen:** every consumer reads `secrets.json` at the point of use. Nothing
writes to `os.environ`.

**Alternative considered — load the store into `os.environ` at process startup,
with a handler that refreshes it when the file changes.** Rejected on three
counts:

- *The refresh cannot be built as described.* The dashboard writes the file; the
  scheduler is a different container. No signal, shared volume, or privilege lets
  one process mutate another's environment. The only implementation is a watcher
  inside every process polling the file.
- *Once every process polls, the environment layer is pure cost.* Both designs
  perform the same read. The environment version adds a staleness window bounded
  by the poll interval, plus a watcher per process; call-time reading has neither.
  A stale credential presents as a 401 from a key the UI displays as correct.
- *It leaks by default.* `dashboard/lib/actions/spawn-cli.ts` spawns children with
  `env: { ...process.env }`. Materializing credentials into the dashboard's
  environment sends every credential to every child it spawns, silently crossing
  the `inherit_env: []` boundary. Secrets arriving everywhere and being subtracted
  by allowlists is the wrong direction.

Startup-only loading was rejected for a fourth reason: it reproduces
"edit, then recreate the container", which is the problem the change exists to
remove.

### 2. No migration, no import, no fallback

**Chosen:** the store is the only source from the first commit. Nothing reads a
credential environment variable, including diagnostics.

**Alternative considered — read the environment as a fallback, or offer a
one-click import from it.** Rejected: the repo has no deployed users, so both
serve nobody. More importantly, either one requires at least one module that
legitimately reads credential env vars, which turns an absolute rule into a
judgment call and leaves a path where a stale `.env` silently satisfies a
credential the UI reports as unset.

The cost is that any existing local checkout must re-enter its keys once. That is
a one-time manual step for the repo's only user, and cheaper than carrying a
compatibility path forever.

### 3. Credentials reach children through a per-spawn environment

**Chosen:** a `child_env(names)` helper reads the store at spawn time and returns
the environment dict for one `subprocess.run`.

This is the only place an environment variable is still involved, and it is
unavoidable: `folocli` is not our code and accepts a token no other way. Building
it per spawn keeps call-time freshness, keeps the allowlist positive and local to
the call site, and leaves our own environment untouched.

It follows an established convention rather than introducing one — `gbrain_env()`
and `coding_agents/runner.py::build_child_env()` already build child environments
explicitly, for the same reason.

**An absent credential is omitted, not passed as `""`.** Forcing a loud failure by
injecting an empty value would delegate our failure mode to a third party's
empty-string handling, and the resulting message would be folocli's rather than
ours. Instead the caller checks and raises before spawning.

### 4. Cloud model constructors get `api_key` explicitly, and raise first

`agno/models/anthropic/claude.py` does `self.api_key = self.api_key or getenv("ANTHROPIC_API_KEY")`;
Gemini and the OpenAI classes do the same. Passing `None` therefore hands
resolution back to the environment — the exact fallback this change removes,
hidden inside a dependency where no grep of our source would find it.

So the factory resolves the credential, raises `RuntimeError` naming it when
absent, and only then constructs. `_build`'s existing `RuntimeError` → 
`fallback_profile` path means a missing cloud credential degrades to the
configured fallback profile rather than hard-failing, which is the established
behavior for an unavailable provider.

### 5. Writing the store invalidates the model cache

`_build` is `lru_cache`d, so an AgentOS agent built once holds its credential for
the process's life. `reset_cache()` already exists and is already called after
YAML edits; the store's write path calls it too. Without this, the "no restart
needed" guarantee would hold for the scheduler (which builds per job through
`get_stage_model`) but quietly fail for interactive agents — a promise true only
on the path that happened to be tested.

### 6. Keys are named after the environment variables they replace

`FOLO_TOKEN` must be spelled exactly that way in the child environment, so at
least one credential needs its literal name. Introducing logical names
(`deepseek`, `folo`) alongside would mean two identifiers for one credential and
a mapping table to keep in sync. One slightly legacy-looking name set is the
smaller cost, and it keeps `doctor` output and the docs legible.

### 7. Presence only — no last-four preview

With no migration, the only way a credential is in the store is that the user
typed it there. A masked preview disambiguates between candidates that do not
exist, and it forces a length-floor rule to avoid exposing a meaningful fraction
of a short token. `{present: boolean}` is the whole contract. Adding a preview
later is additive if a real need appears.

### 8. One Credentials section rather than inline per provider

Five of the seven credentials have no existing settings card — Anthropic, Google,
OMLX, GitHub, and Folo — so "inline" means inventing three new sections. One
section also matches the underlying fact that there is now exactly one credential
file, and it costs one touch on `embedding-section.tsx`, which F4 is rewriting
anyway. Engine and Embedding keep a presence indicator that links to it.

### 9. The dashboard hosts the Folo sign-in callback itself

**Chosen:** the dashboard starts the sign-in, receives the one-time token on its
own route, exchanges it for a session token, and stores that. `folocli` takes no
part in authenticating.

This works for one specific reason: the dashboard is already published on the
host loopback (`DASHBOARD_BIND_ADDRESS:3000`), so the operator's browser can
reach it even though it cannot reach anything else inside the container. The
address is fixed and known, unlike folocli's ephemeral callback port.

**Alternative considered — drive `folocli login` through the existing
coding-agent auth broker.** The broker is the right shape for a *device*
authorization flow: it reads a URL off the child's stdout and writes a code back
to stdin, which needs no network path from browser to CLI. Folo's flow is a
loopback redirect instead, so the browser must reach the CLI directly. In Docker
it cannot, and the port cannot be published because it is chosen at runtime.
Wiring this up would produce a Connect button that works only when the stack runs
outside its supported deployment.

**Alternative considered — paste box only.** Rejected once the token's nature was
established: with no API-token page, "paste a token" resolves to copying a
session cookie out of devtools or reading `~/.folo/config.json` after a local CLI
login. That is precisely the hand-extraction this work exists to remove, so the
credential would have gained a UI without gaining a usable path.

Manual entry remains for every credential including this one, so a failed or
unreachable sign-in is never a dead end.

**Ship it as its own commit.** The flow is a protocol integration against Folo's
API, while the rest of the change is a store plus form controls; keeping the diff
separable keeps each half reviewable and revertable on its own.

## Risks / Trade-offs

- **Plaintext on the state volume** → Accepted deliberately. Same threat model as
  the `.env` it replaces; a Docker named volume is not a vault. Confined to one
  module so a later move to a real secret manager is a single-file change.
- **`0600` is not enforceable on Windows** → The spec scopes the guarantee to the
  Linux container, which is the supported deployment. Development on a Windows
  host cannot verify it, so verification happens in the container per the
  project's Docker-verification rule.
- **A file read per credential use, instead of a process-global variable** →
  Acceptable: these are small local reads on paths that then make a network call
  to a model provider. Not worth a cache whose invalidation is the hard part.
- **A stale `.env` still sitting in a working tree looks authoritative** → The
  credential block is deleted from `.env.example`, and diagnostics never mention
  `.env` for credentials. Since nothing reads those variables, a leftover file is
  inert rather than misleading in effect — but the docs must not describe it as a
  configuration path.
- **`FOLO_TOKEN` becomes mandatory where a cached CLI session used to suffice** →
  Only affects a host-only development setup; the container path never had a
  working session file. The error names the credential and points at Settings.
- **The Folo sign-in depends on an undocumented contract** — the `cli_callback`
  parameter and the one-time-token exchange are folocli's private arrangement
  with Folo's web app, unversioned and free to change → Accepted: the project
  already pins `folocli@0.0.5` and parses its private JSON envelopes, so this is
  the same class of dependency rather than a new one. Contained by keeping manual
  entry available, so drift degrades the sign-in button rather than the
  credential. Confine the handshake to one module so a change is one edit.
- **A dashboard route that writes a credential is a new mutation surface** →
  Same-origin only, one in-flight attempt, bounded lifetime, and an HTTPS domain
  allowlist for the sign-in target — the constraints the coding-agent login
  endpoints already operate under. `DASHBOARD_BIND_ADDRESS` remains loopback by
  default for the same reason it already is.
- **The change touches seven capabilities at once** → Inherent: credentials are
  cross-cutting. Mitigated by the single-source rule, which makes the sweep
  verifiable — after implementation, no credential name appears in an
  environment read anywhere in the tree.

## Migration Plan

No data migration exists by design (Decision 2). Deployment is a rebuild:

1. `docker compose build && docker compose up -d`.
2. Open Settings → Credentials and enter each credential the deployment uses.
3. `next-signal doctor` confirms presence; the folocli and embedder checks turn ✓.

Rollback is `git revert` plus restoring credential values into `.env`; the store
file is inert to the previous revision and can be left in place.
