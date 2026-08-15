## Why

Two frictions that look unrelated share one root: the repo asks to be edited
before it will run, and the state a user creates afterwards is stored where a
rebuild erases it.

**Goals never reach the job that consumes them.** `/goals` is a complete, specced
editor that writes `configs/info_radar/goals.yaml`. In a container that path is
`/app/configs/info_radar/goals.yaml`, and `/app` is image-baked —
`docker-compose.yml` mounts `pstate`, `/wiki`, and `/wiki-raw`, nothing else. A
dashboard save lands in the *dashboard container's* writable layer, where the
`scheduler` cannot see it, and `docker compose build` discards it.

Verified, not inferred: a probe file written into `/app/configs/info_radar/`
inside `next-signal-dashboard-1` was absent in `next-signal-scheduler-1`. The two
`goals.yaml` copies are byte-identical today only because nothing has edited them
since the containers were created; divergence begins at the first successful save.
`core-database` folds `goals.yaml` into the evaluation `prompt_digest`, so a
divergent copy also makes eval provenance wrong.

**The stack refuses to start until `.env` is edited.**
`${WIKI_DIR:?set WIKI_DIR in .env}` is a hard precondition on `docker compose up`,
making the documented first run "clone, copy `.env.example`, open an editor, find
two absolute host paths, then start". Those paths are bind-mount *sources*,
resolved by Docker at container creation, so no dashboard could ever set them. The
fix is a default, not a UI.

## What Changes

- **The runtime goals file moves to user state.** Both readers resolve
  `STATE_ROOT / "goals.yaml"` (`/state/goals.yaml` in a container) instead of
  `configs/info_radar/goals.yaml`. `pstate` is already mounted by every app
  service, so dashboard and scheduler share one file that survives a rebuild.
- **`goals.example.yaml` stays in the repo** as shipped content and is **seeded
  into user state once, by container bootstrap**, guarded on the file's absence.
  `load_goals()` remains a pure read — a missing file still raises loudly, exactly
  as today. The `/goals` page covers every other case: a **Start from example**
  button in the empty state, and a read-only **View examples** disclosure
  available at any time.
- **An empty goals list becomes valid to persist and stays fatal to run.**
  Clearing the seeded examples is a legitimate step toward writing your own, so
  the dashboard stops rejecting a zero-length list. `load_goals()` still raises
  `RuntimeError` when a run needs goals and none exist, and `doctor` reports it as
  an actionable failed check.
- **Compose defaults the wiki mount sources** to `${WIKI_DIR:-./state/wiki}` and
  `${WIKI_RAW_DIR:-./state/wiki-raw}`, so `docker compose up` works against an
  untouched `.env`. Pointing at a real vault stays a deliberate one-line edit.
- **The application's `WIKI_DIR` contract is unchanged.** `knowledge-pipeline`
  requires that resolving the wiki root with the variable unset raises loudly with
  no hardcoded default; that stays true, because the compose `environment:` block
  still sets `WIKI_DIR=/wiki` inside every container. Only the *host mount source*
  gains a default, consumed by Docker and never by Python or Node.
- **Existing deployments migrate once.** A `configs/info_radar/goals.yaml` at the
  old path is copied into state when state has no goals file, so an upgrade never
  resets a curated list to the examples. **BREAKING** only for goal edits that
  existed solely inside a container's writable layer — those were already lost on
  every rebuild and are not recoverable.
- **The tracked `configs/info_radar/goals.yaml` is deleted.** Once goals are user
  state, a committed copy is stale by construction: the dashboard writes
  `/state/goals.yaml` and the repo file freezes at whatever it last said, while
  still looking authoritative to anyone who opens it — including the
  `radar-prompt-tuning` skill's reader. It was also the last file publishing the
  maintainer's own interests from a public repository. The migration path in
  `provision.py` stays for deployments upgrading across this change and is a
  candidate for removal in a later cleanup; `goals.example.yaml` is unaffected.
  **BREAKING** for any deployment that has not yet run bootstrap on this change:
  with the repo file gone, provisioning seeds the example instead of migrating,
  so upgrade the stack before pulling a revision that lacks it.

Deliberately out of scope: `sources.yaml`, which stays in the repo because it is
an argv descriptor — a literal command line plus a parser name that must exist in
the Python `PARSERS` registry — and so is coupled to code and to what the image
installs, unlike `goals.yaml`, which is pure user data. Also out of scope:
credential storage and readiness reporting, which are separate changes.

## Capabilities

### New Capabilities

None. This change relocates state and relaxes one validation rule; it introduces
no new capability surface.

### Modified Capabilities

- `info-radar-analysis`: `Goals declared in a single user-editable YAML` moves the
  path to user state, defines first-read seeding, and splits "file missing"
  (seeded, transient) from "goals list empty" (persistable, fatal at run time).
  `next-signal doctor checks goals.yaml` follows the new path and reports a
  configured-but-empty list as a failed check.
- `dashboard-goals`: all four requirements repoint from
  `configs/info_radar/goals.yaml` to the state file. `Goals schema preservation`
  loses its `empty goals list is rejected` scenario; `Goals page`'s missing-file
  empty state becomes a seeded-examples state.
- `core-container-verification`: `Source visibility contract` gains the fact that
  the runtime goals file lives in `/state` and is therefore live and shared across
  services, and that the `/wiki` and `/wiki-raw` bind-mount sources default to
  repo-relative paths when unset.

## Impact

**Modified code**

- `src/next_signal/workflows/info_radar_analysis/goals.py` — state-relative
  `goals_path()`, atomic seed-if-absent, empty-list error message
- `src/next_signal/core/paths.py` — the state-relative goals path
- `dashboard/lib/goals.ts` — `GOALS_PATH` via `stateRoot()`; example path stays
  repo-relative; matching seed-if-absent
- `dashboard/lib/actions/goals.ts` — the empty-list rejection goes
- `dashboard/components/goals/goals-editor.tsx` — deleting the last goal allowed,
  with an explicit empty state
- `dashboard/lib/i18n/dictionaries.ts` — both locales
- `docker-compose.yml` — `:-` defaults on both wiki sources in both anchors
- `scripts/container_bootstrap.sh` — one-time migration from the old repo path
- `src/next_signal/interfaces/cli.py` — the doctor goals check

**Deleted**

- `configs/info_radar/goals.yaml` — tracked user data superseded by the state
  file; read by nothing after migration

**Unchanged on purpose**: `configs/info_radar/goals.example.yaml`,
`configs/info_radar/sources.yaml`, `collectors/info_radar/loader.py`, and every
`WIKI_DIR` resolution site in `core/paths.py` and `dashboard/lib/paths.ts`.

**Dependencies**: none added. No new UI primitive, so no `/design` entry.

**Docs** (bilingual pairs, both sides in this change): `README.md` quick start
(the `$EDITOR .env` step and the "only two values are required" paragraph both
go), `docs/operations.md` (goals location, seeding, empty-list semantics),
`docs/containerized-deployment.md` (quickstart prerequisites and the mount table),
`docs/modules/info_filter.md`, `.env.example` (the wiki section becomes
optional-with-a-default), plus `README.zh-CN.md` and the `docs/zh/` mirrors.
`CLAUDE.md` names `configs/info_radar/goals.yaml` as required and must follow.

**Verification**: `/app` is image-baked, so `docker compose build` must precede any
`exec` check. The decisive test is the one that found the bug — save through
`/goals`, then read the file from the `scheduler` container and confirm it
matches. `next-signal doctor` spends no model tokens; a full `info-radar analyze`
does.
