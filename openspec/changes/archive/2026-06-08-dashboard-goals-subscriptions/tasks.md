## 1. Preconditions

- [x] 1.1 Re-read `dashboard/design/pages-other.jsx`, `dashboard/design/data.js`, and the relevant CSS in `dashboard/design/pages.css` before writing Goals/Subscriptions JSX.
- [x] 1.2 Confirm `openspec/specs/info-radar-analysis/spec.md` goal schema and `paca.workflows.info_radar_analysis.goals.load_goals` validation rules still match the proposed dashboard schema.
- [x] 1.3 Capture or confirm the real `folocli subscription list` JSON shape; if unavailable, add a minimal canned fixture based on current folocli docs/output before implementing the parser.

## 2. Goals Data Helpers

- [x] 2.1 Add an explicit dashboard YAML parser dependency if needed (for example `yaml`) and update `dashboard/pnpm-lock.yaml` via `pnpm`.
- [x] 2.2 Author `dashboard/lib/goals.ts` with typed `GoalConfig`, `readGoals()`, `validateGoals()`, and `writeGoalsAtomic()` helpers targeting `configs/info_radar/goals.yaml`.
- [x] 2.3 Mirror Python loader constraints: top-level `goals`, allowed entry keys only, non-empty `name`/`description`, string-list `topics`/`keywords`, numeric `weight`, unique names, and non-empty goal list.
- [x] 2.4 Add focused tests for the goals helper covering valid load, missing file, duplicate names, unknown keys, empty list, invalid list fields, and atomic write output.

## 3. Goals Page

- [x] 3.1 Add server actions for save/add/delete flows that call the goals helper, return structured `{ ok, message }` results, and never write invalid data.
- [x] 3.2 Implement `dashboard/app/goals/page.tsx` matching the committed Goals mock: page title/subtitle, add button, goal cards, edit panel, chip editors for topics/keywords, weight input, and toasts.
- [x] 3.3 Keep existing goal names read-only in edit mode; implement rename as delete + add only.
- [x] 3.4 Add missing-file and validation-error states that explain `goals.yaml` vs `goals.example.yaml` clearly.
- [x] 3.5 Manually verify editing a real or copied `configs/info_radar/goals.yaml` updates the file and the page refreshes without breaking `uv run paca doctor`.

## 4. Folo Subscription Integration

- [x] 4.1 Extend `src/paca/integrations/info_radar/folo.py` with `subscription_list()` using `default_argv()`, timeout, JSON envelope parsing, and loud `RuntimeError` paths consistent with `entry_get()`.
- [x] 4.2 Add a normalized subscription row shape with stable fields for dashboard use: title, feed URL, category/view, unread count when available, and updated timestamp/text when available.
- [x] 4.3 Add `paca info-radar subscriptions --json` CLI command that calls the integration and prints JSON-safe normalized rows.
- [x] 4.4 Add Python tests for successful parsing, auth/non-ok envelope, malformed JSON, timeout, and `FOLO_CLI_ARGV` override behavior.

## 5. Subscriptions Page

- [x] 5.1 Add `dashboard/lib/subscriptions.ts` server helper that invokes `uv run paca info-radar subscriptions --json`, parses output, and returns structured success/error state.
- [x] 5.2 Implement `dashboard/app/subscriptions/page.tsx` matching the committed Subscriptions mock: title/subtitle, loading copy, search input, category/view chips, table, unread badges, and empty states.
- [x] 5.3 Keep subscription filtering client-side after initial server load; no URL params for v1.
- [x] 5.4 Ensure the page has no add/edit/delete controls and no code path mutates Folo subscription state.
- [x] 5.5 Manually verify the page against a successful local folocli run or fixture, plus an auth/error path.

## 6. Documentation and Specs

- [x] 6.1 Update `dashboard/README.md` so `goals` / `subscriptions` are no longer described as future-only once the pages land.
- [x] 6.2 Update `CLAUDE.md` / `AGENTS.md` current-status text to mention the two pages and the new subscription CLI.
- [x] 6.3 If implementation changes the spec contract, update this change's delta specs before marking tasks complete.

## 7. Verification

- [x] 7.1 Run focused Python tests for goals/Folo subscription helpers.
- [x] 7.2 Run focused dashboard helper tests if added.
- [x] 7.3 Run `pnpm typecheck` in `dashboard/`.
- [x] 7.4 Run `pnpm build` in `dashboard/`.
- [x] 7.5 Run `uv run pytest -q tests/test_cli_dashboard.py` plus any new focused tests.
- [x] 7.6 Run `openspec validate dashboard-goals-subscriptions --strict`.

## 8. Completion

- [x] 8.1 Review `git diff --check` and the final diff for unrelated churn.
- [x] 8.2 Mark completed tasks in this file as each implementation step lands.
