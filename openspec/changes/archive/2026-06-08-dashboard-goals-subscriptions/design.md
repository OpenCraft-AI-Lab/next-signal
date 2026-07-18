## Context

The dashboard shell already has `Goals` and `Subscriptions` nav entries. The foundation spec allowed those links to be placeholders, and `dashboard-radar` explicitly left `dashboard-goals` and `dashboard-folo-subs` as future work. The design mocks for both pages exist in `dashboard/design/pages-other.jsx`.

`info-radar` analysis already treats `configs/info_radar/goals.yaml` as a required runtime input. The canonical Python loader (`paca.workflows.info_radar_analysis.goals.load_goals`) enforces a small schema and fails loudly on missing, empty, duplicate, or unknown-key configs. Folo auth and CLI invocation are already represented in `paca.integrations.info_radar.folo`, but that module does not yet expose subscription listing.

## Goals / Non-Goals

**Goals:**

- Turn `/goals` and `/subscriptions` into real dashboard pages matching the committed mocks.
- Let the operator edit `configs/info_radar/goals.yaml` without leaving the dashboard, while preserving the strict analysis schema.
- Let the operator inspect current Folo subscriptions from the dashboard without editing Folo state.
- Keep provider auth, pinned folocli argv, and subprocess error handling consistent with the existing Folo integration.
- Keep the pages local-user only; no auth layer, no multi-user goal profiles.

**Non-Goals:**

- Editing Folo subscriptions from the dashboard.
- Changing the `goals.yaml` schema or adding per-user/per-agent goal sets.
- Triggering `paca info-radar analyze` automatically after a goal edit.
- Storing goals in Postgres.
- Replacing `configs/info_radar/sources.yaml` or the collector source definitions.

## Decisions

### D1: One change, two capabilities

Use one change (`dashboard-goals-subscriptions`) because the nav exposes both missing pages and both pages are control-plane surfaces for `info-radar`. Keep specs separate as `dashboard-goals` and `dashboard-folo-subscriptions` so each page has a focused contract and can be archived independently into main specs.

Alternative considered: two changes (`dashboard-goals`, `dashboard-folo-subs`). That is cleaner in isolation, but it leaves the nav half-fixed and duplicates design/app-shell work.

### D2: `/goals` writes the existing YAML file, not a new store

`configs/info_radar/goals.yaml` remains the source of truth. Dashboard server helpers read it, validate entries against the same fields as the Python loader, then write the full document atomically (`goals.yaml.tmp` + rename). The page displays the file path and makes saves explicit via server actions and toasts.

Use a real YAML parser/emitter in the dashboard package instead of ad hoc string manipulation. If no direct YAML package is available, add a small explicit dependency such as `yaml`; do not rely on a transitive `js-yaml` from another package.

Alternative considered: call Python `load_goals()` for validation and a Python writer for persistence. That would guarantee parser parity but adds a CLI/write boundary just for a simple schema. The dashboard can keep a compact TS validator and back it with tests; the analysis loader remains the runtime authority.

### D3: Goal names are immutable after creation

Existing `name` values are stable identifiers used in prompts and mental models. Editing an existing card may change `description`, `topics`, `keywords`, and `weight`; renaming is modeled as delete + add. The UI follows the mock: name appears in a disabled mono input inside the edit panel.

Alternative considered: allow rename and update the array entry in place. That creates duplicate-name and identity edge cases with little value for v1.

### D4: `/subscriptions` reads through a Python CLI boundary

Add `paca.integrations.info_radar.folo.subscription_list()` and expose it through a small CLI command such as `uv run paca info-radar subscriptions --json`. The dashboard server helper invokes the CLI and parses the JSON envelope. This keeps Folo argv selection (`FOLO_CLI_ARGV` override, pinned default), auth behavior, timeout behavior, and error messages in Python integration code rather than duplicating provider rules in Next.js.

Alternative considered: have the dashboard run `npx --yes folocli@0.0.5 subscription list` directly. That is shorter but duplicates the integration contract and makes future Folo CLI changes harder to contain.

### D5: Subscriptions page is read-only with client-side filtering

The server fetches the full subscription list once per request. Search text, category/view filters, and empty states are client-side page state; they do not write URL params in v1. The page shows cold-start loading copy because `npx --yes folocli@<version>` can take tens of seconds on first run.

Alternative considered: URL-backed filters via `nuqs`. Useful later, but subscriptions are an operator inventory page rather than a sharable analytical view.

### D6: Error states are loud but local

`/goals` save errors show exact validation messages and do not write partial files. `/subscriptions` shows an error panel when Folo auth/CLI fails and points the operator toward `paca doctor`/Folo auth; it does not silently render an empty table.

## Risks / Trade-offs

- **Risk: TS goal validation drifts from Python loader.** → Mitigation: keep the schema tiny, mirror the allowed-key list, add dashboard helper tests for duplicate names / unknown keys / empty goals, and keep Python loader as runtime authority for analysis.
- **Risk: two browser tabs edit goals concurrently and last write wins.** → Mitigation: v1 is single local user; save writes the whole file atomically. A future change can add file mtime conflict detection if needed.
- **Risk: YAML formatting/comments are not preserved.** → Mitigation: generated YAML is canonical and simple. The user-editable source remains clear; comments from the original file are not a v1 guarantee.
- **Risk: folocli output shape differs from assumptions.** → Mitigation: Python parser normalizes to stable dashboard rows and raises on missing envelope/data shape, with tests using canned CLI output.
- **Risk: cold `npx` makes `/subscriptions` feel slow.** → Mitigation: explicit loading state and timeout. No background polling in v1.

## Migration Plan

1. Add helper code and tests for reading/writing goals.
2. Add Folo subscription list integration + CLI JSON command and parser tests.
3. Add `/goals` and `/subscriptions` pages/components against `dashboard/design/pages-other.jsx`.
4. Verify with `pnpm typecheck`, `pnpm build`, focused Python tests, and a manual local `/goals` edit against a copy or real `goals.yaml`.

Rollback: remove the new dashboard routes/components and the subscription CLI helper. Existing `goals.yaml`, Folo auth state, radar tables, and analysis pipeline are unchanged.

## Open Questions

- Exact `folocli subscription list` JSON shape should be confirmed during implementation with a real local command or canned output from the installed CLI.
- Whether to preserve YAML comments can be revisited if generated canonical YAML is too annoying for hand editing.
