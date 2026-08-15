# next-signal dashboard

> **English** · [简体中文](./README.zh-CN.md)

Local Next.js 15 app — the operator's view into `radar`, `knowledge`, goals,
and Folo subscriptions. Single-user, desktop-only —
no auth, no mobile. Cross-module conventions live in
[docs/modules/dashboard.md](../docs/modules/dashboard.md).

## Prerequisites

- Node 20+
- pnpm (install via `npm install -g pnpm` if missing — pnpm 11+ recommended)
- `uv` on `PATH` (used by server actions to invoke `next-signal ...`)
- `gbrain` on `PATH` (used by the knowledge search server action)
- `npx` / Folo auth for `/subscriptions` (`FOLO_TOKEN` or `~/.folo/config.json`)

## Run

The recommended entrypoint goes through the `next-signal` CLI so both backends share
one binary:

```bash
uv run next-signal dashboard             # http://localhost:3000, HMR
uv run next-signal dashboard --port 3001 # custom port
uv run next-signal dashboard --build     # `pnpm build`
uv run next-signal dashboard --start     # `pnpm start` (requires prior --build)
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

## The dashboard does NOT depend on `next-signal serve`

`next-signal serve` (AgentOS at `:7777`) and `next-signal dashboard` (Next at `:3000`) are
**fully decoupled processes**. Every dashboard feature today either reads
Postgres directly or spawns a one-shot `next-signal` CLI child — none make HTTP calls
to AgentOS.

| Doing this                                                                                                      | Need `next-signal serve`?                   |
| --------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| Browsing `/radar`, clicking Ingest / Pull+Analyze                                                               | ❌ no                                       |
| Searching `/knowledge`, clicking Re-index                                                                       | ❌ no                                       |
| Running workflows manually (`next-signal info-radar pull/analyze`, `next-signal run-workflow knowledge_ingest`) | ❌ no (CLI child, writes Postgres directly) |
| Debugging new agents / workflows                                                                                | ✅ yes (or use `next-signal run-agent`)     |

`NEXT_PUBLIC_AGENT_OS_URL` is pre-wired (default `http://localhost:7777`) for
the day a page actually needs to call AgentOS HTTP endpoints — none do yet.

## Environment variables

| Name                       | Default                   | Used by                                                            |
| -------------------------- | ------------------------- | ------------------------------------------------------------------ |
| `WIKI_DIR`                 | (none in code; Compose defaults to `./state/wiki`) | `/knowledge` (tree + re-index)                          |
| `NEXT_PUBLIC_AGENT_OS_URL` | `http://localhost:7777`   | Browser-side AgentOS calls (none yet)                              |
| `DATABASE_URL`             | (Postgres URL)            | `dashboard-radar` (direct DB reads)                                |
| `NEXT_SIGNAL_DATABASE_URL` | `DATABASE_URL`            | Optional dashboard-specific Postgres URL                           |
| `INFO_RADAR_TIMEZONE`      | `America/Los_Angeles`     | Calendar-day grouping and recap ranges for `/radar`                |
| `FOLO_TOKEN`               | (Folo CLI session file)   | `/subscriptions` via `next-signal info-radar subscriptions --json` |
| `FOLO_CLI_ARGV`            | `npx --yes folocli@0.0.5` | Optional override for the Folo CLI launcher                        |

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

### Brand marks

Three families live under [`components/brand/`](./components/brand/), all built
from one atom — a node — plus one connective form each:

| Family               | Module               | Field   | Connective form |
| -------------------- | -------------------- | ------- | --------------- |
| next-signal (parent) | `signal-mark.tsx`    | linear  | chevron         |
| info-radar           | `radar-mark.tsx`     | polar   | wedge           |
| knowledge-base       | `knowledge-mark.tsx` | network | link            |

Each module exports a flat **mark** and an animated **emblem**. Detail is a
function of size, and the tier is an explicit prop — never inferred from `size`:

```tsx
<RadarMark size={44} />                  // icon tier: rings, crosshairs, wedge, blip
<RadarMark size={16} variant="nav" />    // nav tier: ring, wedge, core
<RadarEmblem size={72} />                // emblem: + bearing ticks, sweep, 3 blips
```

Violet (`--accent`) carries structure in all three. Each module mark spends
exactly one secondary colour on the element that _is_ its job — the caught blip,
the index hub — from `--brand-spark-radar` / `--brand-spark-kb`. Those are
independent of the semantic verdict ramp on purpose: brand hue and status hue
must stay separately changeable.

Emblems are transparent, take every colour from tokens (so one asset serves both
themes), and stay server components — motion comes from the `.brand-*` hooks in
`app/globals.css`, where each radar blip's delay is _derived_ from its bearing
(`t = (bearing - 45) / 90`) rather than hand-tuned. Every emblem also has a
composed still under `prefers-reduced-motion: reduce`.

The one exception to token colouring is [`app/icon.svg`](./app/icon.svg), the
favicon: it is rasterised outside the document and cannot read CSS variables, so
its colours are baked.

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

Dashboard UI chrome defaults to **English** and can be switched from the nav
language picker, whose trigger shows the _current_ locale and whose menu lists
every available one. Locale names there are self-labelled and never translated
(`English`, `中文`) — the menu has to be readable to someone who cannot read the
language the UI is currently in. The selected locale is stored in the
`ns_locale` cookie (`en` / `zh`), and `app/layout.tsx` sets the matching
document `lang`.

Translations live in [`lib/i18n/dictionaries.ts`](./lib/i18n/dictionaries.ts).
Only interface copy is localized: labels, buttons, empty states, toasts,
relative time, and date display. User/data content such as article titles,
analysis summaries, tags, YAML values, wiki document bodies, and feed/category
names is rendered as stored.

## Settings

The **gear button** in the nav links to `/settings`, a page with four groups
and a sticky rail: content language, scheduled runs, engine, and embedding. It
replaced a nav popover — sections stacked in a 22rem panel left the engine group
nowhere to go.

Every value resolves server-side in `app/settings/page.tsx`, so the controls
paint their real state with no fetch on mount. When a setting persists depends
on the control, not the section:

| Control | Commits on | Why |
|---|---|---|
| Segmented (language, on/off, skip/catch-up, parallelism) | click | one interaction is already a complete, valid intent |
| A schedule time | blur / Enter | a native time input emits a complete value per segment edit, so saving each change would publish half-typed times |
| An engine's or embedder's own parameters | explicit **Save** | a partial combination is invalid and cannot be sent |

Either way a successful write raises a toast and a failed one rolls the control
back — an optimistic control moves whether or not the write landed.

## Content language

The first group holds the _content_ language: what the pipeline writes radar
analyses and wiki frontmatter in. It writes `content_language` into
`~/.next-signal/language.json`, which every `next-signal` agent on the `global` policy
reads (see [`docs/modules/core.md`](../docs/modules/core.md#output-language)).

This is deliberately independent of the UI locale above. Reading the interface in
one language while generating content in another is a supported state; nothing
syncs or warns about the two disagreeing.

## Engine

The third group picks which LLM engine next-signal calls, presented as four peers —
**Local model**, **DeepSeek**, **Codex CLI**, **Claude Code CLI** — with the
chosen one's settings opening below it, plus a fallback for when it cannot be
reached. Only the selected engine's form is on screen; four stacked forms was
the reason this needed a page.

They are peers to the operator but not on disk, and the split follows what
already owns each value:

| Setting | Written to | Runtime behavior |
|---|---|---|
| Codex CLI · Claude Code CLI model / effort / speed | `~/.next-signal/coding-agents.json` | Validated when that CLI is invoked |
| Primary engine, fallback, OMLX, and DeepSeek settings | `~/.next-signal/engine.json` | Read once at the start of each production job; changes apply to the next job |

Unset fields in `engine.json` read back from `configs/models.yaml` and
`OMLX_BASE_URL`, so a fresh install shows its real endpoint and model rather
than a value the dashboard invented. `DEEPSEEK_API_KEY` stays in `.env` — the
page reports only whether it is set, and never reads or stores the key itself.
Every LLM stage in one production job uses the same selected engine. A provider
failure may use the configured fallback only before the first successful
response; after that, later stages and schema repairs stay on the pinned engine.
Card status is limited to what the dashboard can observe (a key
present, a model chosen); nothing pings an endpoint, so nothing claims an
engine is reachable.

Neither CLI has an inherit choice: the operator must explicitly enter its model
and effort before next-signal can call it; Codex also requires speed.
next-signal hardcodes no CLI default because provider defaults change over time.
The model inputs suggest current names without restricting future IDs. Codex
Fast mode consumes credits faster on supported models/accounts. Claude accepts
aliases such as `opus`, `sonnet`, and `haiku`, full model names, and supported
`[1m]` aliases; effort is `low`, `medium`, `high`, `xhigh`, or `max`, with final
compatibility owned by Claude Code.

Saving one engine preserves every other's settings. The Dashboard never edits
`~/.codex/config.toml` or `~/.claude/settings.json`. In the official Docker
deployment, each CLI pane also shows the real saved-login status and offers a
bounded Connect/Reconnect/Disconnect flow. It invokes only fixed provider auth
commands and leaves the resulting files in the provider's own auth volume;
model settings remain in `coding-agents.json`.

## Embedding

The fourth group picks the embedder behind the radar's duplicate check, and
writes only `~/.next-signal/embedding.json`. It reuses the engine group's cards
and panes because the interaction is the same, but the consequence is not:
switching an LLM changes who answers a question, while switching an embedder
changes the *vector space*, parking every topic memorised under the previous
identity until you switch back. The group states that before the click, and
displays the exact active identity (`omlx:<model>`, `openai:<model>`, or
`openai_compatible:<space_id>`) verbatim.

Three peers — **Local model**, **OpenAI**, **Custom endpoint** — with one
asymmetry worth knowing:

| Card | Selecting it |
|---|---|
| Local model, OpenAI | commits on click, against that provider's last saved parameters |
| Custom endpoint, before it has ever been saved | **opens its pane and writes nothing** — there is no baseline to select |
| Custom endpoint, once saved | commits on click like the others |

The custom endpoint has no shipped default anywhere in the repo, so its pane is
all-or-nothing: **Save** stores `base_url`, `model`, `api_key_env`, and
`space_id` together and makes it active in the same write. `space_id` is your
own name for the vectors that endpoint produces — change it when weights,
tokenizer, pooling, or quantization change; moving the same service to a new URL
does not need a new one.

No credential passes through this page. The custom endpoint takes the *name* of
an environment variable, never a key, and its URL is restricted to a plain API
root so a secret cannot be persisted in userinfo, a query, or a fragment. Key
presence is computed server-side and reaches the browser as a boolean. Because
the value is read from the pipeline's own environment, editing `.env` needs a
host-process restart or a Compose recreate before it exists — the pane says so.
Hosted providers also state that every kept item's summary leaves the machine
and can be billed, including on unattended scheduler runs.

## Scheduled runs

The second group owns the unattended radar schedule: on/off, one or more daily
times, and whether a run missed while the machine was down gets caught up. It
writes `~/.next-signal/schedule.json`, which the `scheduler` container re-reads
on every 30s poll — so a change here takes effect without a restart.

Times are a list and **each one fires every day**. They render as chips in a
wrapping row rather than one full-width input per row, so three daily runs read
as a set rather than as a form. The last remaining time cannot be removed, since
an enabled schedule with nothing to fire is not a state worth having; "Off" is
how you stop it.

The time zone is **stated, not chosen**. The group shows the zone
`next_signal.core.clock` resolves from `INFO_RADAR_TIMEZONE` and names the
variable; changing it means changing the environment and restarting the stack.
That one value is shared with radar day grouping and review due dates, so a
schedule with a zone of its own would fire at 08:00 in one zone while its results
were filed under a day boundary drawn in another.

An earlier build did offer a picker, stored as `tz`, together with a warning that
the scheduler did not read it — a control whose only observable effect was the
warning that it had no effect. Both are gone. A `tz` left in the file by that
build is ignored on read and dropped on the next write; `next_signal.core.schedule`
takes named fields with `.get`, so its presence was never fatal and its absence
is not either. The next-run line is computed in the zone the scheduler actually
resolves — a next run stated in a zone that decides nothing is the one value here
an operator would act on without checking.

The group also reports where the last run stands, read from the `schedule_state`
table: never run, running (with how long it has been going), succeeded, or
failed. A run the scheduler never finished reads as failed once it starts again,
not as one still in flight. Catch-up covers every genuinely missed run, however
the miss happened — a stopped container, a machine asleep through the time, or a
previous run that overran it. Changing the schedule — or switching it on — never
fires a time that has just passed. See
[`docs/operations.md`](../docs/operations.md#unattended-runs).

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
- `yaml` — parse and render the runtime goals file for `/goals`.
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

`Pull + Analyze` awaits `uv run next-signal info-radar pull`, then starts
`uv run next-signal info-radar analyze` detached. Pull failures surface in the toast;
analyze failures land in the dashboard action log and the source of truth is the
Postgres state after refresh. The dashboard also writes
`~/.next-signal/radar-state.json` so zero-result clicks and
`Last feed` views reflect the operator's most recent click rather than stale DB
clusters. Per-item `Ingest` creates a tracked knowledge ingest job after
re-reading the item by id; Folo rows are staged as full-text HTML first, while
non-Folo rows use the validated `radar_items.url`.

## Goals

`/goals` edits `~/.next-signal/goals.yaml` directly through server actions — user
state, so the scheduler reads the same file and a rebuild cannot discard it.
Rendering the page never writes: the file is provisioned by container bootstrap,
or by the explicit **Start from example** control. An empty `goals:` list is valid
to save (clearing the examples is a legitimate step); analysis then fails loud
until a goal exists. The dashboard mirrors the Python loader contract: top-level
`goals`, unique read-only goal names, required description, string-list topics/keywords,
numeric weight, and no unknown fields. Invalid saves are rejected before writing;
valid saves use an atomic temp-file rename.

Existing goal names are read-only. Rename is intentionally modeled as delete +
add so downstream analysis history is never silently retargeted.

## Subscriptions

`/subscriptions` is read-only. It calls
`uv run next-signal info-radar subscriptions --json`, normalizes the Folo CLI envelope
into dashboard rows, then filters search/category client-side. The page never
adds, edits, deletes, or otherwise mutates Folo subscriptions.

Unread counts come from a second folocli command. `subscription list` carries no
unread field, so the integration also runs `unread list` — which enumerates every
feed that has unread entries — and joins it on `feedId`. A feed missing from that
response genuinely has zero unread, which is why `unread` is always a number and
never null. A failed `unread list` raises rather than degrading to absent counts,
since a table of zeroes reads as data.

There is no last-updated column. Folo's subscription list carries no per-feed
update timestamp — only `createdAt`, the date you subscribed — and the real value
would cost one `folo feed get <feedId>` call per feed.

## Build-script approval

pnpm 11 requires explicit approval for packages that run install scripts.
`esbuild`, `sharp` (Next.js image optimization), and `unrs-resolver` (Next.js
internals) are whitelisted in [`pnpm-workspace.yaml`](./pnpm-workspace.yaml).
