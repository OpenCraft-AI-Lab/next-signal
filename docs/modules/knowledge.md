# Module: knowledge (knowledge management)

> **English** · [中文](../zh/modules/knowledge.md)

## What it solves

Turn URLs and files into durable markdown artifacts and searchable long-term
knowledge. Clean markdown goes into the wiki tree, the raw original is archived,
and GBrain provides indexing and hybrid search.

## Where the code lives

`src/paca/tools/knowledge/` — agent-facing knowledge tools.
`src/paca/integrations/knowledge/` — OpenCLI (WeChat) / Bilibili / GitHub adapters.
`src/paca/workflows/knowledge_ingest.py` — the centralized workflow factory.
`src/paca/workflows/stages/knowledge_ingest/` — workflow-private pipeline stages.
`src/paca/workflows/knowledge_review/` — the spaced-repetition review scheduler
(curve + reconciliation in `__init__.py`, Postgres I/O in `store.py`).

## Agents

| Agent | Model profile | Used for |
|---|---|---|
| `knowledge_artifact_editor` | local | Ingest's clean step: body cleanup / whisper correction (DB-free transformation agent) |
| `knowledge_github_cleaner` | local | GitHub-repo-specific clean step: aggressively trims only the `## README` section (badges, install commands, sponsor blocks); structured signal sections are preserved verbatim |
| `knowledge_frontmatter` | local | Ingest's enrich step: produces title/summary/tags/freshness (`FrontmatterDraft` schema, DB-free). Locale-aware: `.zh.md` / `.en.md` prompt variants generate title/summary in the ingest locale |
| `knowledge_github_summary` | local | GitHub-repo-specific enrich step: organizes the summary around does/value/maturity/ecosystem, reusing the `FrontmatterDraft` schema. Locale-aware (`.zh.md` / `.en.md`) |
| `knowledge_tag_translator` | local_structured | Best-effort: translates an English tag key to a localized display label (`TagLabel` schema), cached in `knowledge_tag_labels` per `(tag, locale)` |
| `knowledge_classifier` | local | Picks the wiki category directory from the taxonomy at ingest time (DB-free transformation agent) |

## Tools

Knowledge-domain tools:

- `knowledge_ingest_workflow` — the single-article ingest path (fetch → clean →
  enrich → classify → persist).

KB **retrieval** is cross-cutting infrastructure and does not belong to this
module: `search_knowledge` lives in `paca/tools/knowledge/search.py`;
`gbrain_search` / `gbrain_get` / `gbrain_query` / `gbrain_ingest` live in
`paca/tools/gbrain.py`; and the GBrain bridge is `paca/integrations/gbrain.py`.
Agents in any module can reference these tools by name.

## External systems

- **OpenCLI** — the WeChat Official Account entrypoint. A local
  `node opencli weixin download` subprocess downloads the article plus images
  into the raw store, then rewrites the markdown image links to local relative
  paths by slot index. `OPENCLI_BIN` is required and read at call time.
- **MarkItDown** — converts YouTube / PDF / HTML / Office / text-like files to
  markdown (cross-cutting adapter: `paca/integrations/markitdown.py`).
- **Bilibili** — prefers public subtitles; when there are none, downloads
  temporary audio, transcribes locally, then deletes the temporary media. It also
  exports a lightweight `bilibili_fetch_captions` (subtitles + title +
  description only, no audio download) — a helper for cross-domain sampling
  scenarios that next-signal has no caller for today. It is kept for future use
  and is **not** part of the ingest path.
- **GitHub** — for bookmarking a single repo. Accepts only
  `github.com/owner/repo` root URLs (subpaths fail loud). It calls the REST API
  for repo metadata, the top-level file tree, the 3 most recent releases,
  top-level manifests, the 10 most recent commits, contributors plus language
  distribution, and the README, then assembles a structured markdown bundle. The
  dedicated `knowledge_github_cleaner` trims the README section aggressively, and
  `knowledge_github_summary` writes the summary across the four does / value /
  maturity / ecosystem angles. `GITHUB_TOKEN` is optional — without it, requests
  go out anonymously (60/h rate limit, fine for occasional personal bookmarking);
  when set, it is read at call time and added as a Bearer header.
- **GBrain** — the long-term knowledge-base peer service. Ingest goes through the
  cross-cutting GBrain bridge (`paca/integrations/gbrain.py`); it is not owned by
  this module.
- **Obsidian Git plugin** — wiki repo ↔ GitHub sync runs as a plugin inside the
  vault, not in the paca process. See "Wiki ↔ GitHub sync" below.

## Where data lives

- Clean wiki: `~/Projects/digitalpaca-wiki/`
- Raw archive: `~/Projects/digitalpaca-wiki-raw/`
- Re-ingest manifest: `~/.next-signal/knowledge_ingest_manifest.json`
- Review schedule: `knowledge_reviews` table (Postgres)
- Index: GBrain's own local storage

## How to use it

```bash
uv run paca knowledge ingest <url|staged-file>
uv run paca knowledge ingest <url> --category knowledge/ai-ml   # pick the destination folder (skips auto-classification)
uv run paca knowledge ingest <url> --progress                   # one JSON event per pipeline step, plus a final result JSON line
uv run paca knowledge gbrain-search "query"
uv run paca run-workflow knowledge_ingest            # re-ingest changed files + refresh every Related block
uv run paca knowledge review                         # reconcile the wiki against knowledge_reviews (enroll new / unenroll gone)
```

`--category` must be a path that exists in `configs/knowledge_taxonomy.yaml`;
invalid values fail loud before the fetch. `--progress` feeds the dashboard's
ingest progress panel (see below). Local file input is accepted only for files
staged under `PACA_AGENT_TMP_DIR`; `/radar`'s Folo ingest respects that boundary
too, writing the full-text HTML into that directory first and then handing the
file path to the generic knowledge pipeline.

## Knowledge review (spaced repetition)

Ingest is the write side; review is the read side. Every wiki doc gets one row in
`knowledge_reviews`, scheduled back onto the reader's screen along a fixed
Ebbinghaus curve so captured material is refreshed before it decays.

- **Curve** — stages at **1, 3, 7, 15, 30, 60, 120 days** after the doc's
  `captured_at`; `next_due_at = captured_at + STAGES[stage]`, always anchored to
  the capture date, never to when the reader clicked. No recall rating, no ease
  factor — "seen" is a single acknowledgement.
- **Fast-forward** — seeding an existing corpus anchors each doc at its real
  `captured_at` and jumps it to the first stage not yet elapsed, so a doc captured
  100 days ago lands at the 120-day stage rather than dumping six overdue reviews.
  The same `max(stage + 1, first-not-elapsed)` rule applies on advance, so a late
  review never produces an already-overdue card.
- **Retirement** — advancing past the final stage sets `next_due_at = NULL` and
  the doc stops surfacing. A corpus mostly older than 120 days therefore surfaces
  once and then quiets down; re-enrolling retired docs would be a separate
  evergreen-rotation feature, not a wider stage list.
- **Card content** — the card reuses the doc's own frontmatter `summary` (the
  closing summary written to frontmatter and the canonical `## Summary` section at
  ingest, localized at render), so
  the review layer makes **no LLM call** and stores no generated text. A
  hand-created doc with no `summary` falls back to its first body paragraph.
- **Reconciliation** — `paca knowledge review` walks the wiki, enrolls
  unknown docs (seeded per the curve), and unenrolls docs whose files are gone.
  It refuses to act on a missing or empty wiki rather than reading "no files" as
  "everything deleted". `captured_at` is resolved from frontmatter with the same
  `captured_at` → `updated_at` → `created_at` → mtime precedence the dashboard
  wiki view uses.

Delivery is a section at the top of `/knowledge` (above the ingest form), capped
at five cards longest-overdue first with a remainder count. Clicking a card opens
the doc's full text in the page's preview pane and scrolls to it (`#doc-preview`),
so a review is a re-read of the source, not just a reminder — opening never
advances the stage. "Seen" is a POST server action that advances the stage
in-request (a GET could let a prefetch advance the curve); the refresh control
spawns the `--sync` job detached, since reconciliation plus recall generation is
LLM work.

## Invariants

- Review state lives entirely in `knowledge_reviews`; the review layer never
  writes a wiki markdown file, including frontmatter. `doc_path` (the
  wiki-relative path) is the identity, kept consistent with the filesystem by
  reconciliation rather than a foreign key.
- A GBrain ingest failure must never lose the artifact: the clean wiki and raw
  files stay on disk and the workflow fails loud. The run is not marked
  successful; once GBrain is fixed, direct ingest or the weekly sync backfills the
  index.
- The re-ingest manifest advances only after a successful index — otherwise later
  runs skip the file and KB search goes stale.
- Direct ingest and re-ingest must derive the same GBrain-safe slug from the
  wiki-relative path. Non-ASCII paths get a stable hash suffix so GBrain pages
  cannot collide.
- Wiki filenames derive from the **source title** (`source_title`, the pre-LLM
  original), NOT the localized `title` — so the same source keeps one stable slug
  and GBrain identity across locales. Frontmatter records a `digest` (a source
  hash) as the same-origin identity: a same-origin re-ingest overwrites in place
  (idempotent update), while an identical title from a different source gets a new
  file with a `-<digest[:8]>` suffix. Never silently overwrite someone else's
  article — including collisions across the two directory layouts.
- **Localization is per-item; storage stays canonical.** The stored `.md` is
  locale-independent: English frontmatter KEYS, English enum tokens (`status: clean`,
  `freshness`, `source_type`, `converter`), English tag KEYS, and canonical
  `## Summary` / `## Related` headings. The locale-bound LLM prose — `title` and
  `summary` — is generated in the ingest `--locale` and recorded in a `locale`
  frontmatter field; the pre-LLM title is kept as `source_title`. Provenance
  (`source_url` / `published` / `author`) is structured frontmatter, seeded for radar
  ingests from a staged `<stem>.meta.json` sidecar (never an English label block in
  the body). The dashboard localizes every per-item label — frontmatter key/value
  labels, the two headings, and tag DISPLAY aliases (from `knowledge_tag_labels`,
  generated once per `(tag, locale)` via `knowledge_tag_translator`, best-effort) —
  by the artifact's own `locale`, so each item renders whole in its language
  regardless of the UI cookie. A UI language switch never retranslates existing
  items; re-ingesting under the other locale regenerates the prose. The two
  `knowledge_frontmatter.{zh,en}.md` (and `knowledge_github_summary.{zh,en}.md`)
  prompt variants must stay structurally in sync.
- A `knowledge_artifact_editor` failure must not produce deterministic fallback
  content.
- WeChat artifacts use a per-article directory layout
  (`<category>/<slug>/<slug>.md` plus a sibling `images/`);
  `gbrain_slug_for_path` collapses that duplicated directory level so the GBrain
  slug matches what the flat layout produces.
- The `<!-- gbrain:related ... -->` marker block at the end of every wiki article
  is GBrain-driven derived data: written at ingest time from one hybrid query on
  title+summary, and fully refreshed by the weekly sync. **Do not hand-edit
  inside the marker block**; the rest of the body is yours to change freely. The
  Related list uses explicit `[[wiki/path/Note]]` wikilinks, which Obsidian
  renders automatically and wires into the Backlinks panel, and GBrain `extract`
  syncs back into typed edges.

## Wiki ↔ GitHub sync

Syncing `digitalpaca-wiki/` to GitHub happens **outside the paca process**,
handled by the [Obsidian Git plugin](https://github.com/Vinzent03/obsidian-git)
inside the vault and fully decoupled from paca. paca only guarantees that the
moment the wiki hits disk, it is in sync with GBrain; pushing to GitHub on a
schedule is the plugin's job.

### Credentials

On macOS desktop, Obsidian Git shells out to the system `git` and inherits the
global git config. One-time setup:

```bash
gh auth setup-git   # route git HTTPS ops through the PAT the gh CLI already stored in the keychain
```

You do not need to paste a token into the plugin UI. If the plugin cannot find
the helper path, set "Custom git binary path" in its settings to the output of
`which git` (usually `/opt/homebrew/bin/git`).

Mobile Obsidian is a different stack (isomorphic-git) and requires pasting a PAT
into the plugin settings — not needed for a single desktop setup.

### Recommended plugin configuration

| Setting | Value | Effect |
|---|---|---|
| Vault backup interval (minutes) | `30` | Auto commit + push interval |
| Auto pull interval (minutes) | `10` | Auto pull, so conflicts don't pile up |
| Pull updates on startup | ✓ | Sync as soon as Obsidian opens |
| Pull before push | ✓ | Pull first to reduce rejects |
| Commit message | `vault: {{date}} ({{numFiles}} files)` | Template |
| Date placeholder format | `YYYY-MM-DD HH:mm` | Feeds `{{date}}` |

### End-to-end picture

```
paca knowledge ingest
  → fetch + clean + classify + persist
  → writes wiki/<category>/<slug>/<slug>.md + images/
  → gbrain put + embed   ← fails loud here, but the artifact stays on disk
  → success → paca is done, the wiki files remain
       ↓ (paca no longer involved)
Obsidian Git plugin (every 30 min)
  → git add -A && git commit && git push
```

## Specs and status

Specs: [`openspec/specs/knowledge-pipeline/`](../../openspec/specs/knowledge-pipeline/),
`knowledge-search-tool`, `knowledge-reindex`, `knowledge-review`,
`dashboard-knowledge-ingest`, `dashboard-knowledge-review`.

Current status: the artifact pipeline, GBrain ingest/search, the weekly
re-ingest workflow baseline, the `paca doctor` GBrain health check, the
spaced-repetition review layer (`knowledge_reviews` table, the fixed
Ebbinghaus curve, `paca knowledge review`, and the `/knowledge` review section),
and the redesigned dashboard `/knowledge` page are all in place. The dashboard provides
the wiki tree, ANN search, a preview pane, and a `Re-index` trigger; interface
copy goes through dashboard i18n (defaults to English, switchable to Chinese),
while wiki document content itself is never translated.

`/knowledge`'s wiki tree supports file management (dashboard-only, via server
actions): it displays the real directory structure nested (including empty
directories, with per-article `<slug>/<slug>.md` collapsed into a single
document), with a delete button on row hover plus a confirmation dialog.
**Creating a folder** means creating the directory and appending the path to
`configs/knowledge_taxonomy.yaml` (a text-line splice that preserves comments and
alignment rather than reserializing the file). **Deleting a folder or file** only
removes wiki files (deleting a folder also prunes the matching taxonomy entry)
and **does not touch the GBrain index or the raw archive** — index consistency is
what `Re-index` is for. The tree and taxonomy rewrite logic lives in
`dashboard/lib/wiki.ts` + `dashboard/lib/taxonomy.ts`, with the actions in
`dashboard/lib/actions/knowledge.ts` (path-traversal validation +
`revalidatePath`).

`/knowledge` also has an ingest form (URL input plus an optional folder
`<select>`, grouped by taxonomy namespace with the option `title` showing scope)
and an "in-progress ingests" panel. Both ingest entrypoints (the knowledge form
and `/radar`'s Ingest to wiki) go through the dashboard's shared in-memory job
registry (`lib/ingest/jobs.ts`, spawning
`paca knowledge ingest … --progress`), and the panel subscribes over SSE
(`/api/knowledge/ingest/stream`) to show live fetch/clean/enrich/classify/persist
progress per source label.

The `/radar` entrypoint first resolves a radar row into ordinary ingest input:
Folo sources use `source_id` with `folocli entry get` to pull the full text,
stage it as `PACA_AGENT_TMP_DIR/radar-ingest/*.html`, and then ingest; non-Folo
sources validate `radar_items.url` and ingest the URL directly. The knowledge
pipeline itself does not understand internal references like `radar://` — it only
handles URLs and staged files. The registry is single-process in-memory state, so
restarting the dashboard loses the progress view of in-flight jobs (the child
process and artifact writes are unaffected). The runner defensively skips
non-event JSON lines, since structlog writes to stdout by default.
