## Why

The `/subscriptions` table shows `0` unread on every row and "22 feeds · 0 unread"
in the subtitle, while the account actually has 710 unread entries. It also shows
"2mo ago" in a "Last updated" column for all 22 feeds. Both are the same root
cause: `folocli subscription list` returns neither an unread count nor an update
timestamp, so `_normalize_subscription` produces `unread: None` (rendered as a
literal `0`) and falls back to `createdAt` — the date the operator *subscribed* —
for `updatedAt`.

Verified against folocli@0.0.5 with the live account: the union of keys across all
22 rows (top level plus the nested `feeds` object) is `category, createdAt,
feedId, feeds, hideFromTimeline, isPrivate, title, userId, view` and
`description, errorAt, errorMessage, id, image, owner, ownerUserId, siteUrl,
title, type, url`. There is no `unread*` and no `updatedAt` anywhere.

## What Changes

- `subscription_list()` additionally invokes `folocli unread list` and merges its
  per-feed `unreadCount` into the subscription rows, matched on `feedId`. That
  command returns `data.total` plus `data.items[]` of
  `{sourceType, sourceId, feedId, title, category, view, unreadCount, isPrivate}`,
  listing only feeds that have unread entries — so it is authoritative, and a
  subscription absent from it genuinely has `0` unread.
- `unread` becomes a plain integer instead of `int | None`. The dashboard no
  longer conflates "no data" with "zero unread", because there is no longer a
  no-data case.
- A failed `unread list` raises `RuntimeError` out of `subscription_list()`
  rather than degrading to null counts. Degrading would re-render the exact
  phantom `0` this change removes, and both commands sit behind the same folocli
  auth path anyway.
- The "Last updated" column is removed from the table, along with the `updatedAt`
  field across the Python normalizer, the dashboard row type, and both i18n
  dictionaries. Folo exposes no per-feed update timestamp short of one
  `folo feed get <feedId>` call per feed, and rendering the subscription creation
  date under a "Last updated" header is worse than showing nothing.
- **BREAKING**: `paca info-radar subscriptions --json` rows drop the `updatedAt`
  key and `unread` is never `null`. The only consumer is the dashboard, which is
  updated in the same change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dashboard-folo-subscriptions`: the subscriptions-page requirement changes from
  rendering "unread count when available … and last-updated text when available"
  to rendering an accurate per-feed unread count and no last-updated column; the
  integration requirement gains the `unread list` merge and its loud-failure
  behavior.

## Impact

- `src/paca/integrations/info_radar/folo.py` — new `unread_list()` bridge;
  `subscription_list()` merges it and drops `updatedAt`.
- `dashboard/lib/subscriptions.ts` — `SubscriptionRow.unread: number`, drop
  `updatedAt`.
- `dashboard/components/subscriptions/subscriptions-table.tsx` — drop the column,
  its header, and the now-unused `timeAgo`/`locale` usage; `colSpan` 5 → 4.
- `dashboard/lib/i18n/dictionaries.ts` — drop `subscriptions.lastUpdated` from the
  English and Chinese dictionaries.
- `tests/test_folo_subscription_list.py` — the existing tests monkeypatch
  `subprocess.run` with a single lambda; they must dispatch on argv now that
  `subscription_list()` shells out twice.
- `tests/test_cli_info_radar_analyze.py::test_subscriptions_prints_json` — fixture
  row shape.
- `dashboard/README.md` + `dashboard/README.zh-CN.md` — the Subscriptions section
  describes the normalization; both must state the two-command merge.
- One extra folocli subprocess per page load. `subscription list` and
  `unread list` are independent, so the added latency is bounded by the slower of
  the two rather than their sum.
