## Context

The repo already has two ingest-style flows:

- `paca/workflows/knowledge_ingest.py` — agent-driven, on-demand, single-URL pipeline. Heavy: classification, LLM cleaning/enrichment, GBrain.
- `paca/tools/finance/financial_news.py` — domain-specific portfolio news pull with a 3-state cache and Moomoo as the only source.

Neither matches "give me everything new from N sources, on a schedule, no LLM, stash for later analysis." This change introduces that primitive.

The collector is intentionally separate from `tools/` (no agent calls it directly) and from `workflows/` (no LLM step). The only reason it touches `workflows/` at all is the existing scheduler dispatches by workflow name; a 5-line workflow shell lets us reuse that without expanding the scheduler schema.

## Goals / Non-Goals

**Goals:**

- One uniform shape for "fetch via CLI, parse stdout, upsert to Postgres."
- Zero LLM cost in the hot path.
- Source-level dedup that is automatic and impossible to forget (`UNIQUE (source, source_id)` + `ON CONFLICT DO NOTHING`).
- 30-day retention enforced by both writer (sweep) and reader (query window).
- Adding a new source = add a YAML entry + register one parser function.
- Operator can pull manually (`paca info-radar pull`) for debugging.

**Non-Goals:**

- Cross-source dedup (same article in two feeds = two rows; downstream analysis can collapse).
- Incremental `--cursor`/`--since` pulls. First version always pulls a fixed window; revisit if a source's volume regularly exceeds the configured `--limit`.
- LLM-based filtering, scoring, or summarization (next change).
- Surfacing radar items to agents as tools (will live in `paca/tools/info_radar/` when a consumer exists).
- Dashboard UI, Discord push (separate changes).

## Decisions

### D1. New top-level package `paca/collectors/` instead of reusing `workflows/` or `tools/`

`tools/` is defined by `CLAUDE.md` as agent-facing. `workflows/` composes agents and tools. Info-radar is neither — it's background CLI-driven data movement. Putting it in `tools/` invites future LLMs to call it (wrong); putting it in `workflows/` forces a no-op LLM ceremony.

**Considered:** wrap collector as a no-op `Workflow` class only. **Rejected** because the wrapping is only for the scheduler, and a fake workflow leaks LLM-shape semantics into a non-LLM module.

**Chosen:** real implementation lives under `paca/collectors/info_radar/`. A thin `paca/workflows/info_radar_pull.py` exists *only* to satisfy the scheduler — it imports and calls the collector and does nothing else.

### D2. `(source, source_id)` complex unique key, no cross-source dedup

Sources fall into two camps: RSS guid-style (folo timeline) and CLI-emitted native IDs (zhihu answer_id). Both are stable strings per source. Cross-source dedup would require URL canonicalization and/or content hashing — each has corner cases that produce false negatives or false positives. We avoid both.

**Chosen:** parser is responsible for extracting a `source_id` per item. `(source, source_id)` is a Postgres unique constraint; collector always uses `INSERT ... ON CONFLICT DO NOTHING`. No pre-check, no read-modify-write.

If a downstream analysis change wants cross-source dedup later, it can add a `content_hash` column and operate on top — without touching the collector.

### D3. Folo posture β — ignore Folo's unread state

`folocli` exposes `--unread-only` and `entry mark-read` / `mark-all-read`. Using them would mean the collector mutates state the user also touches via the Folo GUI/app, breaking their personal reading workflow.

**Considered:** posture α (pull `--unread-only`, mark-read after upsert). **Rejected** for the UX reason above.

**Chosen:** posture β. Collector always passes `--limit N` (no `--unread-only`, no mark-read). DB unique constraint absorbs repeated pulls. `--cursor` optimization deferred (see D7).

### D4. Source descriptor is YAML; parser is a registry name

```yaml
sources:
  - name: folo_articles_ai
    enabled: true
    cli:
      argv: ["npx", "folocli", "timeline", "--view", "articles", "--limit", "100"]
      timeout_sec: 60
    parser: folo_timeline
```

`parser:` is a key into `PARSERS: dict[str, Callable]` defined in `paca/collectors/info_radar/parsers/__init__.py`. Loader fails fast if the name is unknown.

**Considered:** dotted import path (`paca.collectors.info_radar.parsers.folo_timeline`). **Rejected** — typos surface late, and the registry doubles as a discoverable inventory of supported sources.

For opencli sources, `argv` uses an `${OPENCLI_BIN_ARGV}` placeholder that the loader expands at runtime via the existing `_opencli_bin()` helper from `paca/integrations/knowledge/opencli.py` (lifted into `paca/integrations/info_radar/opencli_runner.py` so this change doesn't reach into knowledge internals).

### D5. RadarItem dataclass + uniform parser contract

```python
@dataclass(frozen=True)
class RadarItem:
    source_id: str
    title: str
    url: str | None
    excerpt: str | None
    published_at: datetime | None
    payload: dict          # raw record, stored in JSONB

ParserFn = Callable[[str, str], list[RadarItem]]  # (stdout, source_name) -> items
```

The collector framework injects `source` from the YAML `name:` at write time, so parsers don't see it. `payload` keeps the raw upstream record verbatim; future migrations or reparses can re-derive fields without re-fetching.

### D6. Postgres business table; raw psycopg short-lived connections

```sql
CREATE TABLE radar_items (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    url           TEXT,
    title         TEXT NOT NULL,
    excerpt       TEXT,
    published_at  TIMESTAMPTZ,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    seen_at       TIMESTAMPTZ,
    payload       JSONB NOT NULL,
    UNIQUE (source, source_id)
);
CREATE INDEX radar_items_fetched_at_idx ON radar_items (fetched_at);
CREATE INDEX radar_items_unseen_idx     ON radar_items (fetched_at) WHERE seen_at IS NULL;
```

Mirrors the existing `seen_news` / `portfolio_tickers` pattern: DDL in `scripts/bootstrap_db.py`, runtime via `psycopg.connect(database_url())` short-lived sessions. No SQLAlchemy. No async.

`seen_at` is populated by the downstream analysis workflow (not in this change); we provision it now so analysis doesn't need a follow-up migration.

### D7. 30-day retention: writer sweep + reader window (belt and suspenders)

- **Writer**: collector calls `DELETE FROM radar_items WHERE fetched_at < now() - interval '30 days'` after every successful collection. Best-effort; failure logs but doesn't fail the pull.
- **Reader**: all query helpers automatically AND `fetched_at > now() - interval '30 days'` into the WHERE clause.

This makes correctness independent of any single mechanism: a misconfigured cron still cleans up on the next manual pull; a forgotten sweep clause in a query still hides expired rows.

### D8. Scheduler integration via thin workflow shell

```python
# paca/workflows/info_radar_pull.py
class InfoRadarPullWorkflow:
    def __call__(self, **_inputs) -> dict:
        from paca.collectors.info_radar.runner import run_all
        result = run_all()
        return {"sources_run": len(result), "items_written": sum(r.written for r in result)}
```

Registered in the workflow registry like any other; `configs/schedules.yaml` gets a normal entry. No scheduler code changes.

### D9. Per-source failure isolation; whole-run loud failure

If one source's CLI errors or its parser raises, log the failure, persist a structured error to per-run state, and continue with the next source. The whole pull returns a non-zero exit only if *every* source failed — partial success is the common case for flaky external CLIs.

This mirrors `register_all`'s try/except posture for integrations and matches the project's "fail loud" rule (the failed source raises `RuntimeError` internally; the runner catches it at source boundary).

### D10. CLI subcommand name: `paca info-radar` (with dash)

Per explicit user direction: "所有地方都要 info-radar，包括 cli 到名字." Subcommands: `paca info-radar pull [--source NAME]`, `paca info-radar sweep`. Internal Python module path uses underscore (`paca.collectors.info_radar`) per PEP 8; this is the only allowed deviation.

## Risks / Trade-offs

- **[npm cache cold start makes first hourly pull slow]** → Use `npx folocli` (not `--yes`) so cache is reused; document `npm i -g folocli` as a stability upgrade for the operator. `paca doctor` uses `--yes ... @latest` once to warm cache.
- **[`FOLO_TOKEN` not set or expired silently]** → `paca doctor` runs `folocli whoami`; collector raises a loud `RuntimeError` on first folo source pull if auth fails. No silent skip.
- **[opencli zhihu output schema unknown until task time]** → Task 1.1 explicitly runs `opencli zhihu --help -f yaml` and a sample call before parser is written; design.md gets an appendix once shape is known.
- **[Hourly pull volume exceeds `--limit 100`]** → Some items missed silently until next pull bumps `--limit`. Acceptable for v1 (Folo timeline rarely produces 100+/hour for personal subscriptions); mitigation is straightforward `--cursor` add-on.
- **[Parser drift between folocli versions]** → Pinning `folocli@<version>` in the source's `argv` is an operator-side ops decision, not a code change. Parsers should validate `ok == true` first and raise on schema surprises.
- **[Same RSSHub route subscribed in Folo AND fetched via opencli for the same site]** → Two rows for the same conceptual item. Acceptable per D2; downstream analysis can collapse.
- **[New top-level `paca/collectors/` package is a non-trivial architectural addition]** → Documented here and in CLAUDE.md addition; rule of thumb: "no LLM, no agent caller, periodic, writes a business table" lives here. If only the radar consumer ever uses it, future cleanup can fold it back, but until then a clear name beats squatting in `workflows/`.

## Open Questions

- **First batch source selection details**:
  - Which Folo timeline slice ships first — full timeline, `--view articles`, or a `--category`? Resolved in task 1.2 after operator logs in and reviews available views/categories.
  - Which `opencli zhihu` subcommand — `following`, `hot`, or per-question? Resolved in task 1.1 after `opencli zhihu --help -f yaml`.
- **Schedule cadence**: defaults to hourly in `configs/schedules.yaml`. Operator-tunable; this design doesn't dictate.
- **CLAUDE.md addition**: the new `paca/collectors/` package warrants a short paragraph in the "代码组织铁律" section. Out of scope for the artifacts but flagged for task list.

## Appendix A: opencli zhihu — deferred from v1 (exploration notes)

`opencli zhihu` was scoped in but cut after task 1.1 recon revealed it's **browser-driven** (uses opencli's Chrome bridge daemon on port 19825, not an HTTP API), making operational cost (Chrome session lifecycle, daemon health, launchd compatibility) disproportionate for v1. The framework remains multi-source from day one; adding `opencli_*` parsers later is a localized addition (one YAML entry + one parser function + one `PARSERS` registry line).

The recon below stays in design.md as the entry point for the follow-up change.

### Subcommand inventory

`opencli zhihu` ships 14 subcommands (`opencli zhihu --help -f yaml`). Read-only candidates for info-radar:

| subcommand | what it returns | needs login | suitable for radar |
|---|---|---|---|
| `hot` | global hot list (rank/title/heat/answers) | no | global trending signal |
| `recommend` | personalized homepage feed | **yes** | best personalized signal beyond RSS |
| `search <query>` | keyword search results (rank/title/type/author/votes/url) | no | possible per-keyword sources; noisy for author-tracking |
| `collection <id>` | one bookmark folder | yes | static — low signal |
| `question <id>` | answers for one question | yes | poll per-question — special-case |
| `answer-detail <id>` | full body of a single answer | yes | enrichment, not collection |

Write actions (`answer`, `comment`, `favorite`, `follow`, `like`) are out of scope for info-radar.

### Architectural implication: opencli is browser-driven

All zhihu subcommands declare `browser: true` and use the opencli Chrome bridge (`opencli doctor` shows a running daemon on port 19825 + a Chrome extension). This means:

- `paca doctor` must verify the opencli daemon is up, not just that the binary exists.
- launchd-triggered runs need the user's Chrome browser session to be live and the bridge daemon attached (operator's GUI environment must be available).
- Use `--site-session persistent` so login state survives across calls — empirically required for `recommend` (defaulting to `ephemeral` returned `[]`).
- Realistic per-call latency is **5–30s** (browser nav + render). `timeout_sec: 180` is a safe baseline for v1.

### `recommend` output schema (sampled)

```json
[
  {
    "rank": 1,
    "type": "answer",
    "title": "国际社会是怎样看待特朗普本次访华行程的？",
    "author": "太初月关",
    "votes": 10951,
    "url": "https://www.zhihu.com/question/2038010908488590805/answer/2038619999275840283"
  }
]
```

Fields available: `rank`, `type` (`answer` | `article`), `title`, `author`, `votes`, `url`.

Notably **missing**: `published_at`, `excerpt`, any timestamp. Parser maps to `RadarItem` as:

- `source_id` = last numeric segment of `url` (e.g., `2038619999275840283`). For `/answer/<aid>` use `aid`; for `zhuanlan.zhihu.com/p/<aid>` use `aid`. Strip `<em>` tags if present (seen in `search` output).
- `title` = trimmed title (strip `<em>`)
- `url` = upstream url verbatim
- `excerpt` = `None` (could enrich via `answer-detail` later — out of scope v1)
- `published_at` = `None` (no field upstream)
- `payload` = the raw record dict

### `hot` output schema (sampled)

```json
[
  {
    "rank": 1,
    "title": "稻城亚丁景区截断近 40 公里省道收费...",
    "heat": "614 万热度",
    "answers": 163,
    "url": "https://www.zhihu.com/question/2042270970505687095"
  }
]
```

Fields available: `rank`, `title`, `heat` (Chinese-formatted string, NOT numeric — e.g., `"614 万热度"`), `answers`, `url`.

Notably **missing**: `type` (all entries are questions), `author` (item is a question, not an answer), `votes` (use `answers` count instead), `published_at`, `excerpt`.

Parser maps to `RadarItem`:

- `source_id` = last numeric segment of `url` (the `question_id` from `/question/<qid>`)
- `title` = trimmed title (no `<em>` in `hot` output)
- `url` = upstream url verbatim
- `excerpt` = `None`
- `published_at` = `None`
- `payload` = the raw record dict (keeps `heat` string and `answers` count for downstream)

Dedup semantics: `(source, question_id)` means the same trending question won't be re-reported across pulls — correct behavior for "what's hot right now." It does NOT track new answers to a still-hot question (that would require `question <id>` polling, out of v1 scope).

`hot` works **without login** but still requires `--site-session persistent` (default `ephemeral` returned empty `[]` empirically).

### Shape divergence: separate parsers for `recommend` vs `hot`

| field | recommend / search | hot |
|---|---|---|
| `type` | `answer` \| `article` | absent (always question) |
| `author` | string | absent |
| `votes` | int | absent |
| `heat` | absent | string (`"NNN 万热度"`) |
| `answers` | absent | int |
| url pattern | `/answer/<aid>` or `/p/<aid>` | `/question/<qid>` |

Two parsers needed: `opencli_zhihu_recommend` (handles `recommend` and `search`, same shape) and `opencli_zhihu_hot` (separate). Each parser stays under 30 lines.

### Recommended first opencli source

```yaml
- name: opencli_zhihu_recommend
  enabled: true
  cli:
    argv_template: ["${OPENCLI_BIN_ARGV}", "zhihu", "recommend",
                    "--limit", "30", "--site-session", "persistent",
                    "-f", "json"]
    timeout_sec: 180
  parser: opencli_zhihu_recommend
```

Author-following ("track 石川") is **not** modeled through opencli — operator subscribes the RSSHub route (`zhihu/people/activities/<user_id>`) inside their Folo account, and the items flow through `folocli timeline` automatically.

## Appendix B: folocli timeline schema (captured in task 1.2)

### Auth

`folocli login` writes a token to `~/.folo/config.json`. For launchd use, operator can either preserve that file path (`HOME` must resolve correctly in the plist environment) or extract the token and set `FOLO_TOKEN` env var — `folocli` honors both, env var wins.

### Versioning gotcha

`npm view folocli versions` confirms the latest is `0.0.5` (still pre-1.0). `npx folocli` (no `--yes`) may resolve to a different cached version than `npx --yes folocli@latest` — observed `npx folocli timeline` returning `{"error": {"code": "UNKNOWN_ERROR", "message": "This operation was aborted"}}` while `npx --yes folocli@latest timeline` worked. Implication for source descriptors: **pin the version explicitly**, e.g., `["npx", "--yes", "folocli@0.0.5", ...]`. Operators bump via `FOLO_CLI_ARGV` env override when a new version ships.

### Response envelope

All folocli subcommands return:

```json
{
  "ok": true|false,
  "data": {...} | null,
  "error": null | {"code": "...", "message": "..."}
}
```

Parser MUST check `ok == true` and raise `RuntimeError` on `false`, surfacing `error.code` / `error.message`.

### `timeline` data shape

```json
{
  "ok": true,
  "data": {
    "entries": [ /* see entry shape below */ ],
    "nextCursor": "2026-05-25T11:00:00.353Z",
    "hasNext": true
  },
  "error": null
}
```

`nextCursor` is the timestamp of the oldest entry in the page; pass to `timeline --cursor <datetime>` for pagination. **v1 ignores cursor** (per D7).

### Entry shape (sampled)

```json
{
  "read": false,
  "view": 1,
  "aiScore": null,
  "from": ["feed"],
  "entries": {
    "id": "1127262502032277504",
    "title": "Anthropic co-founder Chris Olah was invited to speak at...",
    "url": "https://x.com/AnthropicAI/status/2058983299092009421",
    "description": "Anthropic co-founder Chris Olah was invited to speak at...",
    "guid": "https://twitter.com/AnthropicAI/status/2058983299092009421",
    "author": "Anthropic",
    "authorUrl": "https://x.com/AnthropicAI",
    "publishedAt": "2026-05-25T18:47:27.745Z",
    "insertedAt": "2026-05-25T19:17:57.339Z",
    "summary": "Anthropic co-founder Chris Olah was invited to speak at the presentation of...",
    "media": null,
    "categories": null,
    "language": null
  },
  "feeds": {
    "type": "feed",
    "id": "42034394558772224",
    "url": "rsshub://twitter/user/AnthropicAI",
    "title": "Twitter @Anthropic",
    "siteUrl": "https://x.com/AnthropicAI",
    "errorMessage": null,
    "errorAt": null
  },
  "subscriptions": {
    "category": "Recommended",
    "title": null
  }
}
```

Note the awkward double-nesting: each list element is `{read, view, ..., entries: {actual article}, feeds: {feed metadata}, ...}` — the inner singular `entries` is one article. We keep the shape verbatim in `payload` and extract our normalized fields from `entries.entries.*`.

`view` integer codes match the help: `0=articles, 1=social, 2=pictures, 3=videos, 4=audio, 5=notifications`.

### Parser mapping

| `RadarItem` field | source path | notes |
|---|---|---|
| `source_id` | `entries.entries.id` | stable folo-assigned snowflake ID |
| `title` | `entries.entries.title` | trim whitespace |
| `url` | `entries.entries.url` | upstream article URL |
| `excerpt` | `entries.entries.description` (fallback: `entries.entries.summary`) | description is upstream snippet; summary is folo's AI summary, only present sometimes |
| `published_at` | `parse_iso(entries.entries.publishedAt)` | ISO 8601 with millis |
| `payload` | the whole element verbatim (including `feeds.*` for provenance) | downstream can inspect `feeds.url` to know if item came via RSSHub vs direct RSS |

### v1 source entry

```yaml
- name: folo_timeline_articles
  enabled: true
  cli:
    argv: ["npx", "--yes", "folocli@0.0.5", "timeline",
           "--view", "articles", "--limit", "100"]
    timeout_sec: 60
  parser: folo_timeline
```

`--view articles` chosen for v1 because text-content-first matches the project bias (per user direction "专注在文字内容为主的平台"). Operator can add additional sources for social/videos by adding YAML entries with different `--view`. All share the single `folo_timeline` parser.

### Subscription discoverability (informational)

`folocli subscription list [--view <type>] [--category <name>]` returns the operator's subscriptions with feed metadata. Not used by the collector, but useful for `paca doctor` to report "N feeds subscribed in Folo" or to populate future dashboard pages.
