## 1. Folo integration

- [x] 1.1 Add `unread_list()` to `src/paca/integrations/info_radar/folo.py`: run `[*default_argv(), "unread", "list"]`, apply the same envelope checks `subscription_list` uses (launcher missing, timeout, non-zero exit with empty stdout, non-JSON, missing `ok`, `ok: false`), and return the `data.items` rows. Tolerate the list living under `items` / `subscriptions` / `list` the way `_subscription_rows` does, and raise `RuntimeError` on every failure path.
- [x] 1.2 Build a `{feedId: unreadCount}` map from those rows, keyed on the item's `feedId` and skipping items with no feed id.
- [x] 1.3 Have `subscription_list()` call `unread_list()` and pass the map into `_normalize_subscription`; resolve each row's count from the raw `feedId`, falling back to `feeds.id`, and default to `0` when the feed is absent from the map.
- [x] 1.4 Drop the `updatedAt` key and its alias chain from `_normalize_subscription`; drop the now-dead `unread` / `unreadCount` / `unread_count` lookup on the subscription row.
- [x] 1.5 Update the `subscription_list` docstring to say it merges two folocli commands and that an unread-list failure is loud.

## 2. Python tests

- [x] 2.1 Rework the `subprocess.run` fake in `tests/test_folo_subscription_list.py` to dispatch on argv — subscription envelope for `subscription list`, unread envelope for `unread list` — and thread it through every existing test.
- [x] 2.2 Update the three happy-path assertions (`test_subscription_list_happy_path`, `test_subscription_list_accepts_nested_feed_shape`, `test_subscription_list_accepts_data_list`) for the new row shape: no `updatedAt`, `unread` always an int.
- [x] 2.3 Add a test that a feed present in `unread list` gets its `unreadCount`, and a feed absent from it gets `0`.
- [x] 2.4 Add tests that a failing `unread list` (`ok: false`, non-JSON, timeout) raises `RuntimeError` out of `subscription_list()`.
- [x] 2.5 Extend `test_subscription_list_uses_argv_override` to assert the override prefix reaches the unread call too.
- [x] 2.6 Fix the fixture row in `tests/test_cli_info_radar_analyze.py::test_subscriptions_prints_json` (drop `updatedAt`).
- [x] 2.7 `uv run pytest -q` green; `uv run ruff check src` clean.

## 3. Dashboard

- [x] 3.1 `dashboard/lib/subscriptions.ts`: `SubscriptionRow.unread: number`, remove `updatedAt`; in `normalizeRows`, throw on a non-number `unread` the way the other shape violations throw rather than defaulting.
- [x] 3.2 `dashboard/components/subscriptions/subscriptions-table.tsx`: remove the last-updated `<th>` and `<td>`, set the empty-state `colSpan` to 4, and drop the `timeAgo` import plus `locale` from the `useI18n()` destructure if nothing else uses them.
- [x] 3.3 Simplify the unread cell now that `unread` is never null — a `> 0` badge, plain `0` otherwise.
- [x] 3.4 `dashboard/lib/i18n/dictionaries.ts`: remove `subscriptions.lastUpdated` from both the English and Chinese blocks.
- [x] 3.5 `pnpm --dir dashboard lint` and `pnpm --dir dashboard exec tsc --noEmit` clean.

## 4. Docs

- [x] 4.1 `dashboard/README.md` Subscriptions section: state that the page merges `subscription list` with `unread list` and that there is no last-updated column, with the reason.
- [x] 4.2 Mirror 4.1 into `dashboard/README.zh-CN.md`.
- [x] 4.3 `docs/modules/info_filter.md` "External systems" → Folo CLI bullet: add the unread-list use alongside source / full content / subscriptions.
- [x] 4.4 Mirror 4.3 into `docs/zh/modules/info_filter.md`.
- [x] 4.5 Walk the code-review doc-sync map for the remaining rows (`docs/operations.md` 常用命令, `CLAUDE.md` CLI 子命令 list) and confirm the `paca info-radar subscriptions --json` description still matches; update if not.

## 5. Verify

- [x] 5.1 `docker compose build && docker compose up -d --force-recreate`, then `docker compose exec dashboard /app/.venv/bin/python` against live Folo: 22 rows, no `updatedAt` key, every `unread` an int, sum = 712 = `folocli unread count`, 5 feeds at zero.
- [x] 5.2 `/subscriptions` on the fresh image renders 4 columns — Title / Feed URL / Category / Unread, no last-updated — subtitle `22 feeds · 712 unread`, badges matching the CLI, no console errors. Verified in both locales.
- [x] 5.3 `uv run openspec validate --all`.

## 6. Review fixes

- [x] 6.1 `_envelope_rows` raises when the envelope is a dict with no recognized rows key, instead of silently returning `[]` — reusing it for `unread list` had created a new silent-zero path that contradicted the change's own loud-failure decision. Error message carries keys only, never values.
- [x] 6.2 Tests for both call sites of 6.1 (`unread list` shape drift, `subscription list` shape drift); a bare `[]` and a known-key-empty list still parse as legitimately empty.
- [x] 6.3 `subscription_list` docstring states `timeout` is per folocli call, so the worst case is twice it (dashboard budgets 90s in `dashboard/lib/subscriptions.ts`).
- [x] 6.4 Module docstring lists the actual public surface — it claimed "two things only" while exporting five functions.
