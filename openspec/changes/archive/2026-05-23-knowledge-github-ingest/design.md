## Context

The current `knowledge_ingest` pipeline handles 6 `source_type`s — `markdown`, `markitdown`, `youtube`, `web`, `wechat`, `bilibili` — each with its own fetcher in `paca/workflows/stages/knowledge_ingest/fetch.py`. Detection is deterministic and host-based in `classify.py::detect_source_type`. After fetch, all source types share `clean_body` + `write_frontmatter` (`knowledge_artifact_editor` + `knowledge_frontmatter` agents).

A GitHub URL currently falls into the generic `web` route. That route just HTML-to-markdown'd the public repo page, which means the artifact body is essentially the README plus GitHub chrome, and the generic frontmatter writer produces a vanilla "this article describes X" summary. For a saved repo the things that matter most — *what it does*, *its value proposition*, *maturity*, *ecosystem positioning* — are exactly what the generic flow flattens out.

GitHub's REST API exposes much richer structured signal than the rendered page: repo metadata, file tree, releases, manifest files, recent commits, contributors, languages. Combining these with the README gives the LLM enough material to produce a real assessment, not a paraphrase.

This change adds `github` as a first-class `source_type` and introduces a source-type-specific frontmatter agent — the first time the pipeline branches at the frontmatter step.

## Goals / Non-Goals

**Goals:**

- Detect `https://github.com/owner/repo` (root path only) as `source_type == "github"`.
- Collect six signal classes via GitHub REST and assemble a structured markdown packet for the rest of the pipeline.
- Aggressively condense the README portion of that packet (dropping badges, install commands, ToCs, sponsor / contributor / acknowledgement blocks, marketing copy) via a dedicated body cleaner agent. The assembled metadata sections are kept verbatim.
- Produce a frontmatter `summary` that explicitly covers *does* / *value* / *maturity* / *ecosystem* via a dedicated agent, while keeping the existing `FrontmatterDraft` schema and `{summary, tags, freshness}` contract — downstream consumers (`persist`, GBrain, wiki UI) are byte-identical to other source types.
- Work without a `GITHUB_TOKEN` (anonymous 60/h rate limit) and use one when present — read at call time, never at import.
- Keep all other `source_type` flows byte-for-byte unchanged.

**Non-Goals:**

- Subpath URLs (`/blob`, `/tree`, `/issues`, `/pull`, gist, user pages). Subpaths raise `RuntimeError` so the user knows the adapter saves *repos*, not arbitrary GitHub pages.
- Cloning repos, indexing source files, or running any code locally.
- New env vars. `GITHUB_TOKEN` is already declared by the horizontal `paca/integrations/github.py`.
- Refactoring the existing horizontal `paca/integrations/github.py` (cross-cutting agent-facing tools). The new file is a knowledge-domain adapter and does not import from there.

## Decisions

### 1. New file `paca/integrations/knowledge/github.py` (don't reuse the horizontal one)

The horizontal `paca/integrations/github.py` exposes agent-facing `@tool` functions (`gh_list_issues`, `gh_get_file`, …). Per the project's `tools/` vs `integrations/` boundary (CLAUDE.md), knowledge-domain extraction is a private workflow concern. It should not surface as an LLM-callable tool, and a knowledge adapter should not import from the agent-facing tool layer — that direction of dependency is fine downward (`tools → integrations`) but the knowledge adapter is itself at the integration layer.

The auth pattern (`Authorization: Bearer <GITHUB_TOKEN>` from `env()` at call time, standard accept + version headers) is duplicated verbatim — ~5 lines, not worth a shared helper that would couple the two layers.

**Alternative considered:** import `_headers()` from the horizontal file. Rejected: introduces a horizontal-from-integration import, and `_headers()` currently requires a token (will raise on absence), while the knowledge adapter needs graceful anonymous fallback.

### 2. Anonymous fallback when `GITHUB_TOKEN` is missing

Personal bookmarking is bursty and low-frequency. Anonymous rate limit (60 requests / hour / IP) is plenty for ad-hoc saves, while requiring a token would block the user from a feature they reasonably expect to "just work".

**Alternative considered:** loud failure when token missing (matches CLAUDE.md "失败要 loud"). Rejected: token absence is a *configuration* choice, not a runtime failure. The rule applies to *unexpected* failure modes — anonymous access is expected and supported by GitHub.

If anonymous rate-limit is hit at runtime, the GitHub 403 response surfaces through `response.raise_for_status()` and fails loud, which is the right behavior.

### 3. Six signal classes, assembled into structured markdown sections

The markdown packet handed to `clean_body` has fixed sections:

```
# owner/repo

## Repo Signals
- Source / Description / Homepage / License / Language
- Stars / Forks / Open Issues / Watchers
- Created / Pushed / Default branch
- Topics

## Project Layout
<top-level dirs and files, one per line>

## Recent Releases
<up to 3 releases: name, tag, published, truncated body>

## Manifest (<filename>)
<truncated content of pyproject.toml | package.json | Cargo.toml | go.mod — first match>

## Recent Commits
<up to 10 commit subjects with short SHA>

## Activity
- Contributors: <count from Link header total or list length>
- Languages: <top 4 languages with byte percentages>

## README
<decoded README markdown, truncated to ~12000 chars>
```

Any non-README section that fails (network, 404, parse) is skipped silently within its own section — the others still ship. README failure is fatal: a repo with no README is rare enough, and without it the summary agent has nothing to work with.

**Alternative considered:** flat README + sidebar JSON. Rejected: the LLM produces much more grounded summaries when signals are labelled and sectioned than when given JSON to interpret.

### 4. New agent `knowledge_github_cleaner` aggressively condenses only the README section

`clean_body` already branches on `source_type` for bilibili / youtube: it partitions on `## Transcript` so the scaffold (`# title`, `## Metadata`) stays verbatim and only the transcript prose goes through the editor with a transcript-specific retention floor. The github branch mirrors this exactly:

```python
elif artifact.source_type == "github" and "## README" in original:
    head, sep, prose = original.partition("## README")
    cleaned = _run_editor(artifact, prose.strip(), agent_name="knowledge_github_cleaner")
    _check_summarized("github-readme", prose, cleaned, _MIN_GITHUB_README_RETENTION)
    artifact.markdown = f"{head.rstrip()}\n\n{sep}\n\n{cleaned}\n"
```

The `## Repo Signals`, `## Project Layout`, `## Recent Releases`, `## Manifest (...)`, `## Recent Commits`, and `## Activity` sections are kept verbatim — they're already concise, structured signal that we deliberately assembled in fetch. Sending them through a cleaning agent risks the model rewording stars/forks numbers, reordering signal blocks, or summarizing across sections it shouldn't merge.

`_run_editor` grows an `agent_name` kwarg defaulting to `"knowledge_artifact_editor"` (zero change for existing callers). The github branch passes `"knowledge_github_cleaner"`.

`_MIN_GITHUB_README_RETENTION = 0.20` (vs `_MIN_LONG_TEXT_RETENTION = 0.60` for articles): heavy condensation is the explicit goal. The floor's job here is only to catch pathological collapse-to-one-line, not to enforce information preservation.

`knowledge_github_cleaner`'s prompt instructs the model to:

- **Drop** badge rows, hero images / logos, ToC blocks, install commands, long quickstart code blocks (keep at most one minimal conceptual example), CI / build status blurbs, contributor / sponsor / acknowledgement / "buy-me-a-coffee" sections, "made with X" footers, and LICENSE sections (license is in `## Repo Signals`).
- **Preserve** the substance: what the project is and isn't, key features, how it differs from alternatives, core concepts / architecture, caveats, real use cases.
- **Output** tight prose with markdown structure (`##` / `###` headers, bullet lists) — no emoji, no marketing copy, no decoration.

**Alternative considered:** keep `knowledge_artifact_editor` and just relax the retention guard for github. Rejected: the editor's *prompt* is also article-shaped — it's told to preserve content, fix typography, normalize spacing. Telling the same agent to behave differently for github sources is a polymorphism we'd have to maintain in one prompt. Cleaner to give github its own role.

**Alternative considered:** clean the whole packet (including `## Repo Signals` etc.) as one body. Rejected: those sections are already concise and structured; the cleaner would either no-op on them (waste) or rewrite them (risk corrupting deliberately formatted signal).

### 5. New agent `knowledge_github_summary` reuses `FrontmatterDraft`; only the prompt differs

`artifact_editor.write_frontmatter` becomes a one-line agent-name switch — schema and downstream contract are unchanged:

```python
agent_name = "knowledge_github_summary" if artifact.source_type == "github" else "knowledge_frontmatter"
agent = build_from_name(agent_name)
draft = run_structured(agent, agent_input, FrontmatterDraft)
artifact.artifact_edit = draft.to_artifact_edit()
```

The `knowledge_github_summary` prompt instructs the model to write a `summary` that explicitly covers four perspectives in one cohesive block:

1. **Does** — what the repo does in one sentence
2. **Value** — why it's worth bookmarking (unique angle, pain it solves, comparable projects it improves on)
3. **Maturity** — picked from a small bucket list (production-ready / stable / active-development / experimental / abandoned) inferred from stars, last push date, release cadence, open-issue ratio
4. **Ecosystem** — language + domain slug (e.g. `python/data`, `rust/cli`, `kubernetes`)

The four perspectives live inside the single `summary: str` field; no new schema, no extra frontmatter keys, no tag-namespace conventions. `tags` and `freshness` are populated by the same rules as every other source type via `_normalize_tags` and the `Freshness` Literal.

**Alternative considered:** split `summary` into named fields (`does` / `value` / `maturity` / `ecosystem`) on a new `GithubSummaryDraft` schema. Rejected: introduces a schema divergence between source types, requires special `to_artifact_edit()` synthesis to map back to `summary`, and the original motivation (forcing the model to pick a `maturity` enum) is overkill — a prompt explicitly listing the bucket list gets the same quality from a local model and stays inside the existing contract.

**Alternative considered:** keep `knowledge_frontmatter` and only enrich its prompt with a `if source_type == github` clause. Rejected: the project's pattern is one YAML/prompt per agent role; smearing a github-specific routine inside a generic agent is harder to evolve and harder to test.

### 6. Subpath URLs raise loud

`detect_source_type` checks `host == "github.com"` and the path. Exactly two non-empty segments → `"github"`. Anything else (`/blob`, `/tree`, `/issues`, `/owner` only, gist, etc.) → `RuntimeError`. We deliberately don't silently fall back to `web`: the user typed a GitHub URL expecting GitHub-aware handling, and "saved a single file under github.com" would be a confusing artifact in their wiki.

### 7. Raw store: repo metadata JSON + README original

Following bilibili's pattern of writing both raw HTML and the transcript JSON. The github adapter writes:

- `metadata.json` — full `/repos/{repo}` response (durable record even if API changes)
- `readme.md` — decoded README pre-truncation

`raw_path` on the artifact points at `readme.md`. Other signal blobs (releases, commits) are *not* persisted to raw — they're cheap to refetch and would bloat the raw tree for marginal value.

## Risks / Trade-offs

- **Rate limits without a token** → for normal individual use, anonymous 60/h is fine; if hit, GitHub returns 403 with a clear message and the workflow fails loud. Mitigation: documented in the agent's prompt + README; user can set `GITHUB_TOKEN` for higher limits.
- **Six API calls per ingest** → adds latency (~1-3s). Mitigation: each call has the 30s default timeout from `http_client()`; failures of non-README sections are non-fatal so a slow-but-partial collection still produces a useful artifact.
- **Cosmetic drift across source types** → github `summary` fields read like a structured does/value/maturity/ecosystem block while other sources read as free prose. Mitigation: it's a single text field, downstream is identical, and the divergence is intentional (github bookmarks need different perspectives than an article).
- **README size variance** → some repos have 50kB READMEs that swamp the context window. Mitigation: truncate to ~12000 chars (same constant as `_MAX_MARKDOWN_CHARS` budget already used in `artifact_editor.py`).
- **Auth code duplicated between `paca/integrations/github.py` and the new knowledge adapter** → low risk: ~5 lines, GitHub headers are stable and well-documented; extracting a shared helper would cross the horizontal/domain boundary CLAUDE.md is explicit about.
