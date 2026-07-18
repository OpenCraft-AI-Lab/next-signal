## Context

`dashboard/` is currently a single Next.js server component (`app/knowledge/page.tsx`) with no `package.json`, no Tailwind, no shared layout, and no shared UI primitives. Every operator-facing feature in the pipeline (`info-radar` reader, goals CRUD, folo subscriptions, future investment workflow) needs the same chrome: a top nav, a theme toggle, a toast root, and a small library of shadcn-style primitives.

agno's `agent-ui` is the upstream reference for this stack (Next.js 15 + React 18 + Tailwind 3 + Radix + lucide). We are deliberately **not** vendoring it: we want our own pages, our own component code, and a self-contained `pnpm dev` workflow with no second app process. But we DO want the dependency set to match `agent-ui`'s exactly, so individual components from `agent-ui` can be copied file-by-file later (e.g. when `personal-assistant-router` needs a chat surface) without install drift.

Visual design will be supplied by the operator outside this proposal — HTML mocks land in `dashboard/design/` and downstream changes implement them.

## Goals / Non-Goals

**Goals:**

- Establish a real Next.js 15 app under `dashboard/` with the dep set above.
- Provide a global app shell (top nav, theme, toast root) that every downstream change can drop pages into without re-deciding layout.
- Self-author shadcn-style UI primitives in `dashboard/components/ui/` so component code is ours to evolve, no upstream tracking.
- Migrate `app/knowledge/page.tsx` into the shell with **zero behavior change** — same `execFile gbrain search`, same `Re-index` server action, same `PACA_WIKI_DIR` env var.
- Lock the convention that visual layouts come from operator-committed mocks under `dashboard/design/`.

**Non-Goals:**

- Page implementations for radar / goals / subscriptions / investment (separate downstream changes).
- Any FastAPI router on AgentOS for the dashboard's needs (server actions handle subprocess + DB).
- Vendoring `agent-ui` source.
- Chat surface, agent sidebar, or any operator-facing AgentOS proxy UI.
- Auth, multi-user, or mobile responsiveness — single local operator on a desktop browser.
- Editor for `dashboard/design/` mocks — operator hand-commits.

## Decisions

### D1: Dep set mirrors `agent-ui` exactly, primitives are Radix-backed, visual vocabulary comes from `dashboard/design/`

We pin every dependency that appears in `agno-agi/agent-ui`'s `package.json` (Next 15.5.18, React 18.3.1, TS 5, Tailwind 3.4, Radix dialog/select/slot/tooltip/icons + `react-collapsible`, class-variance-authority, clsx, tailwind-merge, tailwindcss-animate, lucide-react, next-themes, nuqs, zustand, framer-motion, sonner, react-markdown + remark-gfm + rehype-raw + rehype-sanitize, dayjs, use-stick-to-bottom). We do **not** copy any `agent-ui` source.

The committed design (`dashboard/design/`) ships its own visual vocabulary — Geist tokens, "shadow-as-border" elevation, a continuous score-color ramp, custom dialog / collapsible / segmented-control patterns. The design's reference JSX is hand-rolled HTML, **not** Radix-based.

We reconcile by: every primitive in `dashboard/components/ui/` is **Radix-backed under the hood** but **styled to match the design's tokens / motion / states**. That gets us both (a) the dep-mirror promise (any agent-ui component we port later drops in with zero install drift) and (b) the design's exact look.

**Why:** the user wants one dep surface for the long-term, but no upstream code to track. When we later need (say) `agent-ui`'s `MessageList` component for a chat page, we copy the file in and `pnpm install` is a no-op — versions already match. The same Radix primitive (`Collapsible`, `Tooltip`, `Dialog`) underpins both their components and ours.

**Alternatives considered:**
- *Vendor `agent-ui` whole* — was the old `dashboard-extensions` plan. Rejected: brings chat-shell weight we don't need, couples our look to their tree, makes upgrades harder.
- *shadcn CLI live-init* — would pin shadcn's preferred versions, not `agent-ui`'s. Rejected: causes drift the moment we want to port one of their components.

### D2: Server actions for trigger / subprocess work; no new FastAPI router

Workflow triggers (`Run pull`, `Run analyze`, `Ingest to wiki`, `Re-index knowledge`) are implemented as Next.js server actions that `execFile("uv", ["run", "paca", ...])`. AgentOS at `:7777` keeps doing what it does today; we do not add `/api/triggers/...` endpoints.

**Why:** mirrors the existing knowledge `Re-index` action; one fewer process layer; CORS-free; the operator's browser only talks to Next (`:3000`). Multi-client streaming progress is explicitly out of scope (operator said "事后" is fine).

**Alternatives considered:**
- *AgentOS FastAPI router* — better if multiple clients ever need to subscribe to the same job. We're single-operator so this is YAGNI.
- *Next.js Route Handlers* — fine, but server actions colocate the button and its handler, which is shorter and harder to drift.

**Trade-off:** server actions only survive while `next dev` (or the production `next start`) is up. Fire-and-forget subprocesses outlive the request just fine via `spawn` + `detached`, but losing the Next process before the subprocess finishes means the toast never fires. Acceptable — operator can re-check `radar_analyses` to confirm.

### D3: Operator-committed design mocks under `dashboard/design/`

Subsequent dashboard changes (`dashboard-radar`, `dashboard-goals`, `dashboard-folo-subs`) MUST implement against HTML/Figma-export mocks the operator commits under `dashboard/design/`. This proposal reserves the directory and documents the convention in `dashboard/README.md`. We do not specify layouts or visual rules here.

**Why:** the user is doing visual design out-of-band (via Claude design). Pinning the mocks in-repo makes them reviewable in PRs and prevents implementers from inventing alternate layouts.

**How downstream changes apply it:** their tasks.md will include a step like "Verify against `dashboard/design/radar.html` (provided by operator)." If the mock isn't there when tasks start, that's a blocker for the implementer, not a license to improvise.

### D4: Knowledge page is rewritten against the new design in this change

The existing knowledge page is fully replaced. The new layout (sidebar wiki tree + ANN search results + preview pane) is already specified in `dashboard/design/pages-other.jsx::KnowledgePage`. Behavior of the server actions (`Re-index` triggering `paca schedule run-now weekly_knowledge_sync`, `gbrain search` for query, `PACA_WIKI_DIR` listing for the tree) is preserved.

**Why (changed from earlier draft):** the operator committed full knowledge mocks alongside radar. Splitting the redesign into a separate change would mean shipping a stub that mismatches the rest of the dashboard. Doing it inside foundation keeps every page on the same visual vocabulary from day one.

**Trade-off:** foundation grows; rollback granularity for "just knowledge" disappears. Acceptable — the new page is bounded and reads from existing data sources.

### D5: pnpm, port 3000, env `NEXT_PUBLIC_AGENT_OS_URL`

`pnpm dev` runs the dashboard on `:3000` alongside `uv run paca serve` on `:7777`. The dashboard reads `NEXT_PUBLIC_AGENT_OS_URL` (default `http://localhost:7777`) — currently unused but pre-wired for future browser-side calls to AgentOS endpoints.

**Why:** matches `agent-ui`'s defaults; the operator's dev environment already lines up.

### D6: Geist Sans + Geist Mono via Vercel's `geist` package

The design uses Geist Sans (body / titles) and Geist Mono (ids / scores / tags / eyebrows / code-ish chrome) exclusively. We load both via `geist/font/sans` and `geist/font/mono` (Vercel's official Next-first package) — no Google Fonts request, no FOIT, no flash on theme toggle.

**Alternatives considered:**
- *Google Fonts via `next/font/google`* — extra network hop, no functional gain.
- *Letting system fonts (Inter / SF Pro) fall back* — visual parity with the mocks breaks immediately.

### D7: Theme attribute is `data-theme="dark|light"`, not the class-based default

The design's CSS targets `[data-theme="dark"]` and `[data-theme="light"]` selectors for every variable swap. We configure `<ThemeProvider attribute="data-theme">` instead of the default `attribute="class"`, and tell Tailwind `darkMode: ["selector", "[data-theme='dark']"]` so Tailwind utilities still see "dark" when the design's selector is active.

**Why:** ports the design's CSS as-is with zero rewrites; both `next-themes` and Tailwind 3 support this natively.

### D8: Brand assets ship as the production marks only

`dashboard/components/brand/alpaca.tsx` and `dashboard/components/brand/radar-alpaca.tsx` are direct ports of `Alpaca` and `RadarAlpaca` from `dashboard/design/components.jsx`. The design's exploratory variants — `AlpacaOutline`, `AlpacaFace`, `AlpacaBadge`, `RadarAlpacaScope`, `RadarAlpacaArc` — are **not** ported. The `/design` brand section reflects this by showing only the actually-shipped marks.

**Why:** ship the identity that the operator picked; leaving variants in the runtime bundle invites accidental usage and visual drift.

### D9: `/design` page is a permanent living style guide

We bundle a `/design` route (ported from `dashboard/design/pages-ds.jsx`) showing tokens / components / states / brand. Drops the multi-variant brand explorer per D8.

**Why:** keeps token definitions reviewable in the running app; future contributors have one place to see how `--accent-tint` looks rather than diffing CSS.

### D11: Server actions go through `spawnPacaDetached` — no ad-hoc spawn

Every dashboard server action that runs `uv run paca ...` SHALL go through `dashboard/lib/actions/spawn-paca.ts::spawnPacaDetached`. The helper centralizes: (a) cwd at `REPO_ROOT`, (b) detached + `unref()` so toasts fire immediately, (c) stdio piped to `~/.intelligent-digitalpaca/dashboard-actions.log` (tag-prefixed lines for `tail -f` debugging), (d) result message contract — always `"<verb> started"` on success, never `"completed"` (we don't await the subprocess, we can't honestly claim it finished).

**Why:** the foundation has one caller (`reindexKnowledge`); the radar change adds two (`runPullAndAnalyze`, `ingestToWiki`); future `dashboard-goals` / investment workflows will add more. Without a shared helper each caller re-invents cwd / env / stdio / log routing and the "started vs completed" semantics drift quickly.

**Trade-off:** the helper assumes `uv run paca` is the only subprocess shape — direct binary invocations (e.g. `gbrain search` from `searchKnowledge`) stay raw `execFile` because they're synchronous and small. If we ever need detached non-`paca` subprocesses we'll generalize then.

### D12: GBrain is NOT an HTML sanitization boundary

Search snippets from `gbrain search` carry `<em>...</em>` highlight markers around query matches plus arbitrary substring of the underlying wiki markdown body. Wiki markdown can legally contain raw HTML (CommonMark allows it). `gbrain` does no HTML escaping. The dashboard is the rendering sink and MUST be the sanitization boundary.

The dashboard ships `<HighlightedSnippet>` (`dashboard/components/knowledge/highlighted-snippet.tsx`) which splits the snippet on `<em>...</em>` pairs, renders each segment as React text (auto-escaped), and re-wraps the pair contents in real `<em>` elements. Any other tags in the input become inert text, never DOM.

`dangerouslySetInnerHTML` SHALL NOT appear in the search / preview path. If we later need richer formatting in snippets, we add `rehype-sanitize` (already in deps) — not a wider escape hatch.

### D13: `getWikiDoc(id)` restricted to `.md` files inside `WIKI_ROOT`

The `?doc=<id>` query param goes straight into `getWikiDoc`. To prevent the preview pane from rendering anything that happens to sit inside `WIKI_ROOT`, `getWikiDoc` enforces: (a) `id.endsWith(".md")`, (b) no absolute path, (c) no `..` path segments, (d) the resolved absolute path stays inside `WIKI_ROOT`. Returning `null` for any failure means the preview pane shows the empty state rather than leaking file content or path metadata.

Tighter alternative considered: only accept ids returned by `listWikiTree()`. Rejected for now — it'd require two filesystem walks per `/knowledge` request. Revisit if we ever store non-markdown secrets next to the wiki.

### D10: Score color ramp lives in `dashboard/lib/score.ts`

The design uses two pure functions — `scoreHue(s)` (orange → yellow → green, continuous) and `scoreLOff(s)` (darkens the upper half) — to color score chips, the histogram bars, the range slider thumb, and the design-system gradient stripe. Both functions land in `dashboard/lib/score.ts` and are imported wherever needed.

**Why:** single source of truth; trivially testable; keeps `data.js` mock-data concerns out of the production code path.

## Risks / Trade-offs

- **Risk: dep set drift over time.** `agent-ui` may bump Next or React; if we don't sync, the "drop a file in" promise breaks.
  → Mitigation: document the mirror policy in `dashboard/README.md`; treat any `agent-ui` upstream bump that we want to track as a small standalone change (`dashboard-deps-sync-YYYYMMDD`).

- **Risk: server-action subprocesses die if Next restarts.** Fire-and-forget toast can be lost.
  → Mitigation: state is in Postgres (`radar_analyses` / `radar_items`); operator can refresh to confirm. Long-running jobs are already designed to be idempotent via `radar_items.seen_at`.

- **Risk: implementer starts before operator's mocks land.** Empty `dashboard/design/` directory means downstream tasks are blocked.
  → Mitigation: downstream tasks.md will explicitly call out the mock path as a precondition. If a downstream change is created without a mock, the implementer pauses and asks rather than improvising.

- **Risk: `next dev` and AgentOS run on different ports during dev.** Operator has to remember to start both.
  → Mitigation: `dashboard/README.md` documents the two-process flow with a one-line `concurrently` hint as optional.

- **Risk: scope creep from "supersede `dashboard-extensions`".** Tempting to also delete that change here.
  → Mitigation: this proposal explicitly leaves `dashboard-extensions` in place; operator archives it separately when ready.
