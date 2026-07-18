## Why

The dashboard nav already exposes `Goals` and `Subscriptions`, but those routes are still empty placeholders. The operator needs a browser surface for the two user-editable/control-plane inputs that steer `info-radar`: `configs/info_radar/goals.yaml` and the Folo subscription set.

## What Changes

- Add `/goals`: a dashboard page for reading, adding, editing, and deleting entries in `configs/info_radar/goals.yaml`.
- Validate and persist goals through the same schema contract used by `paca.workflows.info_radar_analysis.goals.load_goals`: `name`, `description`, `topics`, `keywords`, optional `weight`, no unknown keys, non-empty goal list.
- Add `/subscriptions`: a read-only dashboard page backed by `folocli subscription list`, with search, category/view filtering, unread counts when available, and a clear loading/error state for cold `npx` starts or auth failures.
- Add small server-side helpers/actions for YAML read/write and Folo subscription listing. These are dashboard-facing boundaries, not new agent tools.
- Keep the existing nav entries; they become real pages instead of placeholder links.
- No schema changes to Postgres and no change to the `info-radar` analysis goal schema.

## Capabilities

### New Capabilities

- `dashboard-goals`: `/goals` route and server actions for managing `configs/info_radar/goals.yaml`.
- `dashboard-folo-subscriptions`: `/subscriptions` route and server-side Folo subscription-list integration.

### Modified Capabilities

None.

## Impact

- **Dashboard code**: new `dashboard/app/goals/page.tsx`, `dashboard/app/subscriptions/page.tsx`, page-specific components, and server helpers under `dashboard/lib/`.
- **Python integrations**: likely extend `paca.integrations.info_radar.folo` with a small `subscription_list()` helper that reuses `default_argv()` and the existing auth/timeout/error style.
- **Config files**: `/goals` writes `configs/info_radar/goals.yaml` atomically and preserves the strict loader contract. `configs/info_radar/goals.example.yaml` remains the sample, not the runtime file.
- **External CLI**: `/subscriptions` invokes the pinned `folocli@0.0.5` argv through `default_argv()` unless `FOLO_CLI_ARGV` overrides it; auth remains `FOLO_TOKEN` or the local Folo session file.
- **Dependencies**: no new npm or Python dependency expected; use existing `yaml` in Python and dashboard package set.
- **Testing**: add focused tests for goals serialization/validation and Folo subscription parser/error handling; dashboard typecheck/build remains the main frontend gate.
