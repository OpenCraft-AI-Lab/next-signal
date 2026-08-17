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
- `npx` and a Folo token for `/subscriptions` (Settings → RSS)

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
| _(`FOLO_TOKEN`)_           | not an env var            | Set in Settings → RSS; used by `/subscriptions`                     |
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

The **gear button** in the nav links to `/settings`, a page with seven
collapsible sections and a sticky rail: content language, scheduled runs,
engine, radar embedding, knowledge embedding, RSS, and a read-only credentials
summary. It replaced a nav popover — sections stacked in a 22rem panel left the
engine group nowhere to go.

Every section starts **collapsed**, showing only its label and a one-line
summary of what is selected (or that nothing is); expanding it is required to
change anything. Every value resolves server-side in `app/settings/page.tsx`,
so the controls paint their real state with no fetch on mount. When a setting
persists depends on the control, not the section:

| Control | Commits on | Why |
|---|---|---|
| Segmented (language, on/off, skip/catch-up, parallelism) | click | one interaction is already a complete, valid intent |
| A schedule time | blur / Enter | a native time input emits a complete value per segment edit, so saving each change would publish half-typed times |
| An engine's, embedder's, or GBrain provider's own parameters | explicit **Save configuration** | a partial combination is invalid and cannot be sent |
| Which engine is primary, which embedder is selected | explicit **Apply selection** (Engine) or the pane's own confirmed Save (Radar/Knowledge Embedding) | picking a card only proposes it; a separate commit is what writes it, unlike the plain discrete choices above |

Either way a successful write raises a toast and a failed one rolls the control
back — an optimistic control moves whether or not the write landed.

Every credential (`DEEPSEEK_API_KEY`, the two OpenAI keys, `EMBEDDING_API_KEY`,
`VOYAGE_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, `FOLO_TOKEN`) is entered
inline, in the section that consumes it — there is no shared credential-entry
section anymore. The **Credentials** section at the bottom of the page is a
plain, read-only, presence-only summary of all of them; it exists so an
operator can see the whole configured surface at a glance, not to enter or
clear anything.

## Content language

The first group holds the _content_ language: what the pipeline writes radar
analyses and wiki frontmatter in. It writes `content_language` into
`~/.next-signal/language.json`, which every `next-signal` agent on the `global` policy
reads (see [`docs/modules/core.md`](../docs/modules/core.md#output-language)).

This is deliberately independent of the UI locale above. Reading the interface in
one language while generating content in another is a supported state; nothing
syncs or warns about the two disagreeing.

## Engine

The engine section picks which LLM engine next-signal calls, presented as four
peers — **Local model**, **DeepSeek**, **Codex CLI**, **Claude Code CLI** —
with the chosen one's settings opening below it, plus a fallback for when it
cannot be reached. Only the selected engine's form is on screen; four stacked
forms was the reason this needed a page.

**Nothing is selected on a fresh install**, and no card shows as chosen until
one is explicitly applied — this is real, not cosmetic: on the Python side,
`EnginePreferences.primary` is genuinely optional, and every production stage
job (`stage_job()`) raises a distinct `EngineNotSelected` before any provider
call when nothing has been saved, rather than silently defaulting to the local
model the way it once did. Clicking a card only proposes it as primary; an
explicit **Apply selection** action (rendered beside whichever pane's own Save
button is currently open, not in a separate block) is the commit, matching
every other section's own-parameters-need-explicit-Save rule rather than the
commit-on-click behavior a plain discrete choice gets elsewhere on this page.

They are peers to the operator but not on disk, and the split follows what
already owns each value:

| Setting | Written to | Runtime behavior |
|---|---|---|
| Codex CLI · Claude Code CLI model / effort / speed | `~/.next-signal/coding-agents.json` | Validated when that CLI is invoked |
| Primary engine, fallback, OMLX, and DeepSeek settings | `~/.next-signal/engine.json` | Read once at the start of each production job; changes apply to the next job |

Unset fields in `engine.json` read back from `configs/models.yaml` as **form
prefill only** — a suggested model string for the OMLX/DeepSeek panes' own
fields — never as a selected primary. The local endpoint has no baseline at
all and starts **empty**, because no value the repo could ship would be right
and reading one from this container's environment would show the dashboard's
answer while the scheduler resolves its own. An empty endpoint is savable — it
is how you say you have no local server, which sends OMLX profiles to their
cloud fallback. The OMLX card's status reflects whether that endpoint has
actually been saved, not a fixed "configured" label. Scheduled runs and new
commands see a change immediately; agents already running inside AgentOS pick
it up when that process restarts. `DEEPSEEK_API_KEY` is entered inline in the
DeepSeek pane — the page reports only whether it is set, and never reads or
stores the key itself.
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

## Radar Embedding

This section picks the embedder behind the radar's duplicate check, and writes
only `~/.next-signal/embedding.json`. It reuses the engine section's cards and
panes because the interaction is similar, but the consequence is bigger: an
embedder choice **locks the section in full once saved** — every card and pane
renders read-only afterward, with no unlock path through this UI. A different
model produces vectors that cannot be compared against ones already stored, so
this is a one-time choice for the life of the install, not a switchable
preference the way the engine is. The section displays the exact active
identity (`omlx:<model>`, `openai:<model>`, or `openai_compatible:<space_id>`)
verbatim once locked.

**Nothing is selected on a fresh install**, and the section says so: dedup is
off until you choose an embedder, and the radar otherwise runs normally. There
is no provider the repo could honestly pick for you — the local one needs an
address only you know, the hosted ones need a key and spend money.

Three peers — **Local model**, **OpenAI**, **Custom endpoint** — all behaving
identically while unlocked:

| Card | Selecting it |
|---|---|
| Any card whose settings are incomplete | **opens its pane and writes nothing** — there is nothing valid to select yet |
| The first complete, credentialed pane you save | prompts for confirmation that the choice is permanent, then commits and locks the section |

A pane opens prefilled with suggestions from `configs/models.yaml` — form
prefill, not defaults; only what you save runs. **Save configuration** stores
that provider's fields and selects it in the same write.

The local card carries **its own API root**, separate from the engine section's:
one mlx-lm process serves one model, so a chat model and an embedding model are
two ports. `space_id`, on the custom endpoint, is your own name for the vectors
it produces — change it when weights, tokenizer, pooling, or quantization
change; moving the same service to a new URL does not need a new one.

Each hosted pane's credential is entered **inline, in that pane** —
`RADAR_EMBEDDING_OPENAI_API_KEY` for OpenAI, `EMBEDDING_API_KEY` for the
custom endpoint — and saving requires that credential to already be present,
not just the other fields, since this save is about to lock the section
permanently. `RADAR_EMBEDDING_OPENAI_API_KEY` is a different stored credential
from GBrain's own `OPENAI_API_KEY` (see Knowledge Embedding below), even
though both are "an OpenAI key" — they're independent embedding flows that
coincidentally shared one name in the past. URLs are restricted to a plain API
root so a secret cannot be persisted in userinfo, a query, or a fragment. Key
presence is computed server-side and reaches the browser as a boolean. Hosted
providers also state that every kept item's summary leaves the machine and can
be billed, including on unattended scheduler runs.

## Knowledge Embedding

This section configures and initializes **GBrain**'s embedding provider for
knowledge-base search — independent of Radar Embedding above, which configures
a different embedder for a different vector space entirely. It's the
dashboard's front end for what used to be CLI-only:
`next-signal knowledge gbrain-init --embedding-model <provider>:<model>`.

Six peers — **OpenAI**, **Voyage**, **Google**, **Ollama**, **LM Studio**,
**llama-server** — the three hosted ones needing a credential entered inline in
their own pane (`OPENAI_API_KEY`, `VOYAGE_API_KEY`,
`GOOGLE_GENERATIVE_AI_API_KEY` respectively — GBrain's own subprocess reads
these exact names from its environment, an external contract this dashboard
doesn't choose), the three local runners needing none. Saving a hosted pane
requires its credential to already be present, same rule as Radar Embedding.

Saving is a two-step commit: an explicit warning that the model choice is
**permanent for the life of this GBrain instance** (it sizes GBrain's Postgres
schema; a second `gbrain-init` against an initialised brain refuses rather than
reconfiguring it), then the actual `gbrain-init` call — awaited, not
fire-and-forget, so the section knows the real outcome before deciding whether
to lock. Success locks the section; a failure (including "already
initialised") leaves it open and reports the error.

The section reports GBrain's readiness as one of three states — **not
initialized**, **initialized but credential missing**, **ready** — computed by
reading `.gbrain/config.json` directly, the same way `next-signal doctor`
does, rather than trusting `gbrain doctor --fast` (which reports a healthy
brain even when none exists).

## RSS

This section owns `FOLO_TOKEN` — the credential info-radar's Folo source and
the `/subscriptions` page depend on. Two entry points: **Sign in to Folo**
(opens Folo in a new tab, exchanges the returned one-time token on a
dashboard-hosted callback route, and stores the resulting session token) and
**Paste manually** (opens a small dialog for a browser that cannot reach the
dashboard, or if sign-in fails — the same stored result either way).

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
