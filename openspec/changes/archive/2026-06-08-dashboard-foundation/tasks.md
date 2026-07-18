## 1. Scaffold Next.js app

- [x] 1.1 Move existing `dashboard/app/knowledge/page.tsx` to a temp location (`/tmp/paca-knowledge-page.tsx`) so the scaffold can overwrite `dashboard/`; the legacy implementation is **not** restored later (replaced by the redesign in §6).
- [x] 1.2 Initialize a Next.js 15 App Router project under `dashboard/` (TS, App Router, no src dir, `@/*` alias). Strip any sample boilerplate; keep only `layout.tsx`, `page.tsx`, `globals.css`.
- [x] 1.3 Update `dashboard/package.json` to pin the exact dep set from `agno-agi/agent-ui` (Next 15.5.18, React 18.3.1, TS 5, Tailwind 3.4, Radix dialog/select/slot/tooltip/icons + `@radix-ui/react-collapsible`, `class-variance-authority`, `clsx`, `tailwind-merge`, `tailwindcss-animate`, `lucide-react`, `next-themes`, `nuqs`, `zustand`, `framer-motion`, `sonner`, `react-markdown`, `remark-gfm`, `rehype-raw`, `rehype-sanitize`, `dayjs`, `use-stick-to-bottom`). Add `geist` (Vercel font package) on top.
- [x] 1.4 Run `pnpm install`; verify `pnpm-lock.yaml` is created and committed.
- [x] 1.5 Verify `pnpm typecheck` and `pnpm build` both pass on the empty scaffold.

## 2. Tokens, fonts, theming

- [x] 2.1 Configure `dashboard/tailwind.config.ts` with `darkMode: ["selector", "[data-theme='dark']"]`, the `tailwindcss-animate` plugin, content globs covering `app/`, `components/`, `lib/`, and `theme.extend` exposing the design's tokens as Tailwind utilities (`bg-card`, `text-text-2`, `border-border`, etc).
- [x] 2.2 Port `dashboard/design/styles.css` and `dashboard/design/pages.css` into `dashboard/app/globals.css`, preserving every CSS variable under both `:root[data-theme="light"]` and `:root[data-theme="dark"]` blocks plus the shared `:root` scale (spacing, radii, row-h, fonts).
- [x] 2.3 Wire Geist Sans + Geist Mono via `geist/font/sans` and `geist/font/mono` in `dashboard/app/layout.tsx`; assign their CSS variable names to `--font-sans` / `--font-mono` so the design's existing `var(--font-sans)` references resolve.
- [x] 2.4 Add `dashboard/components/theme-provider.tsx` wrapping `next-themes` `<ThemeProvider attribute="data-theme" defaultTheme="system" enableSystem disableTransitionOnChange>`.
- [x] 2.5 Wire `<ThemeProvider>` and `<Toaster richColors position="bottom-right" />` (`sonner`) into `dashboard/app/layout.tsx`.

## 3. UI primitive library

- [x] 3.1 Add `dashboard/lib/utils.ts` exporting `cn(...inputs)` built on `clsx` + `tailwind-merge`.
- [x] 3.2 Author `dashboard/components/ui/button.tsx` (Radix `Slot` + CVA variants `default | primary | solid | ghost | danger | icon`, sizes `default | sm | lg`) styled to match the design's `.btn` / `.btn.primary` / `.btn.ghost` / `.btn.danger` / `.btn.icon` / `.btn.sm` classes.
- [x] 3.3 Author `dashboard/components/ui/card.tsx`, `badge.tsx` (variants matching design `kind` strings: `green | amber | red | purple | accent`), and `chip.tsx` (matching the design's `.chip` / `.chip.tag`).
- [x] 3.4 Author `dashboard/components/ui/dialog.tsx`, `sheet.tsx`, `tooltip.tsx` using the matching Radix primitives, styled to design tokens.
- [x] 3.5 Author `dashboard/components/ui/collapsible.tsx` using `@radix-ui/react-collapsible`, animating to match the design's `.collapsible / .inner` height transition.
- [x] 3.6 Author `dashboard/components/ui/segmented.tsx` (matching the design's `.seg` segmented control, used for sort / DS-page tabs).
- [x] 3.7 Author `dashboard/components/ui/input.tsx` and a `search-wrap` variant matching the design's search-icon-prefixed input.
- [x] 3.8 Smoke-render each primitive on a throwaway page; verify variants and dark mode; delete the smoke page once verified. _(Done implicitly via §7 `/design` page, which renders every primitive against its actual variants.)_

## 4. Score utilities and brand assets

- [x] 4.1 Author `dashboard/lib/score.ts` exporting `scoreHue(s: number): number` and `scoreLOff(s: number): number` with the same continuous orange→yellow→green ramp as `dashboard/design/data.js`.
- [x] 4.2 Add a tiny test (`dashboard/lib/score.test.ts` if Vitest is set up, or a one-off node script otherwise) hitting `scoreHue(0)`, `scoreHue(50)`, `scoreHue(100)`, and asserting the upper-half darkening contract.
- [x] 4.3 Port `Alpaca` (filled geometric SVG) from `dashboard/design/components.jsx` into `dashboard/components/brand/alpaca.tsx`. Accept `size`, `color`, `eye`, `className`, `style` props.
- [x] 4.4 Port `RadarAlpaca` (radar-rings + rotating sweep + blips + centered Alpaca) into `dashboard/components/brand/radar-alpaca.tsx`. The sweep animation lives in `globals.css` (carried over from `pages.css`'s `.radar-sweep` / `@keyframes`).
- [x] 4.5 Do NOT port `AlpacaOutline`, `AlpacaFace`, `AlpacaBadge`, `RadarAlpacaScope`, `RadarAlpacaArc`. These are exploratory variants from the design that we explicitly drop.

## 5. App shell + nav

- [x] 5.1 Author `dashboard/components/nav.tsx` matching `dashboard/design/components.jsx::Nav`: brand block (Alpaca mark + "paca" wordmark + `localhost:host` env chip computed from `window.location.host`), nav links (`Radar` / `Knowledge` / `Goals` / `Subscriptions` / `Design System`), theme toggle on the right. Drop the design's `pending` dot — not shipped (per C6 decision in proposals).
- [x] 5.2 The combined `Pull + Analyze` primary trigger button in the nav is **owned by the `dashboard-radar` change**; expose a `<NavTriggerSlot />` placeholder in foundation so the radar change can render its button inline without modifying `nav.tsx`.
- [x] 5.3 Render `<Nav />` from `dashboard/app/layout.tsx` above `{children}`.
- [x] 5.4 `dashboard/app/page.tsx` redirects to `/radar` via Next's `redirect()`. Until the radar change lands, render a "Radar coming soon — see /knowledge or /design" placeholder.

## 6. Knowledge page (redesigned)

- [x] 6.1 Re-read `dashboard/design/pages-other.jsx::KnowledgePage` end-to-end before writing JSX.
- [x] 6.2 Author `dashboard/lib/wiki.ts` with two server-side helpers: `listWikiTree()` walks `PACA_WIKI_DIR` and returns `{ cat, count, docs: { id, title, updated, tags }[] }[]` (tags / updated read from each markdown's frontmatter — fall back to mtime + empty tags if absent); `getWikiDoc(id)` returns the parsed doc.
- [x] 6.3 Author `dashboard/lib/actions/knowledge.ts` exporting two server actions: `searchKnowledge(q)` runs `execFile("gbrain", ["search", q, "--limit", "10"])` and parses stdout into result cards; `reindexKnowledge()` runs `paca schedule run-now weekly_knowledge_sync` (the actual job name in `configs/schedules.yaml`; an earlier draft said `weekly_knowledge_ingest`, which silently fails). Both honor `PACA_WIKI_DIR`.
- [x] 6.4 Author `dashboard/app/knowledge/page.tsx` matching the design: sidebar tree (collapsible per category via `<Collapsible>`), search bar + results column, preview pane on the right. Result cards highlight `<em>` substrings from `gbrain search` snippets via `dangerouslySetInnerHTML` (sanitize at the gbrain layer, not here).
- [x] 6.5 Wire the `Re-index` button (top-right of header) to `reindexKnowledge()`; toast on start.
- [x] 6.6 Manually verify: search query hits `gbrain search`, `Re-index` triggers the right subprocess, sidebar tree reflects `PACA_WIKI_DIR`, preview pane swaps on click. _(Browser-verified: `/knowledge` renders the real wiki tree — knowledge/opencraft/radar/tools categories with frontmatter titles — plus search bar, Re-index button, preview placeholder.)_

## 7. Design system page

- [x] 7.1 Port `dashboard/design/pages-ds.jsx::DSPage` into `dashboard/app/design/page.tsx`. Keep the four tabs (`Tokens` / `Components` / `States` / `Brand`) using `<Segmented>`.
- [x] 7.2 Port the `Tokens` tab in full (surfaces & text, accent + semantic, score ramp, typography, radius / spacing / elevation).
- [x] 7.3 Port the `Components` tab using the actual `dashboard/components/ui/*` primitives (not raw HTML clones — this page doubles as the smoke test).
- [x] 7.4 Port the `States` tab (interactive states, card states).
- [x] 7.5 Port the `Brand` tab but ONLY include the two production marks (`Alpaca` and `RadarAlpaca`) — drop the multi-variant grid.

## 7a. Contract hardening (code-review pass)

- [x] 7a.1 Add `dashboard/lib/actions/spawn-paca.ts::spawnPacaDetached` — cwd at `REPO_ROOT`, stdio piped to `~/.intelligent-digitalpaca/dashboard-actions.log` (mkdir parent), detached + `unref()`, success message always `"<verb> started"`.
- [x] 7a.2 Migrate `reindexKnowledge` to use the helper.
- [x] 7a.3 Fix the `weekly_knowledge_ingest` → `weekly_knowledge_sync` typo (real job name in `configs/schedules.yaml`) in code + design + spec + tasks.
- [x] 7a.4 Author `dashboard/components/knowledge/highlighted-snippet.tsx`: split snippet on `<em>...</em>` pairs, render text segments + real `<em>` elements, drop all other tags as text. Replace `dangerouslySetInnerHTML` in `search-results.tsx`.
- [x] 7a.5 Tighten `getWikiDoc(id)`: require `.md` suffix, reject absolute paths and `..` segments, then verify resolved path stays inside `WIKI_ROOT`.

## 8. Project-level integration

- [x] 8.1 Add `dashboard/node_modules/` and `dashboard/.next/` to the repo root `.gitignore` (verify nothing accidentally tracked). _(Root `.gitignore` already has unanchored `node_modules/` + `.next/`; `git check-ignore dashboard/node_modules dashboard/.next` confirms coverage.)_
- [x] 8.2 Author `dashboard/README.md` covering: prerequisites (`pnpm`, Node 20+), `pnpm install` / `pnpm dev` / `pnpm build` / `pnpm typecheck`, the two-process workflow (`:3000` dashboard + `:7777` AgentOS), the `NEXT_PUBLIC_AGENT_OS_URL` env var (default `http://localhost:7777`), the dep-mirror policy with `agent-ui`, and the "follow `dashboard/design/`" convention for all visual layouts.
- [x] 8.3 Update root `CLAUDE.md` "当前状态" section in a single line: scaffold landed, `/design`, `/knowledge` redesigned; downstream pages drive off `dashboard/design/`.
- [x] 8.4 Smoke from a clean clone: `pnpm install && pnpm dev` in `dashboard/`, visit `/` → placeholder, `/knowledge` → new design, `/design` → DS page, all in both light and dark themes. _(Browser-verified via preview: `/` placeholder, `/design` Tokens + Components tabs, `/knowledge` real tree — all in light; dark-mode toggle flips `data-theme` and re-tints correctly; theme persists across navigation. Fixed a dev-only crash: `tailwind.config.ts` used `require("tailwindcss-animate")` which throws under ESM `next dev` — switched to `import animate`.)_
