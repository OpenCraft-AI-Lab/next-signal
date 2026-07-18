## 1. Source detection

- [x] 1.1 In `src/paca/workflows/stages/knowledge_ingest/classify.py::detect_source_type`, add a branch that returns `"github"` when `host == "github.com"` and the URL path is exactly `/<owner>/<repo>` (trailing slash tolerated); raise `RuntimeError` for any other github.com path (sub-paths, single-segment, gists, user pages)
- [x] 1.2 Add tests in `tests/` covering: root URL accepted, root URL with trailing slash accepted, `/blob/...` rejected, `/tree/...` rejected, `/issues/...` rejected, `/owner` (single segment) rejected

## 2. GitHub knowledge integration

- [x] 2.1 Create `src/paca/integrations/knowledge/github.py` with an `extract_github(url) -> dict` entry point returning `{ok, title, markdown, metadata, raw}` (matches the bilibili adapter shape)
- [x] 2.2 Implement URL parser inside the module that re-validates `owner/repo` and raises on subpaths (defensive double-check, no fallback)
- [x] 2.3 Implement six API calls with per-call try/except so non-README sections fail soft: `GET /repos/{owner}/{repo}`, `GET /repos/{owner}/{repo}/contents/`, `GET /repos/{owner}/{repo}/releases?per_page=3`, `GET /repos/{owner}/{repo}/contents/<manifest>` (try `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod` in order, first 200 wins), `GET /repos/{owner}/{repo}/commits?per_page=10`, `GET /repos/{owner}/{repo}/languages` (+ contributors count via `?per_page=1` Link header)
- [x] 2.4 Implement README fetch via `GET /repos/{owner}/{repo}/readme`; if this call fails, raise `RuntimeError` (README is mandatory)
- [x] 2.5 Read `GITHUB_TOKEN` via `env("GITHUB_TOKEN", required=False)` (or equivalent in `_helpers`) at the start of each call; attach the `Authorization` header only when the token is set; always send the standard `Accept: application/vnd.github+json` and `X-GitHub-Api-Version: 2022-11-28` headers
- [x] 2.6 Assemble structured markdown with the exact section order from design.md (`# owner/repo`, `## Repo Signals`, `## Project Layout`, `## Recent Releases`, `## Manifest (<file>)`, `## Recent Commits`, `## Activity`, `## README`); truncate README to ~12000 chars
- [x] 2.7 Add a unit test for the URL parser (root vs subpaths) and a smoke test for `extract_github` against a small public repo, marked `@pytest.mark.integration` and skipped by default

## 3. Fetch wiring

- [x] 3.1 Add `fetch_github(value, *, category)` to `src/paca/workflows/stages/knowledge_ingest/fetch.py` following the bilibili template: build a `KnowledgeArtifact` via `_new_artifact(value, "github", category)`, call `extract_github`, write `metadata.json` and `readme.md` into the raw store via `write_raw_text`, set `artifact.raw_path` to the README file, populate `title` / `markdown` / `metadata`
- [x] 3.2 Register `"github": fetch_github` in `_FETCHERS`

## 4. GitHub body cleaner agent

- [x] 4.1 Create `configs/agents/knowledge_github_cleaner.yaml` (model: `local`, `extra: {db: false, shared_context: false}`) — same shape as `knowledge_artifact_editor.yaml`, only the prompt + name differ
- [x] 4.2 Create `prompts/agents/knowledge_github_cleaner.md`. Prompt MUST instruct the model to: (a) **drop** badge rows, hero images / logos, ToC blocks, install commands, long quickstart code blocks (keep at most one minimal conceptual example), CI / build status blurbs, contributor / sponsor / acknowledgement / "buy-me-a-coffee" sections, "made with X" footers, LICENSE sections; (b) **preserve** what the project is and isn't, key features, how it differs from alternatives, core concepts / architecture, caveats, real use cases; (c) **output** tight prose with markdown structure (`##` / `###` headers, bullet lists), no emoji, no marketing copy. Output is plain markdown (same shape as `knowledge_artifact_editor` returns — no JSON schema)
- [x] 4.3 In `src/paca/workflows/stages/knowledge_ingest/artifact_editor.py`:
    - Add `_MIN_GITHUB_README_RETENTION = 0.20` next to the existing retention constants
    - Add an `agent_name: str = "knowledge_artifact_editor"` kwarg to `_run_editor` (default keeps every existing caller unchanged) and use it to pick which agent `build_from_name` loads
    - In `clean_body`, add a new branch (before the generic `else`) for `source_type == "github" and "## README" in original` that partitions on `## README`, sends only the prose to `_run_editor(..., agent_name="knowledge_github_cleaner")`, runs `_check_summarized("github-readme", prose, cleaned, _MIN_GITHUB_README_RETENTION)`, and stitches `head + sep + cleaned` back into `artifact.markdown` (mirrors the bilibili / youtube transcript branch)
- [x] 4.4 Add a unit test (mock `build_from_name` + agent run) verifying: (a) a github artifact routes to `knowledge_github_cleaner` with only the prose under `## README` as input, (b) the assembled signal sections above `## README` are preserved verbatim in the final body, (c) a non-github artifact still routes to `knowledge_artifact_editor` unchanged, (d) cleaned README below the 0.20 floor raises

## 5. GitHub summary agent

- [x] 5.1 Create `configs/agents/knowledge_github_summary.yaml` (model: `local`, `extra: {db: false, shared_context: false}`) — same shape as `knowledge_frontmatter.yaml`, only the prompt + name differ
- [x] 5.2 Create `prompts/agents/knowledge_github_summary.md`. The prompt MUST instruct the model to write a single `summary` text covering, in order, four perspectives in one cohesive block: (1) **Does** — one sentence on what the repo does; (2) **Value** — why bookmark it (unique angle / pain solved / how it compares to alternatives); (3) **Maturity** — pick from `production-ready` / `stable` / `active-development` / `experimental` / `abandoned`, inferred from stars, last push, release cadence, open-issue ratio; (4) **Ecosystem** — short language+domain slug (e.g. `python/data`, `rust/cli`, `kubernetes`, `javascript/frontend`). Output schema is the standard `FrontmatterDraft`:
    - `summary`: all four perspectives as prose
    - `tags`: 2–5 tags chosen for cross-source retrieval. MUST include the primary language (e.g. `python`, `rust`, `go`, `typescript`) and the domain / use-case slug derived from ecosystem (e.g. `cli`, `web-framework`, `data-pipeline`, `observability`, `llm`, `database`). MAY include 1–2 concept tags (e.g. `async`, `wasm`, `vector-search`) when they help retrieval. MUST NOT include vacuous tags (`github`, `repository`, `open-source`, `tool`, `library`) and MUST NOT copy GitHub `topics` verbatim — pick what's useful for the user's wiki taxonomy, not what the maintainer used for SEO
    - `freshness`: same Literal rules as the default agent. Most live repos are `evolving`; long-stable single-purpose libraries are `stable`; abandoned (no push in ~2 years, no open releases) is `ephemeral`
- [x] 5.3 In `src/paca/workflows/stages/knowledge_ingest/artifact_editor.py::write_frontmatter`, pick the agent name based on `artifact.source_type`: `"knowledge_github_summary"` when `source_type == "github"`, else `"knowledge_frontmatter"`. Both branches call `run_structured(..., FrontmatterDraft)` — schema, `to_artifact_edit()`, and the rest of the function stay untouched
- [x] 5.4 Add a unit test that the github source picks `knowledge_github_summary` and any other source picks `knowledge_frontmatter` (mock `build_from_name` and `run_structured`)

## 6. Docs and verification

- [x] 6.1 Update `docs/modules/knowledge.md` to list `github` as a supported source type and note the deeper-signal extraction, the dedicated cleaner + summary agents, and the token-optional behavior
- [x] 6.2 Run `uv run pytest -q` and confirm all existing tests still pass; new tests added in tasks 1.2, 2.7, 4.4, and 5.4 also pass
- [x] 6.3 Manual smoke verified end-to-end on `https://github.com/msitarzewski/agency-agents`: (a) signal sections (`## Repo Signals`, `## Project Layout`, `## Recent Commits`, `## Activity`) preserved verbatim; missing sections (`## Recent Releases`, `## Manifest`) soft-failed and omitted as designed; README condensed from raw 58 kB to a ~5-paragraph tight prose block (no badges / install / sponsor blocks). (b) Summary explicitly covers does (AI agent collection) / value (specialized expertise vs prompt templates) / maturity (`active-development`) / ecosystem (shell automation + AI agent orchestration). Tags `["shell", "ai-agents", "automation", "llm", "cli"]` follow the cross-source-retrieval rules. (c) Raw store at `wiki-raw/github/0b6244279772/` contains `metadata.json` (6.2 kB) + `readme.md` (58 kB). Bonus finding: a stale `GITHUB_TOKEN` returned 401 on the first call; added a session-scoped anonymous fallback (logged loud warning, then degraded) so public-repo bookmarking still works through expired tokens. New test `test_github_401_falls_back_to_anonymous` covers it.
