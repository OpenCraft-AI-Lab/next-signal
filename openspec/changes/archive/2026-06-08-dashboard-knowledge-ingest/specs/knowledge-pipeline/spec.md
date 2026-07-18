## MODIFIED Requirements

### Requirement: `paca knowledge ingest` accepts URLs and files

The CLI command `paca knowledge ingest <url|file>` SHALL detect the source type (microblog article, YouTube, Bilibili, PDF, Office, HTML, image, plain markdown) and route to the matching adapter. The command SHALL accept an optional `--category <path>` flag that pins the destination wiki folder, and an optional `--progress` flag that emits one JSON event per pipeline step to stdout. With both flags absent the command behaves as before (automatic classification, single result-JSON line on stdout).

#### Scenario: WeChat article saved

- **WHEN** `paca knowledge ingest https://mp.weixin.qq.com/s/<id>` is run
- **THEN** the OpenCLI adapter downloads the article + images to the raw store, rewrites image references to local relative paths, and emits clean markdown

#### Scenario: YouTube video saved

- **WHEN** the input URL is a YouTube link
- **THEN** the MarkItDown adapter writes the converted markdown and a raw conversion JSON

#### Scenario: category pinned via flag

- **WHEN** `paca knowledge ingest <url> --category knowledge/ai-ml` is run with a path present in the taxonomy
- **THEN** the artifact is written under that folder and the LLM classification step is skipped

#### Scenario: unknown category rejected

- **WHEN** `paca knowledge ingest <url> --category not/a/real/path` is run
- **THEN** the command fails loud with a non-zero exit before performing the ingest work

#### Scenario: progress events streamed

- **WHEN** `paca knowledge ingest <url> --progress` is run
- **THEN** stdout contains one JSON event line per pipeline step as each step starts and completes, followed by the final result JSON as the last line, with all lines forming valid JSONL

## ADDED Requirements

### Requirement: Category override skips classification

`ingest_one` and the ingest workflow SHALL accept an optional category override. When a valid taxonomy category is supplied, the classify step SHALL use it and NOT invoke the classifier agent; when omitted, automatic classification runs as before. An override that is not a declared taxonomy category SHALL be rejected with a loud error before fetch work begins, with no silent fallback.

#### Scenario: valid override bypasses the classifier

- **WHEN** `ingest_one(value, category="investing/quant")` is called with a taxonomy-valid path
- **THEN** the resulting artifact's category is `investing/quant` and the `knowledge_classifier` agent is not invoked

#### Scenario: omitted override classifies automatically

- **WHEN** `ingest_one(value)` is called with no category
- **THEN** the classify step runs the classifier agent as in current behavior

#### Scenario: invalid override fails loud

- **WHEN** `ingest_one(value, category="bogus")` is called with a path absent from the taxonomy
- **THEN** a loud error is raised and no artifact is written

### Requirement: Per-step progress callback

`ingest_one` and the ingest workflow SHALL accept an optional progress callback invoked as each pipeline step starts and completes, receiving an event identifying the step name and its status (start, done, or error). The callback SHALL be optional; when absent, ingest behaves exactly as today. The final result JSON shape SHALL be unchanged regardless of whether a callback is supplied.

#### Scenario: callback receives one event per step transition

- **WHEN** `ingest_one(value, on_progress=cb)` runs to completion for a supported input
- **THEN** `cb` is called with a start and a done event for each of the fetch, clean, enrich, classify, and persist steps

#### Scenario: callback reports a failing step

- **WHEN** a pipeline step raises during `ingest_one(value, on_progress=cb)`
- **THEN** `cb` receives an error event naming the failing step before the error propagates

#### Scenario: result shape unchanged with a callback

- **WHEN** `ingest_one(value, on_progress=cb)` completes successfully
- **THEN** the returned result still includes `ok`, `source_type`, `category`, `markdown_path`, `raw_path`, `frontmatter`, and optional `ingest` with their existing meanings
