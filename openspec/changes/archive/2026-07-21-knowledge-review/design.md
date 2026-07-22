## Context

The wiki is a directory of markdown files, not a database. There is no per-doc row anywhere — the only existing per-doc state is `knowledge_ingest_manifest.json`, a `{relative_path: content_digest}` map used to decide what needs re-indexing. Docs carry a `captured_at` frontmatter field, and `dashboard/lib/wiki.ts` already resolves an effective date with the precedence `captured_at` → `updated_at` → `created_at` → file mtime.

So the scheduling layer needs storage of its own, an identity for docs that survives across runs, and a reconciliation step — the wiki can change without anything telling the scheduler.

Two prior decisions from the requester frame everything below: the curve is **fixed** (stages at 1/3/7/15/30/60/120 days, no recall rating, no ease factor), and delivery is a **section on the existing `/knowledge` page**, not a new route or an external push.

## Goals / Non-Goals

**Goals:**

- Resurface captured docs on the forgetting curve without requiring the reader to grade themselves.
- Make a review a few seconds of reading, not a re-read of the source.
- Seed an existing corpus without producing a backlog flood.
- Keep all review state out of the wiki files — the markdown is the artifact, not the scheduler's scratchpad.

**Non-Goals:**

- Adaptive scheduling (SM-2, ease factors, recall grading). Explicitly rejected in favour of the fixed curve.
- Any delivery surface outside the dashboard.
- Changes to the ingest pipeline. Reconciliation reads the wiki; it does not hook into ingest.

## Decisions

### K1: Review state is a Postgres business table keyed by wiki-relative path

`knowledge_reviews` with `doc_path TEXT NOT NULL UNIQUE`, using the same relative-path identity as the ingest manifest and the dashboard's `WikiDocSummary.id`.

*Alternatives considered:*

- **Frontmatter in the markdown.** Rejected outright: it would rewrite every doc on every review, churn the ingest digests, and make the scheduler a mutator of the artifacts it is supposed to preserve.
- **JSON under `~/.next-signal/`.** Rejected: due-date selection is a query (`WHERE next_due_at <= today ORDER BY next_due_at`), and the repo's convention puts hand-editable runtime state in `~/.next-signal/` while machine-managed relational state goes in Postgres. Review scheduling is squarely the latter.

### K2: Stages are absolute offsets from `captured_at`, never relative to the last review

`STAGES = [1, 3, 7, 15, 30, 60, 120]`, and `next_due_at = captured_at + STAGES[stage]`.

This is what makes the curve *fixed*: the schedule is a property of when the material was captured, not of when the reader happened to click. Anchoring on `last_reviewed_at` instead would let the schedule drift with reader behaviour, which is the first step toward the adaptive model that was explicitly not chosen.

`captured_at` is resolved from frontmatter with the same precedence the dashboard already uses (`captured_at` → `updated_at` → `created_at` → mtime), so the scheduler and the tree agree on a doc's date.

### K3: Fast-forward is applied on both seed and advance

Seeding sets `stage` to the count of stages already elapsed, i.e. the first stage whose offset has *not* yet passed. A doc captured 100 days ago seeds to stage 6 (next due at day 120), not stage 0 with six overdue reviews behind it.

The same rule applies on advance: marking a card seen sets stage to `max(stage + 1, first-not-yet-elapsed-stage)`. Without this, a reader who reviews a stage-3 card 10 days late would immediately be handed a stage-4 card that is also already overdue, and then a stage-5, cascading through the backlog in one sitting. Fast-forward means a review always produces a card due in the future.

*Alternative considered:* seed everything at stage 0 from the moment the feature is enabled. Rejected — it restarts the curve for material captured months ago, which is both wrong about the memory model and floods the panel on first run.

### K4: Retirement past the final stage

Advancing past stage 120 sets `next_due_at = NULL` and the doc stops surfacing. The premise of spaced repetition is that after enough widening intervals the material is retained; continuing to cycle it forever would turn the panel into noise and dilute genuinely due material.

`next_due_at IS NULL` is a single nullable column, so a future re-enroll or evergreen-rotation mode is additive rather than a migration. See Risks — this decision has a sharp consequence for old corpora.

### K5: Reconciliation is an explicit CLI step, not a side effect of page render

`paca knowledge review` walks the wiki, inserts rows for docs it has never seen (seeded per K3), and removes rows whose file no longer exists. The dashboard reads the table and never writes to it during render.

*Alternative considered:* reconcile inside the `/knowledge` server component, which already walks the whole tree via `listWikiTree()`. Rejected — a GET render should not carry write side effects, and Next.js may render a server component more than once. Making the write explicit also keeps enrollment a deliberate spawned job rather than a side effect of someone opening a page.

*Alternative considered:* insert a review row from the ingest persist stage, so new docs enroll automatically. Rejected for this change — it couples ingest to review for a case `paca knowledge review` already covers, and the ingest pipeline is the most invariant-dense code in the repo. Worth revisiting only if manual sync proves annoying in practice.

### K6: The card reuses the doc's frontmatter `summary`, not a separately generated recall

The card body is the doc's own frontmatter `summary` — the closing summary the ingest pipeline already writes to frontmatter and the `## 总结` section. The review layer generates nothing and makes **no LLM call**.

*Superseded alternative:* an earlier draft added a `knowledge_recall` agent producing three per-doc "recall points", cached on the row with a `source_digest`. In practice, on a local model, those points read as the summary re-chopped into three sentences — near-duplicate content at the cost of a whole generation + cache-invalidation + pending-state layer. The frontmatter summary is already per-doc, already regenerated on every re-ingest (so it stays fresh with no digest bookkeeping), and is literally the doc's own conclusion — showing it and then opening the full text on click is more coherent than surfacing separately-generated text. A doc with no `summary` (hand-created, never ingested) falls back to its first body paragraph. If true *active recall* (hidden-answer cues) is wanted later, that is a distinct feature, not this agent.

### K7: Due docs always have card content

Because the card reuses the frontmatter `summary` (with a body-paragraph fallback), a due doc always has something to show the moment it is enrolled — there is no generation step to wait on, so no pending state and no risk of the due count disagreeing with what renders.

### K8: The panel caps at 5 cards and reports the remainder

Twenty cards due on one day is a wall nobody reads. The section shows at most 5, ordered by `next_due_at` ascending so the longest-overdue surface first, and states how many more are due. Same principle as K3: never silently truncate — say what was left out.

### K9: "Seen" is a POST server action

Advancing a stage is a plain DB write with no LLM involved, so it completes in the request and does not need the spawn-and-poll treatment. It MUST be a POST server action rather than a GET link — the existing re-index control on this page already carries that constraint, and a GET that mutates would let a prefetch advance the curve.

Refresh (`paca knowledge review` reconciliation) *does* spawn detached via `spawnPacaDetached`, keeping this path uniform with the other spawn-and-report controls on the page.

## Risks / Trade-offs

- **An old corpus surfaces once, then goes quiet.** This is the sharp edge of K2 + K4: a doc captured 200 days ago is already past the final stage, so it retires after a single review — or never enrolls as due at all. For a wiki whose contents are mostly older than 120 days, the feature will produce a short burst and then very little. This is the mathematically correct reading of a capture-anchored fixed curve, and it follows directly from the chosen model rather than being a defect in it — but it may not match the expectation of "keep resurfacing my knowledge base". Flagged as an open question below; the fix, if wanted, is additive.
- **A moved or recategorized doc looks like delete + add**, resetting its curve to a fresh seed. Path is the identity (K1), and re-running classification can move files. Accepted: the ingest manifest already has exactly this property, so behaviour is at least consistent across the two systems. Content-digest identity would fix it and is a larger change.
- **Reconciliation deletes rows for missing files**, so a temporarily unavailable wiki (unmounted volume, misconfigured `PACA_WIKI_DIR`) could wipe review state. Mitigation: reconciliation SHALL abort without deleting anything when the wiki root is missing or resolves to an empty tree, rather than interpreting "no files" as "all files deleted".
- **`captured_at` can be absent or malformed**, falling through to file mtime — which a `git clone` or file copy resets to now, re-enrolling old docs at stage 0. Accepted; the same precedence already governs what the tree displays, so at least the panel and the tree agree.
- **Recall quality on a local model is unproven.** Three points from a long doc is a summarization task the profile should handle, and `local_structured` already carries `fallback_profile: deepseek_structured`. The prompt is a file, not code.

## Migration Plan

Additive. `scripts/bootstrap_db.py` gains one `CREATE TABLE IF NOT EXISTS`, safe to re-run — the container bootstrap already runs it on every start.

First enablement is `paca knowledge review`, which enrolls the existing corpus per K3. Because seeding fast-forwards, this produces a due list proportional to the docs genuinely at a curve boundary, not to corpus size.

Rollback is dropping the table and reverting the code. No wiki file is modified at any point, so there is nothing to undo on disk.

## Open Questions

- **Should retired docs re-enroll?** K4 retires at 120 days, which combined with capture anchoring means an older corpus quiets down quickly (see Risks). If the intent is ongoing rotation over the whole knowledge base, that is a different feature — an evergreen sampler — rather than a forgetting curve, and it should be decided deliberately rather than by widening the stage list.
- **Should the review section be collapsible or dismissible for a day?** Putting it above the ingest form means it is the first thing on `/knowledge` every visit. Deferred until there is a sense of how often it is non-empty.
