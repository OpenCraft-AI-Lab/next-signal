# Module: dashboard (operator console)

> **English** · [中文](../zh/modules/dashboard.md)

## What it solves

A single-user, desktop-only local console: read info-radar output, manage the
knowledge base, edit goals, and inventory Folo subscriptions. It is a separate
Next.js 15 process (`:3000`) that **does not depend on `paca serve`** — every
feature either reads Postgres directly or spawns a one-shot `paca` CLI child.

> The complete account of how to run it, its env vars, the design system, i18n,
> the dependency policy, and radar/goals/subscriptions page behavior lives in
> [`dashboard/README.md`](../../dashboard/README.md) — that is the dashboard's own
> primary doc. This page covers only the overview and cross-module conventions.

## Page families

| Route | Function | Detailed behavior |
|---|---|---|
| `/radar` | info-radar reader: today's tracker, filtering and sorting, Pull + Analyze (with live progress), range Recap panel, per-item Ingest to wiki | [info_filter.md](./info_filter.md), dashboard/README |
| `/knowledge` | wiki tree + file management, ANN search, preview, Re-index, URL ingest form + live progress panel | [knowledge.md](./knowledge.md) |
| `/goals` | edits `configs/info_radar/goals.yaml` (mirrors the Python loader contract, atomic write) | dashboard/README |
| `/subscriptions` | read-only Folo subscription inventory | dashboard/README |

## Code structure

```
dashboard/
  app/            pages (App Router; data pages are force-dynamic) + 4 routes under app/api/
                  (knowledge ingest SSE stream / radar run polling / radar recap polling /
                   radar export)
  app/design/     the living design-system reference — every token, primitive, and
                  brand mark; its nav entry renders in dev builds only (see below)
  components/     grouped by page family, plus components/ui/ (Radix-backed primitives)
  lib/            db.ts (direct pg), actions/ (server actions), ingest/jobs.ts
                  (in-memory job registry), radar/ wiki.ts taxonomy.ts i18n/
```

## Cross-module conventions

- **Three server-action modes** (`lib/actions/`): long tasks (analyze) spawn
  detached and the page converges by polling (`/api/radar/run`); short tasks
  (gbrain search, `info-radar pull`) use `execFile` and await synchronously; and
  saving goals spawns nothing at all — it is in-process fs I/O inside the server
  action (`lib/goals.ts`).
- **Ingest progress is single-process in-memory state**: both ingest entrypoints
  (the `/knowledge` form and `/radar` Ingest) share the job registry in
  `lib/ingest/jobs.ts`, which spawns `paca knowledge ingest --progress` and pushes
  over SSE to the panel. Restarting the dashboard loses the **progress view** of
  in-flight jobs (the child process and artifact writes are unaffected);
  `/radar`'s analyze progress is best-effort in the same way
  (`radar-state.json`).
- **Data language is never translated**: i18n covers interface copy only
  (`paca_locale` cookie, defaults to English). Article titles, analysis
  summaries, tags, and YAML values render as stored.
- **Config writes are atomic and mirror the loader contract**: both `/goals` and
  `/knowledge`'s taxonomy edits validate against the Python loader's schema
  first, then land via a temp-file rename. `/knowledge`'s taxonomy uses a
  text-line splice so comments and alignment survive; `/goals` reserializes the
  whole file with `YAML.stringify`.

## Development notes (invariants)

- **Never start a second `next dev`** — it shares `.next` with the dev server
  already running, and two processes writing that cache corrupts the build
  manifest (the classic symptom is
  `Cannot read properties of undefined (reading 'call')`). Stop the server once
  you have verified; after a large change, `rm -rf dashboard/.next` to clear the
  bloated incremental cache.
- New features go in new pages and components, reusing design-system primitives
  and tokens — never bend the app shell for a single page.
- **`/design` is the living design-system reference**: its nav entry renders only
  when `NODE_ENV === "development"` (`components/nav.tsx`), so a deployed
  dashboard never shows it. The route itself is not blocked — `/design` resolves
  in any build if you navigate to it directly. When you add a token or a UI
  primitive, add it to that page in the same change: it is how the next agent
  discovers what already exists instead of inventing a parallel button.
- `/knowledge`'s re-index uses POST, not a GET query.
- Paths parsed inside a server action must pass traversal validation (see the
  precedent in `lib/actions/knowledge.ts`).

## Specs and status

Specs: [`openspec/specs/dashboard-shell/`](../../openspec/specs/dashboard-shell/),
`dashboard-radar-reader`, `dashboard-knowledge-ingest`, `dashboard-goals`,
`dashboard-folo-subscriptions`.

Current status: all four page families are in place. `pnpm test` runs the focused
`lib/` tests (wiki / taxonomy / goals / radar-ingest), and `pnpm typecheck` is
green.
