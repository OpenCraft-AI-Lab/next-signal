## Context

`info-radar` ships items through two persistent tables: `radar_items` (raw input from collectors, ~30-day retention) and `radar_analyses` (one row per analyzed item, `UNIQUE(radar_item_id)`, `verdict` ∈ `drop`/`keep`, plus `summary` / `impact_md` / `score` / `tags` / `content_status` / `dedup_status` / `dedup_match_id`). `radar_pushed_topics` keeps long-term dedup memory with an embedding vector. The pipeline runs idempotently — re-analysis is safe — and `analyzed_at` is `NOT NULL DEFAULT now()`, which means `analyzed_at::date` is a stable per-run-day grouping key.

The operator wants to see this in the browser, daily. They also want to be able to fire the pipeline (combined `Pull + Analyze`) and ingest individual articles into the wiki without leaving the page. Visual design is committed under `dashboard/design/` — specifically `pages-radar.jsx` for `/radar` and `/radar/[id]`, plus shared components in `components.jsx` and tokens in `styles.css` / `pages.css`. Score range across the entire surface is `0..100`, matching `paca.workflows.info_radar_analysis.schemas.Tier2Analysis.score` (`ge=0, le=100`).

## Goals / Non-Goals

**Goals:**

- A `/radar` reader that surfaces the analysis output day-by-day, with today's run prominent and a `RadarAlpaca` emblem in the hero.
- A small "today's run" tracker showing how the pipeline did — pulled-by-source, tier-1 / tier-2 / dedup counts, and a 0..100 score histogram (10-wide buckets) — so the operator can spot regressions at a glance.
- A filter bar (sort / Novel-only / Score≥N) whose state lives in URL query params via `nuqs`.
- A `/radar/[id]` detail view rendering full `impact_md` markdown, exposing one-click wiki ingestion, with prev / next pagination through today's filtered list.
- One combined `Pull + Analyze` button in the top nav: sequential await pull → detached analyze → single toast.
- Zero schema churn, zero new write path, no `job_runs` dependency.

**Non-Goals:**

- Real-time mid-run progress (operator explicitly said post-hoc is fine).
- Editing `radar_analyses` rows (no manual override of verdict / score / tags).
- Surfacing `analyze` failures in the UI (analyze is detached; failures land in stderr / logs).
- `run finished` / `duration` metadata on the tracker (see D9).
- "New since last visit" nav indicator (the design's `pending` dot was dropped per the C6 decision in proposals).
- Any visual layout decisions outside what `dashboard/design/` already shows.
- Operator authentication (single local user).
- Bulk-ingest action across multiple items (out of scope; one-by-one for now).

## Decisions

### D1: Group by `analyzed_at::date`, no `run_id` column

The explore conversation considered three options for "batch":
- (A) one `paca info-radar analyze` invocation = one batch → add `run_id` to `radar_analyses`, write it from the runner.
- (B) `_BATCH_SIZE=10` tier-1 chunk = one batch → also a schema change, and visually meaningless.
- (C) one calendar day = one group → no schema, no writer.

We pick (C). It costs nothing, it matches the operator's mental model ("show me today's signal"), and it's robust against the runner being invoked multiple times a day (the page shows the union, correctly). A future change can add `run_id` if "compare today's two runs side-by-side" ever becomes a need.

### D2: Post-hoc aggregation, no `job_runs` writer

The tracker stats row is computed live from aggregate queries over `radar_items` (`fetched_at::date = ?`, `GROUP BY source`) and `radar_analyses` (`analyzed_at::date = ?`, `GROUP BY verdict / content_status / dedup_status`, plus a score histogram). No new table, no `job_runs` row inserted by the runner, no scheduler dependency. If the operator later wants run-level metadata (start time, wall-clock, errors), that's a `launchd-scheduler`-shaped change — out of scope here.

Trade-off: we can't show *durations* or *errors that didn't produce rows*. Acceptable — the operator wanted a reader, not an ops console.

### D3: DB reads via `pg` package in server components, no FastAPI

Server components do `import { query } from "@/lib/db"` and run raw SQL through node-postgres. We don't proxy through AgentOS because:
- AgentOS is the agent runtime, not a generic data API.
- A direct connection from Next-server-side is two hops shorter and avoids a CORS / serialization layer.
- The connection string comes from the same `DATABASE_URL` env var the Python side uses.

We add `pg` + `@types/pg` — the first packages beyond the `agent-ui` mirror. Documented as such in `dashboard/README.md`.

**Alternatives considered:**
- *Mount FastAPI routers on AgentOS* — fits the old `dashboard-extensions` posture but the operator already vetoed it during exploration. Postponed until a multi-client streaming need appears.
- *Run all queries through `uv run paca` CLI subprocess* — too slow for a page that does ~6 aggregate queries on every load.

### D4: Single combined `Pull + Analyze` button via middle-path sequential / detached

The design wraps both pipeline phases in one primary button on the nav. We implement it as a single server action that:

1. Synchronously `await execFile("uv", ["run", "paca", "info-radar", "pull"])` — folocli + GitHub sources typically finish in <60s; the request keeps the connection open and the button reads `Pulling…`.
2. As soon as pull completes, `spawn("uv", ["run", "paca", "info-radar", "analyze"], { detached: true, stdio: "ignore" }).unref()` — `analyze` runs minutes; we do NOT block on it.
3. Return `{ phase: "analyzing", message: "Pull complete · analyze started" }`. The button flips to `Analyzing…` for ~6s (a client-side timer) then back to default; the toast shows the returned message.

`Ingest to wiki` stays simple fire-and-forget: spawn detached, immediate toast.

**Why this shape:** the design wants one button and a sense of forward progress, not two unrelated triggers. Awaiting only the fast phase gives us real success/failure signal for the part where errors are most likely (auth, network), while keeping the long phase non-blocking. The phase-flip UX is approximated client-side; we can't push a second server-rendered toast mid-action.

**Trade-offs accepted:**
- We can't surface "analyze failed mid-run" — analyze is detached. Acceptable: operator confirms by refreshing `/radar`; the tracker counts reflect reality.
- The button reads `Analyzing…` for a fixed window, not actually tracking progress. Honest enough — the toast says "analyze started", not "analyze done".

**Alternatives considered:**
- *Await both phases synchronously* — request hangs for minutes; the operator's tab will look broken.
- *Detach both phases* — pull errors (folocli auth dead, npx network failure) become invisible.
- *Two separate buttons* (earlier draft) — design rejected this; operator confirmed combined UX is the target.

### D5: `impact_md` renders via `react-markdown` with sanitizer

`radar_analyses.impact_md` is LLM-produced markdown. We render it with `react-markdown` + `remark-gfm` + `rehype-raw` + `rehype-sanitize` (already in deps from `dashboard-foundation`). The sanitizer protects against accidental script tags in pasted source content.

### D6: Score histogram = 11 buckets across 0..100, custom bars

The score is `INTEGER` with backend contract `0..100` (verified against `Tier2Analysis.score` pydantic `ge=0, le=100`). The histogram is 11 inline divs (buckets `[0,9]`, `[10,19]`, …, `[90,99]`, `[100]`), height-proportional within a fixed 56px slot, colored via `scoreHue / scoreLOff` from `lib/score.ts` so the bars share their hue with the corresponding `ScoreChip`. No `recharts` / `d3` dependency. SQL: `COUNT(*) ... GROUP BY LEAST(FLOOR(score / 10), 10)`.

### D7: Design-mocks-driven implementation

This change DOES NOT specify card layouts, badge positions, or empty-state copy. Implementation tasks reference `dashboard/design/pages-radar.jsx` (RadarPage + RadarDetail), `dashboard/design/components.jsx` (shared primitives: ScoreChip / Badges / RadarAlpaca / StatPill / Icon), and the tokens in `dashboard/design/styles.css` + `pages.css`. The conformance check is: "Does the rendered page look like the mock?" — both light and dark mode, on a 1440-wide desktop viewport.

### D8: Detail page resolves by `radar_items.id` (not `radar_analyses.id`)

The URL is `/radar/[id]` where `id` is the `radar_items` PK. We then `LEFT JOIN radar_analyses ON radar_analyses.radar_item_id = radar_items.id`. Reasoning: the URL is shareable / debuggable — operator can paste a `radar_items.id` from `psql` and land on the page even if analysis hasn't run yet (page renders the raw item + a "not yet analyzed" state).

### D9: Tracker explicitly omits `finishedAt` and `durationSec`

The committed design earlier showed "run finished 06:42 PDT · 184s" in the tracker. We drop both fields entirely (no proxy via `MAX(analyzed_at)`, no `MAX − MIN` duration). Reasoning:

- No `job_runs` writer exists (decided in foundation exploration); we keep that decision intact.
- `MAX(analyzed_at)` is misleading when re-runs hit the same day (last analyzed item != run end).
- `MAX − MIN` includes idle gaps between runs and reads like a lie when the operator runs `analyze` twice in a day.

The tracker header instead shows just the date plus the source chips — implementer drops the `run finished … · …s` row from `dashboard/design/pages-radar.jsx::RunTracker` when porting.

### D10: Filter bar state via `nuqs` (URL query params)

The filter bar (`sort`, `novelOnly`, `minScore`) lives in URL query params via `nuqs` (already in deps from foundation). This makes a filtered view shareable / refreshable and survives the page navigation to `/radar/[id]` and back. Defaults: `sort=score-desc`, `novelOnly=false`, `minScore=65` (matching the design).

### D11: Detail prev / next paginates within the current filtered list

`/radar/[id]` accepts the same filter query params as `/radar` (forwarded by `<SignalCard>` on click). Server-side, it computes today's filtered list (same SQL as `/radar`), finds the current item's index, and exposes `prev` / `next` ids in the rendered component. The end-of-list shows a `nextcard-end` "back to radar" affordance.

### D12: `RadarAlpaca` emblem in `/radar` hero

The `/radar` page hero renders `<RadarAlpaca size={72} />` (ported in `dashboard-foundation`, `dashboard/components/brand/radar-alpaca.tsx`) next to the page title. The sweep CSS animation lives in `globals.css` (also from foundation). No new brand work in this change — pure usage.

## Risks / Trade-offs

- **Risk: `pg` driver vs `psycopg` connection-string differences.** Python uses `postgresql+psycopg://`; Node expects `postgresql://`.
  → Mitigation: `dashboard/lib/db.ts` strips the `+psycopg` driver tag if present and reads `DATABASE_URL` (or `PACA_DATABASE_URL` if the operator wants a separate read-only URL).

- **Risk: long-running `analyze` outlives `next dev`.** Since the combined action returns after `pull` completes and analyze is detached, the "Pull complete · analyze started" toast still fires. But if the dev server restarts mid-analyze, the operator has no in-app signal that it finished.
  → Mitigation: state is in Postgres; refreshing `/radar` shows updated rows. Documented in `dashboard/README.md`.

- **Risk: `pull` errors don't surface as gracefully as we want.** If `paca info-radar pull` exits non-zero, the awaited `execFile` rejects and the action returns an error — the button stays disabled until the request completes; the toast says "Pull failed".
  → Mitigation: this is the desired behavior. Most failures are auth (folocli token expired) or network — both should be loud.

- **Risk: phase-flip button label (`Pulling…` → `Analyzing…` → default) lies.** The `Analyzing…` window is a client-side timer, not real progress.
  → Mitigation: timer is short (~6s); toast text says "analyze started" not "analyze done"; tracker counts are the source of truth on refresh.

- **Risk: aggregate queries get slow as `radar_items` grows past 30 days.**
  → Mitigation: existing 30-day sweep keeps `radar_items` bounded; existing indexes on `fetched_at` and `(fetched_at) WHERE seen_at IS NULL` cover the today queries; if we ever drop the sweep, revisit.

- **Risk: `Ingest to wiki` action exposes URL-as-CLI-arg subprocess invocation.** A maliciously crafted URL in `radar_items.url` could in principle be a command-injection vector.
  → Mitigation: `execFile` with `args: [...]` (not `exec` with a string) — Node passes args directly to the child without shell interpretation. We validate `url` is a valid `URL` object before passing.

- **Risk: implementer starts §3 / §4 without the design mock.**
  → Mitigation: explicit "blocker check" at the top of each design-bound task; `dashboard/design/README.md` (from `dashboard-foundation`) tells implementers what to do.

- **Risk: scope creep — operator says "I also want to edit the verdict / bulk-ingest / search radar history".**
  → Mitigation: list those explicitly as Non-Goals; reject inside this change, open a separate proposal.
