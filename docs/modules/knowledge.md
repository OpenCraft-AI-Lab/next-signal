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

## Agents

| Agent | Model profile | Used for |
|---|---|---|
| `knowledge_artifact_editor` | local | Ingest's clean step: body cleanup / whisper correction (DB-free transformation agent) |
| `knowledge_github_cleaner` | local | GitHub-repo-specific clean step: aggressively trims only the `## README` section (badges, install commands, sponsor blocks); structured signal sections are preserved verbatim |
| `knowledge_frontmatter` | local | Ingest's enrich step: produces summary/tags/freshness (`FrontmatterDraft` schema, DB-free) |
| `knowledge_github_summary` | local | GitHub-repo-specific enrich step: organizes the summary around does/value/maturity/ecosystem, reusing the `FrontmatterDraft` schema |
| `knowledge_classifier` | local | Picks the wiki category directory from the taxonomy at ingest time (DB-free transformation agent) |

## Tools

Knowledge-domain tools:

- `knowledge_ingest_workflow` — the single-article ingest path (fetch → edit →
  classify → persist).

KB **retrieval** is cross-cutting infrastructure and does not belong to this
module: `search_knowledge` plus `gbrain_search` / `gbrain_get` / `gbrain_query` /
`gbrain_ingest` live in `paca/tools/gbrain.py`, and the GBrain bridge is
`paca/integrations/gbrain.py`. Agents in any module can reference these tools by
name.

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
- Index: GBrain's own local storage

## How to use it

```bash
uv run paca knowledge ingest <url|staged-file>
uv run paca knowledge ingest <url> --category knowledge/ai-ml   # pick the destination folder (skips auto-classification)
uv run paca knowledge ingest <url> --progress                   # one JSON event per pipeline step, plus a final result JSON line
uv run paca knowledge gbrain-search "query"
uv run paca run-workflow knowledge_ingest            # re-ingest changed files + refresh every Related block
```

`--category` must be a path that exists in `configs/knowledge_taxonomy.yaml`;
invalid values fail loud before the fetch. `--progress` feeds the dashboard's
ingest progress panel (see below). Local file input is accepted only for files
staged under `PACA_AGENT_TMP_DIR`; `/radar`'s Folo ingest respects that boundary
too, writing the full-text HTML into that directory first and then handing the
file path to the generic knowledge pipeline.

## Invariants

- A GBrain ingest failure must never lose the artifact: the clean wiki and raw
  files stay on disk and the workflow fails loud. The run is not marked
  successful; once GBrain is fixed, direct ingest or the weekly sync backfills the
  index.
- The re-ingest manifest advances only after a successful index — otherwise later
  runs skip the file and KB search goes stale.
- Direct ingest and re-ingest must derive the same GBrain-safe slug from the
  wiki-relative path. Non-ASCII paths get a stable hash suffix so GBrain pages
  cannot collide.
- Wiki filenames derive from the title, and frontmatter records a `digest` (a
  source hash) as the same-origin identity: a same-origin re-ingest overwrites in
  place (idempotent update), while an identical title from a different source
  gets a new file with a `-<digest[:8]>` suffix. Never silently overwrite someone
  else's article — including collisions across the two directory layouts.
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
`knowledge-search-tool`, `knowledge-reindex`, `dashboard-knowledge-ingest`.

Current status: the artifact pipeline, GBrain ingest/search, the weekly
re-ingest workflow baseline, the `paca doctor` GBrain health check, and the
redesigned dashboard `/knowledge` page are all in place. The dashboard provides
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
