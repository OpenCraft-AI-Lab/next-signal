# paca dashboard

> **English** · [简体中文](./README.zh-CN.md)

Local Next.js 15 app — the operator's view into `radar`, `knowledge`, goals,
and Folo subscriptions. Single-user, desktop-only —
no auth, no mobile. Cross-module conventions live in
[docs/modules/dashboard.md](../docs/modules/dashboard.md).

## Prerequisites

- Node 20+
- pnpm (install via `npm install -g pnpm` if missing — pnpm 11+ recommended)
- `uv` on `PATH` (used by server actions to invoke `paca ...`)
- `gbrain` on `PATH` (used by the knowledge search server action)
- `npx` / Folo auth for `/subscriptions` (`FOLO_TOKEN` or `~/.folo/config.json`)

## Run

The recommended entrypoint goes through the `paca` CLI so both backends share
one binary:

```bash
uv run paca dashboard             # http://localhost:3000, HMR
uv run paca dashboard --port 3001 # custom port
uv run paca dashboard --build     # `pnpm build`
uv run paca dashboard --start     # `pnpm start` (requires prior --build)
```

It's a thin wrapper over `pnpm`: `os.execvp` replaces the python process so
Ctrl-C / SIGTERM hit Next directly with no middleman. Native pnpm
commands still work:

```bash
cd dashboard
pnpm install
pnpm dev          # http://localhost:3000, HMR
pnpm build
pnpm test         # focused dashboard helper tests
pnpm typecheck
```

## The dashboard does NOT depend on `paca serve`

`paca serve` (AgentOS at `:7777`) and `paca dashboard` (Next at `:3000`) are
**fully decoupled processes**. Every dashboard feature today either reads
Postgres directly or spawns a one-shot `paca` CLI child — none make HTTP calls
to AgentOS.

| Doing this | Need `paca serve`? |
| --- | --- |
| Browsing `/radar`, clicking Ingest / Pull+Analyze | ❌ no |
| Searching `/knowledge`, clicking Re-index | ❌ no |
| Running workflows manually (`paca info-radar pull/analyze`, `paca run-workflow knowledge_ingest`) | ❌ no (CLI child, writes Postgres directly) |
| Debugging new agents / workflows | ✅ yes (or use `paca run-agent`) |

`NEXT_PUBLIC_AGENT_OS_URL` is pre-wired (default `http://localhost:7777`) for
the day a page actually needs to call AgentOS HTTP endpoints — none do yet.

## Environment variables

| Name | Default | Used by |
| --- | --- | --- |
| `PACA_WIKI_DIR` | (none — required) | `/knowledge` (tree + re-index) |
| `NEXT_PUBLIC_AGENT_OS_URL` | `http://localhost:7777` | Browser-side AgentOS calls (none yet) |
| `DATABASE_URL` | (Postgres URL) | `dashboard-radar` (direct DB reads) |
| `PACA_DATABASE_URL` | `DATABASE_URL` | Optional dashboard-specific Postgres URL |
| `INFO_RADAR_TIMEZONE` | `America/Los_Angeles` | Calendar-day grouping and recap ranges for `/radar` |
| `FOLO_TOKEN` | (Folo CLI session file) | `/subscriptions` via `paca info-radar subscriptions --json` |
| `FOLO_CLI_ARGV` | `npx --yes folocli@0.0.5` | Optional override for the Folo CLI launcher |

## Visual design system

The design system's source of truth is the in-app [`/design`](./app/design)
showcase route — tokens, components, states, and brand marks, rendered from
the real primitives. Tokens live in [`app/globals.css`](./app/globals.css);
components under [`components/ui/`](./components/ui/).

**The nav link to `/design` renders only when `NODE_ENV === "development"`** (see
[`components/nav.tsx`](./components/nav.tsx)), so it stays out of a deployed
dashboard. The route itself is not blocked — `/design` still resolves in any
build if you navigate to it directly, which is the escape hatch for inspecting a
production build.

### Consuming a design mock

New pages usually start from a Claude Design mock (an HTML/JSX prototype).
Treat mocks as **transient, external scaffolding** — they stay in the Claude
Design workspace and are never committed to this repo. To implement one:

1. Build the page under `app/` and `components/`, reusing the existing tokens
   (`app/globals.css`) and `components/ui/` primitives — don't invent new
   colors, spacing, or one-off styling.
2. If the mock genuinely needs a token or primitive that doesn't exist yet,
   add it to `app/globals.css` / `components/ui/` and surface it in `/design`
   so the showcase stays complete.
3. Verify against `/design` in both light and dark themes.

Once the page ships, the mock has done its job and is discarded. The shipped
page plus `/design` are the durable reference from then on — specs and docs
point at those, never at a mock file.

## UI language

Dashboard UI chrome defaults to **English** and can be switched to Chinese from
the nav language button. The selected locale is stored in the `paca_locale`
cookie (`en` / `zh`), and `app/layout.tsx` sets the matching document `lang`.

Translations live in [`lib/i18n/dictionaries.ts`](./lib/i18n/dictionaries.ts).
Only interface copy is localized: labels, buttons, empty states, toasts,
relative time, and date display. User/data content such as article titles,
analysis summaries, tags, YAML values, wiki document bodies, and feed/category
names is rendered as stored.

## Dependency policy: mirror `agent-ui`, then add

`package.json`'s dependency set is a strict **superset** of
[`agno-agi/agent-ui`](https://github.com/agno-agi/agent-ui)'s. Every package in
their `dependencies` / `devDependencies` is pinned here at the same or wider
range. Whenever a component from `agent-ui` is useful (e.g. a chat surface),
copying a single source file into `components/` should be a `pnpm install`
no-op.

Packages added on top of the mirror (and why):

- `geist` — official Vercel font package; the design uses Geist Sans + Mono.
- `gray-matter` — parse frontmatter for the knowledge sidebar tree.
- `pg` / `@types/pg` — direct Postgres reads from server components for the
  radar reader, beyond the `agent-ui` mirror.
- `yaml` — parse and render `configs/info_radar/goals.yaml` for `/goals`.
- `tsx` — focused TypeScript helper tests.

## Radar

`/radar` is the local reader for `info-radar` output. It reads
`radar_items`, `radar_analyses`, and `radar_pushed_topics` directly from
Postgres in server components, groups kept analyses by local calendar day, and
shows today's tracker above the reading list.

The tracker is computed live: `radar_items.fetched_at` gives pulled-by-source,
`radar_analyses.verdict` gives tier-1 kept/dropped, `content_status` gives
tier-2 ok/fallback/error, `dedup_status` gives novel/duplicate, and scores are
bucketed into eleven `0..100` histogram bars. It intentionally does not show
run duration or finish time because no run-level writer exists.

Filter state is URL-backed via `nuqs`: `sort=score-desc|score-asc|newest`,
`novelOnly=0|1`, `minScore=0..100` in steps of 5, `day=YYYY-MM-DD`, and
`lastFeedOnly=0|1`. Detail links preserve those params so prev/next stays
inside the same filtered, day-scoped list.

`Pull + Analyze` awaits `uv run paca info-radar pull`, then starts
`uv run paca info-radar analyze` detached. Pull failures surface in the toast;
analyze failures land in the dashboard action log and the source of truth is the
Postgres state after refresh. The dashboard also writes
`~/.next-signal/radar-state.json` so zero-result clicks and
`Last feed` views reflect the operator's most recent click rather than stale DB
clusters. Per-item `Ingest` creates a tracked knowledge ingest job after
re-reading the item by id; Folo rows are staged as full-text HTML first, while
non-Folo rows use the validated `radar_items.url`.

## Goals

`/goals` edits `configs/info_radar/goals.yaml` directly through server actions.
The dashboard mirrors the Python loader contract: top-level non-empty `goals`,
unique read-only goal names, required description, string-list topics/keywords,
numeric weight, and no unknown fields. Invalid saves are rejected before writing;
valid saves use an atomic temp-file rename.

Existing goal names are read-only. Rename is intentionally modeled as delete +
add so downstream analysis history is never silently retargeted.

## Subscriptions

`/subscriptions` is read-only. It calls
`uv run paca info-radar subscriptions --json`, normalizes the Folo CLI envelope
into dashboard rows, then filters search/category client-side. The page never
adds, edits, deletes, or otherwise mutates Folo subscriptions.

## Build-script approval

pnpm 11 requires explicit approval for packages that run install scripts.
`esbuild`, `sharp` (Next.js image optimization), and `unrs-resolver` (Next.js
internals) are whitelisted in [`pnpm-workspace.yaml`](./pnpm-workspace.yaml).
