## Why

`info-radar` collects items into `radar_items` and the analysis pipeline writes verdicts / summaries / scores into `radar_analyses`. Today the operator can only see this output by running `psql` and writing queries by hand. The dashboard needs a daily reader so the operator can: (1) browse what the pipeline kept and why, (2) jump from a high-signal article straight into the wiki via `paca knowledge ingest`, (3) trigger pulls and analyses without dropping to a terminal, and (4) get a quick post-hoc dashboard of how the pipeline performed today (pulled / dropped / kept / score distribution).

## What Changes

- Add a `/radar` page that reads `radar_items` ⋈ `radar_analyses` ⋈ `radar_pushed_topics` directly via `psycopg`-style queries (node-postgres) from server components, grouped by `analyzed_at::date`, with today's run on top and past days collapsed. Page hero shows the `RadarAlpaca` emblem (ported in `dashboard-foundation`) + title + kept-count subtitle.
- Add a tracker stats row above today's items: news-pulled-by-source (from `radar_items`), tier-1 kept / dropped, tier-2 ok / fallback / error, dedup novel / duplicate, and a score histogram in 10-wide buckets across 0..100 — all computed live from aggregate queries. No `finishedAt` / `durationSec` (no `job_runs` writer; not approximated either — explicitly omitted to match the simplified design).
- Add a `/radar` filter bar between the tracker and the item list: sort segmented control (`Score ↓` / `Score ↑` / `Newest`), `Novel only` toggle, and a `Score ≥ N` range slider (default 65). All filter state lives in URL query params via `nuqs` so the operator can share a filtered view.
- Add a `/radar/[id]` detail page rendering one `radar_analyses` row with summary, `impact_md` (markdown via `react-markdown`), tier-1 reason, content status, dedup status, tags, and the source `radar_items.excerpt` / link. Includes prev / next navigation through today's filtered list and an end-of-list "back to radar" affordance.
- Add an "Ingest to wiki" button on the detail page and an inline `Ingest` action on each radar card: server action wraps `uv run paca knowledge ingest <radar_items.url>`, with `sonner` toast feedback. The action re-reads `url` from DB by `radar_items.id` — never trusts a client-passed URL.
- Add a single combined `Pull + Analyze` primary button to the top nav (in the `<NavTriggerSlot />` reserved by foundation). Implementation = middle-path sequential / detached: the server action `await`s `paca info-radar pull` synchronously (typically <60s for folocli), then `spawn`s `paca info-radar analyze` detached, and returns one toast `"Pull complete · analyze started"`. While the action is in-flight, the button shows a `Pulling…` → `Analyzing…` (post-await) → `Pull + Analyze` (returned) progression — the post-await label flip is achieved by streaming a single phase update from the server action before returning.
- Score range across the entire radar surface is `0..100` (matches the backend `Tier2Analysis.score` pydantic schema, `ge=0, le=100`).
- All visual layouts SHALL follow the committed reference in `dashboard/design/` (specifically `dashboard/design/pages-radar.jsx`, plus shared components in `dashboard/design/components.jsx` and tokens in `dashboard/design/styles.css` / `pages.css`).

## Capabilities

### New Capabilities

- `dashboard-radar-reader`: the `/radar` index page (hero + tracker + filter bar + today's items + past-days), `/radar/[id]` detail page (with prev/next), the inline + detail `Ingest to wiki` server actions, and the combined `Pull + Analyze` trigger button.

### Modified Capabilities

None.

## Impact

- **Code (TS)**: new `dashboard/app/radar/page.tsx`, `dashboard/app/radar/[id]/page.tsx`, `dashboard/lib/db.ts` (node-postgres pool), `dashboard/lib/radar/queries.ts` (typed SQL helpers), `dashboard/lib/actions/radar.ts` (`runPullAndAnalyze`, `ingestToWiki`), `dashboard/components/radar/{today-tracker,item-card,score-histogram,day-group,filter-bar,detail-pager,trigger-button}.tsx`.
- **Dependencies**: add `pg` + `@types/pg` to `dashboard/package.json` for direct DB reads (first deps beyond the `agent-ui` mirror — already permitted by the foundation spec). `nuqs` is already in deps from foundation.
- **Python code**: no changes required. `Tier2Analysis.score` is already `ge=0, le=100`. If the `prompts/agents/info_radar_tier2.md` rubric needs tightening to use the full 0–100 range more deliberately, that's a separate prompt-tuning change.
- **DB schema**: none.
- **External services**: none.
- **Depends on**: `dashboard-foundation` must land first. This change relies on the app shell, theme, toast root, UI primitives (`Card`, `Button`, `Badge`, `Collapsible`, `Segmented`, `Tooltip`), the `RadarAlpaca` brand asset, the score color ramp in `lib/score.ts`, and `<NavTriggerSlot />`.
- **Future, separate changes (not in scope here)**: `dashboard-goals` (form CRUD for `configs/info_radar/goals.yaml`), `dashboard-folo-subs` (read-only `folocli subscription list`), `investment-analysis-workflow`.
