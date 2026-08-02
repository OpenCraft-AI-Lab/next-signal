## Context

`subscription_list()` in `src/paca/integrations/info_radar/folo.py` is the single
server-side boundary behind both `paca info-radar subscriptions --json` and the
dashboard's `/subscriptions` page. It parses one folocli command, and its
`_normalize_subscription` helper reaches through a chain of field aliases to
absorb output-shape drift across folocli versions.

That alias chain is what hides the bug. `unread` tries `unread`, `unreadCount`,
`unread_count` and finds none, yielding `None`; `updatedAt` tries four aliases,
finds none, and falls through to `createdAt`. Neither miss is observable — the
row still validates, the dashboard still renders. Confirmed against folocli@0.0.5
on the live account: 22 rows, no `unread*` key and no `updatedAt` key anywhere in
the union of top-level and nested `feeds` fields.

The counts live behind a separate command. `folocli unread list` returns
`{"ok": true, "data": {"total": 710, "items": [...]}}` where each item is
`{sourceType, sourceId, feedId, title, category, view, unreadCount, isPrivate}`.
It listed 17 items summing to exactly the 710 that `folocli unread count`
reports, against 22 subscriptions — it enumerates every feed with unread entries
and omits the rest.

## Goals / Non-Goals

**Goals:**

- `/subscriptions` shows real per-feed unread counts and a real aggregate.
- No cell on the page can render a number that stands in for missing data.
- The removed "Last updated" column leaves no vestigial field in the JSON
  contract, the row types, or the dictionaries.

**Non-Goals:**

- Recovering a genuine per-feed last-update time. That needs
  `folo feed get <feedId>` → `data.entries[0].publishedAt`, one subprocess per
  feed — 22 `npx` invocations behind an already-slow boundary. Out of scope; the
  column goes away instead.
- Caching or persisting unread counts. The page stays a live read-through.
- Anything mutating: subscriptions remain read-only, and this change never marks
  entries read.

## Decisions

**Merge inside `subscription_list()`, not at a higher layer.** The alternative is
a second tool/CLI surface that the dashboard calls separately and joins in
TypeScript. Rejected: it would put a join in the presentation layer, and it would
let the two calls disagree about which feeds exist. Keeping the merge in the
integration means `paca info-radar subscriptions --json` and the dashboard cannot
drift, and the CLI stays the one contract.

**Match on the raw `feedId`.** Subscription rows carry `feedId` at the top level
and `feeds.id` nested, and both equal the `feedId` on unread items. The emitted
row `id` already resolves to `feedId` today via `_first_str(row, "id",
"sourceId", "source_id", "feedId")`, but that is incidental — a future folocli
that adds a real subscription `id` would silently break the join. Match on the
raw `feedId`, falling back to `feeds.id`, and keep the emitted `id` as-is.

**Missing from the unread list means `0`, not null.** This is the one place the
change accepts a default, and it is a default the data licenses: `unread list`
enumerates the feeds that have unread entries, so absence is information, not a
gap. That is what lets `unread` become a plain `int` and removes the
null-vs-zero conflation from the UI entirely.

**A failed `unread list` raises.** Rejected alternative: catch it and return rows
with `unread: None`, keeping the inventory usable. That reproduces the exact
failure this change exists to remove — a page full of `0` that looks like data.
Both commands sit behind the same folocli auth and argv path, so a failure of one
is near-certainly a failure of both; there is little partial-usefulness to
preserve. Raising matches how `subscription_list` already treats a bad
subscription envelope.

**One extra `_normalize_unread`-style parser, same defensive posture as
`_subscription_rows`.** `unread list` nests under `data.items` today, but the
module's existing convention is to tolerate the list living under a few plausible
keys. Follow it rather than inventing a stricter style in one function.

**Sequential, not concurrent, subprocess calls.** Two `npx` calls in series on a
warm npm cache are sub-second each; the cold-start cost is paid once by whichever
runs first, and the second hits the cache. Concurrency here would add
`asyncio`/threading to a module that is deliberately synchronous.

## Risks / Trade-offs

- **A future folocli moves unread counts into `subscription list`** → The merge
  becomes redundant but not wrong; `_first_int` on the subscription row can then
  take priority and the second call be dropped. Cheap to unwind.
- **`unread list` includes list-type subscriptions (`sourceType: "list"`)** whose
  `sourceId` is a list id rather than a feed id → Matching on `feedId` naturally
  ignores them. The account currently has none, so this is untested against real
  data; a list subscription would simply show `0` rather than a wrong count.
- **Page load gets slower by one folocli round-trip** → Accepted. The boundary
  already carries a 90s timeout in `dashboard/lib/subscriptions.ts` sized for
  cold `npx --yes` starts, which dominates either call.
- **Removing `updatedAt` is a breaking change to the JSON contract** → The only
  consumer is the dashboard, updated in the same change. `docs/operations.md`
  documents the command but not its field list.
- **Tests currently monkeypatch `subprocess.run` with an argv-blind lambda** →
  Every existing test in `tests/test_folo_subscription_list.py` would feed the
  subscription envelope to both calls. The fake must dispatch on argv; this is
  the largest single piece of the implementation.
