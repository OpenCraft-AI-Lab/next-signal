## Why

The knowledge base is write-heavy and read-never. Ingest is well-served — route a URL, classify it, enrich frontmatter, land clean markdown in the wiki — but once a doc is filed, nothing ever brings it back. The only paths to an existing doc are remembering it exists and searching for it, or browsing the tree. Material that was worth capturing decays out of memory on exactly the curve Ebbinghaus described, and the system does nothing about it.

This adds the missing read side: a fixed forgetting-curve schedule that resurfaces captured docs at widening intervals, each as a compact summary card rather than a link back into a wall of text.

## What Changes

- New **`knowledge_reviews` table** holding one row per wiki doc: its `captured_at` anchor, current curve stage, and next due date. No generated-text columns.
- **Fixed Ebbinghaus schedule** with stages at 1, 3, 7, 15, 30, 60, and 120 days after `captured_at`. No recall rating, no ease factor — advancing is a single "seen" acknowledgement. Past the final stage a doc retires and stops surfacing.
- **Cold-start fast-forward**: seeding an existing corpus anchors each doc at its real `captured_at` and jumps it to the first stage that has *not* yet elapsed. A doc captured 100 days ago lands at the 120-day stage rather than dumping six overdue reviews on day one. The same rule applies on advance, so a late review never produces an already-overdue card.
- **Card content reuses the doc's frontmatter `summary`** — the closing summary already written at ingest — so the review layer makes no LLM call and holds no generated text. A doc without a `summary` falls back to its first body paragraph.
- New **`paca knowledge review`** subcommand: reconcile the wiki against the table (enroll new docs, unenroll gone ones). No generation step, no flags.
- **`/knowledge` gains a review section** above the ingest form, showing due cards; clicking a card opens the doc's full text in the preview pane, and a "seen" action advances the stage.
- Bilingual docs, English canonical.

Non-goals: no recall rating or SM-2 ease adjustment (the schedule is deliberately fixed); no per-doc recall generation — the card reuses the existing frontmatter summary rather than producing new text; no notification, email, or out-of-dashboard push; no change to the ingest pipeline or its artifacts; no editing of wiki markdown — review state lives entirely in Postgres and never writes frontmatter.

## Capabilities

### New Capabilities

- `knowledge-review`: the scheduling model — curve stages, `captured_at` anchoring, cold-start and advance fast-forward, retirement, wiki↔table reconciliation, frontmatter-summary reuse for the card, and the CLI entrypoint.
- `dashboard-knowledge-review`: the `/knowledge` review section — due-card rendering, the per-day display cap and remainder count, the "seen" action, and the refresh trigger.

### Modified Capabilities

- `core-cli`: the `paca knowledge` subcommand group requirement enumerates its subcommands, so adding `review` changes it.
- `core-database`: adds a `knowledge_reviews` provisioning requirement and extends the raw-psycopg requirement's business-table list.

## Impact

**New files**: `src/paca/workflows/knowledge_review/` (`__init__.py`, `store.py`), `configs/workflows/knowledge_review.yaml`, `dashboard/lib/knowledge/review.ts`, review components, tests.

**Modified**: `scripts/bootstrap_db.py` (DDL), `src/paca/interfaces/cli.py` (subcommand), `dashboard/app/knowledge/page.tsx`, `dashboard/lib/i18n/dictionaries.ts` (EN + ZH), `docs/modules/knowledge.md` + `docs/zh/modules/knowledge.md`.

**Ordering dependency**: this change and `info-radar-recap` both modify `core-database`'s "Business tables use raw psycopg connections" requirement. This change's delta lists **both** `radar_recaps` and `knowledge_reviews`, so it assumes `info-radar-recap` archives first. If the two land in the other order, that delta needs its `radar_recaps` mention dropped before archiving.

**Data**: one new table, keyed by wiki-relative `doc_path` — the same identity the ingest manifest uses. Reconciliation is idempotent and safe to re-run. Scheduling reads only `captured_at` frontmatter; the card additionally reads the doc's `summary`; no wiki file is written.

**Cost**: none — the review layer makes no LLM calls. The card reuses the `summary` already produced by the ingest pipeline.
