## ADDED Requirements

### Requirement: GitHub repo URLs are a first-class source type

`paca knowledge ingest` SHALL detect `https://github.com/<owner>/<repo>` as `source_type == "github"` and route it to a GitHub-specific adapter that collects signal beyond the rendered README. Non-root GitHub URLs (paths beyond `/<owner>/<repo>`, including `/blob`, `/tree`, `/issues`, `/pull`, gist, and user-only pages) SHALL raise a loud error rather than falling back to the generic web adapter.

#### Scenario: root repo URL is recognized

- **WHEN** `paca knowledge ingest https://github.com/<owner>/<repo>` is run (with or without a trailing slash)
- **THEN** detection returns `source_type == "github"` and the github fetcher runs

#### Scenario: subpath URL is rejected loud

- **WHEN** the input is `https://github.com/<owner>/<repo>/blob/...`, `/tree/...`, `/issues/...`, `/pull/...`, a single-segment user URL, or any other non-root GitHub path
- **THEN** detection raises `RuntimeError` instead of routing to the generic web adapter

### Requirement: GitHub adapter assembles deep-signal markdown

The github fetcher SHALL produce a clean markdown packet with sections covering: repo metadata (description, license, language, stars, forks, open issues, topics, default branch, timestamps), project layout (top-level directory listing), recent releases (up to 3), the first matching top-level manifest file (`pyproject.toml`, `package.json`, `Cargo.toml`, or `go.mod`), recent commit subjects (up to 10), activity (contributors count, language breakdown), and the README body. Non-README signal sections that fail to fetch SHALL be silently omitted from the packet; failure to obtain the README SHALL raise a loud error.

#### Scenario: README missing causes loud failure

- **WHEN** the repo has no fetchable README
- **THEN** the fetcher raises an error and no artifact is written

#### Scenario: optional section failure does not abort

- **WHEN** the releases or manifest endpoint fails or returns 404
- **THEN** the packet omits that section and the ingest still succeeds with the README plus the other sections that did fetch

### Requirement: GitHub adapter authenticates only when a token is configured

The github fetcher SHALL read `GITHUB_TOKEN` at call time and send authenticated requests when it is set; when unset, it SHALL fall back to anonymous GitHub REST access and not require any environment configuration.

#### Scenario: token absent

- **WHEN** `GITHUB_TOKEN` is not set and the input is a public repo
- **THEN** the fetcher completes successfully using anonymous GitHub REST access

#### Scenario: token present

- **WHEN** `GITHUB_TOKEN` is set
- **THEN** the fetcher sends an `Authorization: Bearer <token>` header on each request

### Requirement: GitHub artifacts use a source-specific body cleaner

For `source_type == "github"` the `clean_body` step SHALL send only the `## README` section of the assembled markdown to a dedicated `knowledge_github_cleaner` agent and keep the structured signal sections (`## Repo Signals`, `## Project Layout`, `## Recent Releases`, `## Manifest`, `## Recent Commits`, `## Activity`) verbatim. The retention floor for the cleaned README SHALL be lower than the generic article floor so aggressive condensation is permitted; below the floor the workflow SHALL fail loud.

#### Scenario: README section is the only part cleaned

- **WHEN** a github artifact body is processed by `clean_body`
- **THEN** the structured signal sections above `## README` are preserved byte-for-byte in the output and only the README prose is replaced with the cleaner's output

#### Scenario: non-github source uses default cleaner

- **WHEN** the artifact's `source_type` is anything other than `"github"`
- **THEN** `clean_body` invokes the existing `knowledge_artifact_editor` agent under its existing rules and retention floor

#### Scenario: cleaner over-condensation fails loud

- **WHEN** `knowledge_github_cleaner` returns README markdown shorter than the github retention floor
- **THEN** the workflow raises a loud failure and no artifact is written

### Requirement: GitHub artifacts use a source-specific frontmatter agent

For `source_type == "github"` the artifact edit phase SHALL produce frontmatter via the `knowledge_github_summary` agent under the existing `FrontmatterDraft` schema. The github agent's prompt SHALL instruct the model to organize the single `summary` text around four perspectives: what the repo *does*, its *value* / why bookmark it, *maturity*, and *ecosystem*. The schema, the `to_artifact_edit()` contract, and the downstream `persist` / GBrain ingest path SHALL remain identical to other source types — only the agent identity and its prompt differ.

#### Scenario: github source routes to github summary agent

- **WHEN** the artifact's `source_type` is `"github"` and the artifact body is ready for frontmatter
- **THEN** `write_frontmatter` invokes the `knowledge_github_summary` agent under the `FrontmatterDraft` schema

#### Scenario: non-github source uses default frontmatter agent

- **WHEN** the artifact's `source_type` is anything other than `"github"`
- **THEN** `write_frontmatter` invokes the existing `knowledge_frontmatter` agent under the `FrontmatterDraft` schema

#### Scenario: github frontmatter validation failure is loud

- **WHEN** the `knowledge_github_summary` agent fails to produce a valid `FrontmatterDraft` (empty summary, no valid English tags, malformed freshness)
- **THEN** the workflow raises a loud failure and no artifact is written

### Requirement: GitHub raw store keeps metadata JSON and README original

The github fetcher SHALL write the raw `/repos/{owner}/{repo}` JSON response and the decoded README pre-truncation into the raw store, and SHALL set the artifact's `raw_path` to the README file.

#### Scenario: raw artifacts persist

- **WHEN** a github URL is ingested successfully
- **THEN** the raw store directory for the artifact contains both `metadata.json` (the repo API response) and `readme.md` (the original decoded README)
