## 1. Database

- [x] 1.1 Add `CREATE_KNOWLEDGE_REVIEWS` DDL to `scripts/bootstrap_db.py` with the documented columns, `UNIQUE (doc_path)`, and the partial `knowledge_reviews_due_idx`; wire it into `main()`
- [x] 1.2 Verify re-running bootstrap against a populated table preserves stages and cached recall points

## 2. Scheduling core

- [x] 2.1 Create `src/paca/workflows/knowledge_review/store.py`: enroll/unenroll, due selection (`next_due_at <= today` in radar tz, ordered `next_due_at` then `captured_at`), stage advance, and recall-point cache read/write
- [x] 2.2 Implement the curve in `src/paca/workflows/knowledge_review/__init__.py`: `STAGES = [1, 3, 7, 15, 30, 60, 120]`, `next_due_at = captured_at + STAGES[stage]`, and the shared fast-forward helper returning the first not-yet-elapsed stage
- [x] 2.3 Wire fast-forward into both paths: seeding uses it directly, advance uses `max(stage + 1, fast_forward)`; assert neither can emit a `next_due_at` in the past
- [x] 2.4 Implement retirement — advancing past the final stage sets `next_due_at = NULL`, and due selection excludes NULL
- [x] 2.5 Resolve `captured_at` from frontmatter with precedence `captured_at` → `updated_at` → `created_at` → mtime, matching `dashboard/lib/wiki.ts`

## 3. Reconciliation

- [x] 3.1 Implement `sync`: walk the wiki, insert seeded rows for unknown `doc_path`s, delete rows whose file is gone; make it idempotent
- [x] 3.2 Guard the destructive path — raise `RuntimeError` and delete nothing when the wiki root is missing, unreadable, or contains no markdown docs
- [x] 3.3 Reuse the ingest manifest's digest function for `source_digest` rather than introducing a second hashing scheme

## 4. Card content

> Post-review pivot: the card reuses the doc's existing frontmatter `summary`
> instead of a generated recall — the `knowledge_recall` agent/prompt and all
> generation/cache columns were removed. See design K6.

- [x] 4.1 Card body reuses the doc's frontmatter `summary` (read in the dashboard data layer), with a first-body-paragraph fallback; no recall-generation agent, no LLM call, no generated-text columns
- [x] 4.2 Write `configs/workflows/knowledge_review.yaml` — `expose.agent_os: false`, `expose.tool.enabled: false`, `extra.run_now`

## 5. CLI

- [x] 5.1 Add `paca knowledge review` to `src/paca/interfaces/cli.py` (reconcile-only, no flags), printing enrolled / unenrolled / due counts

## 6. Dashboard — data layer

- [x] 6.1 Create `dashboard/lib/knowledge/review.ts`: due-doc query via direct Postgres, capped at 5 with a total due count for the remainder line
- [x] 6.2 Add the POST server action that advances a stage and revalidates `/knowledge`
- [x] 6.3 Add the refresh server action spawning `paca knowledge review` through `spawnPacaDetached`

## 7. Dashboard — UI

- [x] 7.1 Build the review card: title, capture date, review position, the doc's summary
- [x] 7.2 Build the section above the ingest form: up to 5 cards, remainder count, collapsed single line when nothing is due
- [x] 7.3 Card shows the doc's frontmatter summary; a doc without one falls back to its first body paragraph (no pending state)
- [x] 7.4 Wire the seen control as POST — verify no stage advances on render or prefetch
- [x] 7.5 Add EN + ZH strings to `dashboard/lib/i18n/dictionaries.ts`, English canonical; leave doc titles and summaries untranslated
- [x] 7.6 Reuse existing design-system primitives and tokens; if any new token or primitive is introduced, add it to `/design` in this change
- [x] 7.7 Clicking a review card opens the doc's full text in the preview pane and scrolls to it (`#doc-preview`), without advancing the stage

## 8. Tests

- [x] 8.1 Curve arithmetic: seeding a doc captured 100 days ago lands at the 120-day stage; a doc captured today is due tomorrow, not today
- [x] 8.2 Fast-forward on advance: a late review never produces a `next_due_at` in the past and does not cascade the backlog
- [x] 8.3 Retirement: advancing past the final stage nulls `next_due_at` and drops the doc from due selection
- [x] 8.4 Reconciliation: enrolls only unknown docs, is idempotent, unenrolls deleted docs, and raises without deleting when the wiki is empty or missing
- [x] 8.5 Store (real-Postgres integration): enroll/existing round-trip, ON CONFLICT idempotency, delete unenrolls
- [x] 8.6 Due predicate (store `count_due`, real-Postgres): counts only `next_due_at <= today` in the radar tz, excludes future and retired (NULL) rows; card ordering lives in the dashboard SQL and is verified in-browser

## 9. Docs

- [x] 9.1 Document the review layer in `docs/modules/knowledge.md` — table, curve, fast-forward, retirement, recall cache, CLI — and update its 规范与状态 section
- [x] 9.2 Mirror into `docs/zh/modules/knowledge.md`, structure one-to-one with the English page
- [x] 9.3 Update `docs/modules/dashboard.md` + its zh mirror for the new `/knowledge` section

## 10. Verification

- [x] 10.1 `uv run pytest -q` green; `uv run ruff check src` clean
- [x] 10.2 End-to-end in Docker per project policy: `docker compose build && docker compose up`, then `docker compose exec dashboard paca knowledge review` against a real wiki and confirm enrollment counts are proportional to curve boundaries rather than corpus size
- [x] 10.3 Verify in the browser that the section renders, a card can be marked seen, the card leaves the due list, and both locales read correctly

## 11. Sequencing

- [x] 11.1 Before archiving, confirm whether `info-radar-recap` has archived — this change's `core-database` delta lists both `radar_recaps` and `knowledge_reviews`, so if it lands first, drop the `radar_recaps` mention from its MODIFIED requirement
  <!-- info-radar-recap archived first (openspec/specs/core-database already lists radar_recaps); the delta correctly keeps radar_recaps and adds knowledge_reviews. No change needed. -->


