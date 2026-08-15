## 1. Goals file location — Python

- [x] 1.1 Add the runtime goals path to `src/next_signal/core/paths.py` as a `STATE_ROOT`-relative value, beside the existing state consumers. Do not give it a repo-relative fallback.
- [x] 1.2 Repoint `goals_path()` in `src/next_signal/workflows/info_radar_analysis/goals.py` from `CONFIGS_DIR / "info_radar" / "goals.yaml"` to the new state path. Keep the example path repo-relative — `goals.example.yaml` remains shipped content.
- [x] 1.3 Update the module docstring and every error message naming `configs/info_radar/goals.yaml` so the loader's failure text points at the file the operator can actually edit.

## 2. Goals file location — dashboard

- [x] 2.1 In `dashboard/lib/goals.ts`, resolve `GOALS_PATH` through `stateRoot()` from `lib/paths.ts`. Leave `GOALS_EXAMPLE_PATH` resolving under `REPO_ROOT`.
- [x] 2.2 Confirm `writeGoalsAtomic` writes its temporary file in the same directory as the target — the state directory now — so the rename stays atomic and never crosses a filesystem boundary into the image layer.
- [x] 2.3 Update `dashboard/lib/goals.test.ts` fixtures for the new path resolution.

## 3. Provisioning at bootstrap

- [x] 3.1 Provision the runtime goals file from `scripts/container_bootstrap.sh`, which already runs one-time setup before `dashboard` and `scheduler` start. Do not provision from any read path.
- [x] 3.2 Seed from `configs/info_radar/goals.example.yaml` and nothing else. Do **not** implement a migrate-from-`configs/info_radar/goals.yaml` branch: this change deletes that file and no compose service bind-mounts `configs/`, so the branch could never fire on an image built from this revision (D7). Operators upgrading with a curated list copy it into state by hand, per the migration plan.
- [x] 3.3 **Guard on the state file's existence, never on its goal count.** A count-based guard would restore the example goals on the next `docker compose up` after an operator deliberately cleared them. This is the detail most likely to be implemented wrongly.
- [x] 3.4 Write atomically — temporary file inside the state directory, then move into place — so a partially written file is never observable, and repeated `docker compose up` runs are idempotent.
- [x] 3.5 Keep `load_goals()` a pure read: it must not create, modify, or repair the file. A missing file raises `RuntimeError` naming the resolved state path.
- [x] 3.6 Verify `goals.example.yaml` passes `load_goals()` unmodified — it must remain a valid runtime document, not a commented-out template.
- [x] 3.7 Delete the tracked `configs/info_radar/goals.yaml`. A committed copy of a file the dashboard now writes elsewhere is stale by construction and still reads as authoritative; it was also the last file publishing the maintainer's own interests from a public repo. Leave `goals.example.yaml` untouched.

## 4. Empty-list semantics

- [x] 4.1 Remove the empty-list rejection from `dashboard/lib/actions/goals.ts` so `deleteGoal` may produce a zero-length list. Keep every other validation: unique kebab-case names, required fields, no unknown keys.
- [x] 4.2 Allow deleting the last goal in `dashboard/components/goals/goals-editor.tsx`, and render an explicit state when the list is empty saying analysis will fail until at least one goal exists. Do not disable the delete control.
- [x] 4.3 Keep `load_goals()` raising `RuntimeError` on an empty `goals:` list, with a message naming the empty list as the cause and pointing at `/goals`, distinct from a parse error and from a missing file.
- [x] 4.4 Add a **Start from example** control to the empty state (and to the missing-file state) that copies `goals.example.yaml` into the runtime goals file on click. Rendering the page must never write; only this control does.
- [x] 4.5 Add a read-only **View examples** disclosure available in every state, rendering `goals.example.yaml` without writing. Do not offer merging examples into a non-empty list — example names can collide with configured names, and duplicates are rejected.
- [x] 4.6 Add both locales' strings for the empty state, the missing-file state, **Start from example**, and **View examples** to `dashboard/lib/i18n/dictionaries.ts`. Reuse existing primitives; add no `/design` entry.

## 5. Doctor

- [x] 5.1 Update `_check_goals_yaml()` in `src/next_signal/interfaces/cli.py` to report the resolved state path.
- [x] 5.2 Report a configured-but-empty list as a failed check with an actionable message ("no goals configured — add one on /goals"), distinct from the parse-error message.

## 6. Compose defaults

- [x] 6.1 Replace `${WIKI_DIR:?set WIKI_DIR in .env}` with `${WIKI_DIR:-./state/wiki}` and `${WIKI_RAW_DIR:?...}` with `${WIKI_RAW_DIR:-./state/wiki-raw}` in both the `x-app` and `x-app-with-coding-agent-auth` anchors — four occurrences total.
- [x] 6.2 Keep the `./` prefix. Without it Compose parses the value as a named volume rather than a bind mount, producing a silently empty wiki instead of an error.
- [x] 6.3 Leave the `environment:` block's `WIKI_DIR: /wiki` and `WIKI_RAW_DIR: /wiki-raw` untouched — the application contract that an unset variable raises loudly must stay true.
- [x] 6.4 Scope the default to Docker Desktop on macOS/Windows, where the file-sharing layer maps ownership. Do **not** add UID/GID plumbing or committed placeholder directories: on native Linux Docker Engine the daemon creates a missing bind source root-owned, which leaves the stack working but requires `sudo chown -R $USER state/` before the operator can edit their own wiki. Document that in 8.3 rather than automating around it.
- [x] 6.5 Update `.env.example`: `WIKI_DIR` / `WIKI_RAW_DIR` become optional, documented as host paths defaulting to repo-relative directories, with the placeholder values removed so `:-` actually fires.

## 7. Tests

- [x] 7.1 Python: loading resolves the state path; a missing file raises `RuntimeError` **and creates nothing**; an empty `goals:` list raises with a distinct message; duplicate names and unknown keys still raise.
- [x] 7.2 Provisioning is idempotent — a second run does not overwrite an existing file, whatever it contains.
- [x] 7.3 Provisioning does not repopulate an emptied list: with a state file holding an empty `goals:` list, a further run leaves it empty. This is the regression test for task 3.3.
- [x] 7.4 Provisioning fails loudly when the example source is missing, rather than creating an empty or partial goals file.
- [x] 7.5 Dashboard: `goals.test.ts` covers state-path resolution, that rendering writes nothing, that **Start from example** writes the examples, and that saving a zero-length list now succeeds.
- [x] 7.6 Use `tmp_path` with a patched `STATE_ROOT` rather than mocking the filesystem, per the project's fixture-over-mock rule.

## 8. Docs — bilingual, both sides in this change

- [x] 8.1 `README.md` + `README.zh-CN.md`: drop the `$EDITOR .env` step and the "only two values are required before the stack starts" paragraph from Quick start; state that `docker compose up` works against an untouched `.env` and where the wiki lands by default.
- [x] 8.2 `docs/operations.md` + `docs/zh/operations.md`: the goals file's new location, first-read seeding, empty-list semantics, and the one-time migration.
- [x] 8.3 `docs/containerized-deployment.md` + `docs/zh/`: quickstart prerequisites, and the volume/mount table now that the wiki sources have defaults and goals live in `pstate`.
- [x] 8.4 `docs/modules/info_filter.md` + `docs/zh/`: the goals file location.
- [x] 8.5 `CLAUDE.md`: the info-radar section names `configs/info_radar/goals.yaml` as required; update it and any other reference to the old path.
- [x] 8.6 Grep the tree for `configs/info_radar/goals.yaml` and confirm every remaining hit is deliberately about the example file or archived change content.

## 9. Verification

- [x] 9.1 `uv run pytest -q` green, including the new cases.
- [x] 9.2 `docker compose build` before any container check — `/app` is image-baked, so an `exec` against a stale image verifies the previous code.
- [x] 9.3 Decisive test: edit a goal through `/goals` in the dashboard, then read `/state/goals.yaml` from the `scheduler` container and confirm it matches. This is the exact divergence the change exists to fix.
- [x] 9.4 Confirm goals survive a rebuild: save a goal, run `docker compose build && docker compose up -d`, confirm the edit is still present.
- [x] 9.5 Confirm the wiki mounts resolve as bind mounts, not named volumes, with `.env` untouched — inspect the resolved mount type rather than concluding from a successful start.
- [x] 9.6 `next-signal doctor` reports the state goals path and passes; delete every goal and confirm it reports the empty list as an actionable failure, distinct from the missing-file message. Doctor makes no model calls; do not run a full `info-radar analyze` for this.
- [x] 9.7 Confirm an emptied goals list survives a restart: delete every goal, run `docker compose up -d` again, and confirm bootstrap has not restored the example goals.
