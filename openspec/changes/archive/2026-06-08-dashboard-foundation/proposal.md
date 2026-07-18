## Why

`dashboard/` currently holds a single Next-style server component (`app/knowledge/page.tsx`) with no `package.json`, no Tailwind, no shared layout, and no component primitives — it works only because the file happens to be picked up by stock Next defaults. Every new dashboard page (radar reader, goals editor, folo subscriptions, future investment workflow) needs the same shell, the same UI primitives, and the same theme/toast plumbing. We need a real Next.js app underneath before we add anything else, and we want its dependency surface to be a strict superset of agno's `agent-ui` so individual components from `agent-ui` can be ported file-by-file later with zero install drift.

## What Changes

- Scaffold `dashboard/` as a Next.js 15.5.18 App Router project with TypeScript 5, React 18, and pnpm.
- Pin the dependency set to mirror `agno-agi/agent-ui` exactly: Tailwind 3 + tailwindcss-animate + tailwind-merge + class-variance-authority, Radix UI primitives (dialog/select/slot/tooltip/icons), lucide-react, next-themes, nuqs, zustand, framer-motion, sonner, react-markdown + remark-gfm + rehype-raw + rehype-sanitize, dayjs. Self-author shadcn-style primitives under `dashboard/components/ui/` — do NOT vendor agent-ui source.
- Add a global app shell: top nav (`Radar` / `Knowledge` / `Goals` / `Subscriptions` / `Design System`), `next-themes` theme toggle wired to `data-theme` attribute, `sonner` `<Toaster />` root, Tailwind config, Geist Sans + Geist Mono via Vercel's `geist` package, and `lib/utils.ts` (`cn()`).
- Port brand assets from `dashboard/design/` as-is into `dashboard/components/brand/`: `Alpaca` (filled geometric SVG) and `RadarAlpaca` (animated radar-sweep emblem used as the `/radar` hero). Only the production variants — the design's exploratory mark variants (`AlpacaOutline` / `AlpacaFace` / `AlpacaBadge`, `RadarAlpacaScope` / `RadarAlpacaArc`) are NOT ported.
- Port the design's CSS-variable token system (`styles.css` / `pages.css`) into `dashboard/app/globals.css`, wired through Tailwind's theme to make tokens consumable as utilities.
- Port the design's continuous score-color ramp (`scoreHue(s)` / `scoreLOff(s)`, 0–100) into `dashboard/lib/score.ts` so radar pages and the design-system page share one source of truth.
- Add `/design` page (living style guide: tokens / components / states / brand), ported from `dashboard/design/pages-ds.jsx` minus the multi-variant brand explorer (since we only ship the production marks).
- Re-implement `app/knowledge/page.tsx` to match the new design (`dashboard/design/` mocks): sidebar wiki tree, ANN search with result cards + snippet highlights, and a preview pane. Server-side data fetches (`gbrain search`, `PACA_WIKI_DIR` listing, `Re-index` action) keep their behavior — the wrapper changes, the actions don't.
- Add `dashboard/README.md` documenting `pnpm dev` / `pnpm build`, the `NEXT_PUBLIC_AGENT_OS_URL` env var (default `http://localhost:7777`), and the convention that visual implementation follows mocks committed by the operator under `dashboard/design/`.
- Reserve `dashboard/design/` as the contract location for HTML/Figma export mocks. Implementations of subsequent dashboard changes (`dashboard-radar`, future `dashboard-goals`, `dashboard-folo-subs`) MUST follow those mocks rather than invent visual layouts.
- This change replaces the older `dashboard-extensions` change (which proposed vendoring agent-ui + a different admin-page set). That change had no started tasks and was deleted from `openspec/changes/` when this proposal landed.

## Capabilities

### New Capabilities

- `dashboard-shell`: the Next.js app skeleton, dependency contract, global nav/theme/toast shell, the `dashboard/design/` mock convention, and the migration target for `app/knowledge/page.tsx`.

### Modified Capabilities

None.

## Impact

- **Code**: new `dashboard/package.json`, `dashboard/pnpm-lock.yaml`, `dashboard/next.config.ts`, `dashboard/tsconfig.json`, `dashboard/tailwind.config.ts`, `dashboard/postcss.config.mjs`, `dashboard/app/globals.css`, `dashboard/app/layout.tsx`, `dashboard/app/page.tsx` (landing / radar redirect), `dashboard/app/design/page.tsx`, `dashboard/components/ui/*` (Radix-backed primitives styled to design tokens), `dashboard/components/brand/{alpaca,radar-alpaca}.tsx`, `dashboard/components/nav.tsx`, `dashboard/components/theme-provider.tsx`, `dashboard/lib/utils.ts`, `dashboard/lib/score.ts`, `dashboard/README.md`. Rewrite `dashboard/app/knowledge/page.tsx` against the new design.
- **Dependencies**: pnpm + the dep set above. No new Python dependencies.
- **External services**: none.
- **Infra**: dev workflow becomes `pnpm dev` in `dashboard/` (port 3000) alongside `uv run paca serve` (port 7777). Document both in `dashboard/README.md`.
- **Out of scope**: visual design (operator-supplied), the `/radar` `/goals` `/subscriptions` pages themselves (separate downstream changes), any FastAPI router on AgentOS, any change to Python code outside the dashboard.
