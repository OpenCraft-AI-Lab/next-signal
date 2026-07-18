## Why

User wants to bookmark GitHub repos through `paca knowledge ingest`, but the current pipeline only detects WeChat / YouTube / Bilibili / web / file inputs. Falling back to the generic `web` adapter on a GitHub URL produces a shallow README dump and a generic frontmatter summary that fails to capture the things that matter for a saved repo: what it does, why it's worth keeping, how mature it is, and which ecosystem it lives in.

## What Changes

- Add `github` as a first-class `source_type` in the knowledge ingest pipeline (detected when host is `github.com` and path is exactly `/owner/repo`).
- Add `paca/integrations/knowledge/github.py`: collects six signal classes from the GitHub REST API (repo metadata, top-level file tree, latest 3 releases, top-level manifest file, latest 10 commits, contributors count + language breakdown) and assembles a structured markdown packet for the rest of the pipeline.
- Add `fetch_github` in `paca/workflows/stages/knowledge_ingest/fetch.py` and register it in `_FETCHERS`. Raw store keeps the repo metadata JSON and the original README text.
- Add a GitHub-specific body cleaner agent `knowledge_github_cleaner` (YAML + prompt only) for the `clean_body` step. README content is noisy (badge rows, install commands, ToC, sponsor / contributor / acknowledgement blocks, marketing copy) and the generic `knowledge_artifact_editor`'s 60% retention guard actively prevents the aggressive condensation a saved-repo artifact needs. The github cleaner has its own retention floor and a prompt that explicitly drops the noise classes and condenses prose. Only the `## README` section of the assembled markdown is sent to the cleaner; the structured `## Repo Signals` / `## Project Layout` / `## Recent Releases` / `## Manifest` / `## Recent Commits` / `## Activity` sections are kept verbatim (they're already signal-dense).
- Add a GitHub-specific frontmatter agent `knowledge_github_summary` (YAML + prompt only). It outputs under the **existing** `FrontmatterDraft` schema — same `summary` / `tags` / `freshness` contract — but its prompt instructs the model to organize the single `summary` text around four perspectives: *what the repo does*, *its value / why bookmark it*, *maturity*, *ecosystem*. The artifact editor's `write_frontmatter` step picks this agent when `source_type == "github"` and the default agent otherwise. No schema changes, no new tag conventions, no `persist` changes.
- Subpath GitHub URLs (`/blob/...`, `/tree/...`, `/issues/...`, etc.) raise `RuntimeError` instead of silently falling back to the generic web fetcher — keeps the contract honest (this adapter saves *repos*, not arbitrary GitHub pages).
- `GITHUB_TOKEN` is optional: present → authenticated, absent → anonymous (60/h rate limit, fine for personal bookmarking). Token read at call time.

## Capabilities

### New Capabilities

_(none — this extends the existing pipeline)_

### Modified Capabilities

- `knowledge-pipeline`: extend `paca knowledge ingest` source detection to recognize GitHub repo URLs, add a deeper-than-README extraction path for them, and allow source-type-specific body cleaner and frontmatter agents during the artifact edit phase.

## Impact

- New file: `src/paca/integrations/knowledge/github.py`.
- Modified: `src/paca/workflows/stages/knowledge_ingest/classify.py` (detect), `fetch.py` (fetcher + `_FETCHERS` entry), `artifact_editor.py` (route both `clean_body` and `write_frontmatter` on `source_type`, add a github retention floor). `schemas.py` is **not** touched — the github frontmatter agent reuses `FrontmatterDraft`.
- New configs: `configs/agents/knowledge_github_cleaner.yaml`, `configs/agents/knowledge_github_summary.yaml`.
- New prompts: `prompts/agents/knowledge_github_cleaner.md`, `prompts/agents/knowledge_github_summary.md`.
- New tests for `detect_source_type` (github root accepted, subpaths rejected), a smoke test for the github integration's URL parser, and a unit test for the `clean_body` / `write_frontmatter` source-type branching.
- Env: `GITHUB_TOKEN` already documented for the existing horizontal `paca/integrations/github.py` — no new env required.
- No DB / migration / scheduler changes. No other `source_type` pipelines touched.
