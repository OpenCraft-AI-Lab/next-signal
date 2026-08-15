## Context

`~/.next-signal/` (`/state`, the `pstate` named volume) already holds every
user-editable runtime file the settings page owns: `language.json`,
`schedule.json`, `engine.json`, `embedding.json`, `coding-agents.json`. Each is
written by the dashboard, read by the pipeline at call time, and survives a
rebuild because the volume is not the image.

`goals.yaml` is the same kind of thing — pure user data behind a first-class UI —
but was never moved. It lives in `configs/`, which the Dockerfile copies into
`/app`. `core-container-verification` already states that `/app` is image-baked
and must not be assumed live; the `/goals` editor was built against the opposite
assumption. The `dashboard` and `scheduler` services run from the same image but
are separate containers, so each has its own writable layer — which is why a
dashboard save is invisible to the job that consumes it.

The second half of this change has no runtime component at all. Compose resolves
`${WIKI_DIR:?...}` before it creates a container, so the requirement to edit
`.env` is enforced by the orchestrator, not by next-signal. Nothing in the
application can relax it; only the compose file can.

## Goals / Non-Goals

**Goals:**

- One goals file, shared by dashboard and scheduler, surviving rebuilds.
- A fresh install has working, editable goals with no manual step.
- `docker compose up` succeeds against an untouched `.env`.
- Clearing the seeded examples is possible without fighting a validator.

**Non-Goals:**

- Moving `sources.yaml` or giving it a UI. It is executable configuration.
- Changing how the application resolves `WIKI_DIR`, which must keep failing
  loudly when unset.
- Per-goal files, goal history, or import/export.
- Credential storage and readiness reporting — separate changes.

## Decisions

### D1. Resolve the runtime goals file from `STATE_ROOT`

The file becomes `STATE_ROOT / "goals.yaml"` on both sides — `/state/goals.yaml`
in a container, `~/.next-signal/goals.yaml` host-native. This is the smallest move
that makes it shared, because `pstate` is already mounted by `bootstrap`,
`dashboard`, and `scheduler` through the `x-app` anchor. No compose change is
needed to make goals shared; only to make the wiki optional.

*Alternative considered:* bind-mount `configs/info_radar/` into the containers. It
would fix sharing while leaving the file inside deployment code, so `goals.yaml`
would remain a tracked repo file that users are told to edit — and `git pull`
would then conflict with their content. Rejected.

### D2. Seed once at bootstrap; never from a read path

The requirement is narrow: **a fresh install should have example goals to look
at.** That is a setup concern that happens once, and setup already has a home.
`scripts/container_bootstrap.sh` runs before `dashboard` and `scheduler` start —
both declare `depends_on: bootstrap: service_completed_successfully` — and already
performs exactly this category of one-time work when it creates the database
schema.

So bootstrap seeds, and `load_goals()` stays a pure read: a missing file raises
`RuntimeError`, unchanged from today.

**The guard is file existence, not goal count.** Now that an empty `goals:` list is
legal (D3), a guard phrased as "if there are no goals, seed the examples" would
silently resurrect the examples on the next `docker compose up` after an operator
deliberately cleared them. That behaviour would be indistinguishable from a bug.

The `/goals` page covers everything bootstrap does not, with the write attached to
an explicit user action rather than to a page render:

- **Start from example** — shown in the empty state, writes the examples in.
- **View examples** — available in any state, renders `goals.example.yaml`
  read-only. This exists because the two wants are different: with no goals you
  want the file populated; with goals of your own you want to *read* the examples
  for reference, and should not have to delete your work to reach them.

Merging examples into a non-empty list is deliberately not offered. Example goal
names can collide with the operator's, duplicate names are rejected by the schema,
and inventing a skip-or-rename rule is scope this change does not need.

*Alternative considered — seeding inside the read path, in both readers.* It buys
one tidy invariant ("the file always exists") and covers host-native installs
without bootstrap. Rejected on two counts. First, what it actually produces for a
fresh host-native `next-signal info-radar analyze` is a run against *somebody
else's goals* instead of a clear "no goals configured" error — worse behaviour
dressed as convenience, and contrary to this project's fail-loud rule. Second, it
puts a filesystem write where every caller — tests, health checks, dry runs —
reasonably expects a pure read.

*Consequence accepted:* a host-native install that never runs bootstrap has no
goals file until the operator opens `/goals` or the loader tells them so. The
loud error is the correct outcome there, not a gap to paper over.

### D3. Separate "missing" from "empty", and give them different fates

These were conflated. The current requirement says *"a missing or empty
`goals.yaml` SHALL raise `RuntimeError`"*, which is why the dashboard also had to
reject a zero-length list.

| State | Persisting it | Running analysis |
|---|---|---|
| file absent | n/a — nothing to persist | `RuntimeError`, loud (unchanged) |
| `goals:` empty | **allowed** — the dashboard saves it | `RuntimeError`, loud |
| one or more goals | allowed | normal |

Missing and empty both abort a run, but they SHALL carry different messages: one
means "no goals file yet", the other means "you cleared them". Collapsing them
into one error is what made the dashboard reject an empty list in the first place.

The split serves a real workflow: replacing seeded examples with your own. Under
the old rule the operator had to add before deleting, in that order, or be
rejected. The run-time guarantee is unchanged — analysis still refuses to run
without goals and never falls back to an implicit default goal.

### D4. Report a configured-but-empty list as a failed doctor check

`load_goals()` raises on empty, so `doctor` fails for free. Only the message
changes: distinguish "no goals configured — add one on /goals" from a parse error,
so the failure is actionable rather than looking like corruption. This keeps
`doctor`'s exit code meaningful for a state an operator can now deliberately
create and then forget about.

### D5. Default the mount source in Compose, keep the app contract untouched

`${WIKI_DIR:-./state/wiki}` uses `:-`, which substitutes when the variable is unset
**or empty** — necessary because `.env.example` ships the key present and blank
rather than absent.

**The `./` prefix is mandatory.** Compose parses a bind-mount source without a
leading `./` or `../` as a *named volume*, so `${WIKI_DIR:-state/wiki}` would
silently create a volume instead of using a directory, and the operator's wiki
would appear empty with no error. This is the highest-risk detail in the change.

`state/` is already gitignored, so the default lands untracked.

The `knowledge-pipeline` contract — no hardcoded default, loud `RuntimeError` when
unset — is deliberately **not** modified. Inside a container `WIKI_DIR` is always
set, to `/wiki`, by the compose `environment:` block, which overrides `.env` by
design. The default added here is consumed by Docker when it builds the mount, and
never by Python or Node.

### D6. Cross-platform behaviour of the relative default

Compose resolves a relative bind source against the project directory, so the
result is deterministic on every platform. This is *safer* than the status quo,
where the operator hand-types an absolute path: the running stack currently shows
one bind stored as `/run/desktop/mnt/host/c/Users/...` and another as raw
`C:\Users\...`, so hand-written Windows paths are already normalized
inconsistently. A repo-relative default removes the chance to get it wrong.

**The supported platform is Docker Desktop on macOS and Windows.** There, the
file-sharing layer maps ownership, so a directory Docker creates for a missing
bind source is usable both by the container and by the operator on the host. No
extra step is needed and none is added.

**Native Linux (Docker Engine directly) is explicitly out of scope for this
default.** The daemon runs as root and creates a missing bind source `root:root`.
The stack still works — the container runs as root and reads and writes the wiki
normally — but the operator's own account cannot write into `state/wiki` without
`sudo chown -R $USER state/`. Docker Desktop for Linux uses a VM and behaves like
macOS, so this affects Docker Engine specifically.

Making that seamless was considered and rejected. Passing a host UID/GID into
Compose so bootstrap could `chown` the mounts would reintroduce a variable in
`.env` — in a change whose entire purpose is that the operator never opens that
file. Committing placeholder directories through `.gitignore` negation would work
on every platform but buys a stanza of fiddly ignore rules for a platform this
project does not currently target. The scope decision is to document the
behaviour instead, in `docs/containerized-deployment.md` and its mirror.

Pre-existing conditions this change does not alter: bind mounts through the Docker
Desktop VM are slow for many small files; macOS is case-insensitive while the
container is not; Windows `MAX_PATH` can bite on deep taxonomy plus long titles.

### D7. Delete the tracked repo-path goals file, and do not migrate from it

`configs/info_radar/goals.yaml` is deleted. A committed copy of a file the
dashboard now writes elsewhere is stale the moment anyone saves, while still
reading as authoritative — and it was the last file publishing the maintainer's
own interests from a public repository.

**No migrate-then-seed step is implemented, because it could never run.** The
obvious version — "if the old repo file exists and the state file does not, copy
it in first" — reads `/app/configs/info_radar/goals.yaml`. `configs/` is baked
into the image and no compose service bind-mounts it, so on any image built from
this revision that path is absent *by construction*: the same change deleted it.
The branch would be unreachable code carrying the authority of a guarantee, which
is worse than no branch at all. Provisioning therefore has exactly one source,
`goals.example.yaml`, and one guard, the state file's existence (D2).

*Consequence accepted, and the reason this is called out in the migration plan:*
an operator upgrading with a curated repo-path goals file gets the examples
seeded, not their list. The honest remedy is a documented one-line copy before
upgrading, not a code path that cannot fire.

*Deliberately not attempted:* recovering goal edits that only ever existed inside
a container's writable layer. They were already lost on each rebuild, and guessing
which layer to read would be worse than saying so plainly.

## Risks / Trade-offs

- **Omitting the `./` prefix** → produces a named volume and a silently empty
  wiki. Mitigation: a verification step that inspects the *resolved mount type*,
  not merely that the stack started.
- **Re-seeding over a deliberately emptied list** → the operator clears the
  examples, and the next `docker compose up` brings them back. Mitigation: the
  bootstrap guard tests file existence, never goal count (D2). This is the single
  detail most likely to be implemented wrongly.
- **Two places copy the example** (bootstrap and the `/goals` button) → drift.
  Mitigation: both are explicit, neither is hidden inside a read, and the copied
  content is a file rather than schema logic.
- **A host-native install has no goals file until setup happens** → a fresh
  `info-radar analyze` fails. Accepted deliberately: that is the correct loud
  failure, and the message points at `/goals`.
- **Native Linux gets root-owned default wiki directories** → the operator cannot
  edit their own wiki without `chown`. Accepted and documented rather than fixed
  (D6): the supported platform is Docker Desktop on macOS/Windows, and every
  automated fix costs more than the papercut.
- **A deliberately empty goals file looks like a broken install** to anyone reading
  only the file. Mitigation: D4's actionable doctor message and the dashboard's
  explicit empty state.
- **Seeded examples are somebody else's interests** → harmless in practice: the
  scheduler treats an absent `schedule.json` as disabled, so a fresh install cannot
  spend tokens scoring against the examples until the operator turns the schedule
  on.
- **An upgrader's curated repo-path goals file is replaced by the examples** →
  they never asked for somebody else's interests. Mitigation: a documented copy
  step before upgrading (Migration Plan) and the old content's presence in git
  history. Not mitigated in code, deliberately — see D7.

## Migration Plan

1. **Before upgrading**, an operator with a curated `configs/info_radar/goals.yaml`
   copies it to `~/.next-signal/goals.yaml` — or, in a running stack,
   `docker compose cp` it to `/state/goals.yaml`. This is the only step that needs
   doing by hand, and it exists because the file is deleted rather than migrated
   (D7). Skipping it is recoverable: the old content is in git history.
2. Ship the readers pointing at `STATE_ROOT`. The tracked repo-path file is
   deleted in the same revision.
3. On the first `docker compose up` after upgrade, bootstrap seeds
   `goals.example.yaml` into state if and only if no state file exists — so a
   goals file copied in at step 1 is left alone. Host-native installs populate
   state when the operator opens `/goals`, or receive a loud, actionable error
   from the loader before then.
4. Compose defaults take effect on the next `docker compose up`. An operator with
   `WIKI_DIR` already set in `.env` sees no change at all.

**Rollback:** revert the change and restart. The state file remains on the volume
and is ignored by the reverted readers, which resume using the repo path — so a
rollback loses edits made after the upgrade but corrupts nothing.

## Open Questions

None blocking. One worth revisiting after this ships: `sources.yaml` is the same
category of "which feeds do I follow" data as goals, but its current shape is an
argv descriptor coupled to the `PARSERS` registry and to what the image installs.
It stays put here. When a second source lands and a UI is warranted, expose only
the safe knobs (`enabled`, `--limit`, `--view`) and keep `argv` and `parser` in
code — a browser-writable `argv` is arbitrary command execution.
