---
name: docker-verify
description: How to verify a change against next-signal's containerized stack (Postgres, dashboard, next-signal CLI). Use this skill whenever runtime or end-to-end verification is needed in Docker — running the next-signal CLI or a workflow in a container, inspecting the database, checking a dashboard page or API route, confirming that a change actually landed, or working out whether the container is running current code after an edit. Also use it before running anything that might spend model tokens, to pick a model-free command instead.
license: MIT
metadata:
  author: next-signal
  version: "1.0"
---

# Verifying in Docker (next-signal)

`CLAUDE.md` requires runtime / end-to-end verification to happen in containers,
not on the host. This skill is the how: which loop to run for a given edit, how
to reach each service, and what counts as evidence. For the topology — what runs
where and why — read
[`docs/containerized-deployment.md`](../../../docs/containerized-deployment.md);
this skill does not restate it.

**The one trap that matters.** `/app` is baked into the image, not bind-mounted.
Edit `src/` on the host, re-run `docker compose exec`, and you are testing the
*old* code — with no error to tell you. Every false pass in this stack starts
there. Before trusting any result, know which loop you owe.

---

## Which loop do I owe?

| You edited | Loop | Cost |
|---|---|---|
| wiki content, `/state` (incl. `goals.yaml`) | nothing — already live | 0s |
| `tests/`, `docs/`, `openspec/`, any `*.test.ts` | nothing — dockerignored, never in the image | 0s |
| `src/`, `configs/`, `prompts/`, `scripts/` | `docker compose build <svc>` + `up -d <svc>` | ~5–20s |
| `dashboard/` | `docker compose build <svc>` + `up -d <svc>` | minutes (`pnpm build`) |
| `.env` | `docker compose up -d --force-recreate <svc>` | ~5s |
| nothing — just inspecting | `docker compose exec -T <svc> <cmd>` | instant |

Measured on a warm cache: no-op build **3s**, `up -d dashboard` **4.3s**,
`run --rm dashboard next-signal list` **4.8s**. The Python rebuild loop is cheap — do
not avoid it. Only `dashboard/` edits are genuinely slow, because `pnpm build`
re-runs.

### The three path classes

- **Live** — `/wiki`, `/wiki-raw` (bind mounts), `/state` (named volume).
  Host and container see the same bytes immediately. No rebuild, no recreate.
- **Image-baked** — `/app`: `src/`, `configs/`, `prompts/`, `scripts/`,
  `dashboard/`. Requires build + recreate.
- **Excluded** — `tests/`, `docs/`, `openspec/`, and `**/*.test.ts` /
  `**/*.test.mjs` are in `.dockerignore`. They never enter the build context, so
  editing them cannot invalidate the cache and cannot be verified in a container.
  The last two matter because the dashboard's tests sit beside the source they
  exercise, so `tests/` alone does not cover them.

Confirm the live set any time you doubt it:

```bash
docker compose exec -T dashboard mount
```

Only `/state`, `/wiki`, and `/wiki-raw` will appear. `/app` will not.

---

## Is the container running my code?

`docker compose build` does **not** touch a running container. It builds an
image and stops. The container keeps serving the old one until recreated. Check:

```bash
docker image inspect next-signal:latest --format "{{.Id}}"
docker inspect next-signal-dashboard-1 --format "{{.Image}}"
```

Equal → the container is current. Different → **stop, you are about to verify
stale code.** Run `docker compose up -d dashboard` and re-check.

Do this after every build, before drawing any conclusion. It is two commands and
it is the difference between a real pass and a fabricated one.

> Note: a no-op rebuild still mints a new image ID (buildx regenerates the
> attestation manifest), so a changed ID does not by itself prove your code
> changed. It only ever proves the container needs recreating.

### restart vs up -d vs force-recreate

| Command | Container | Picks up |
|---|---|---|
| `restart <svc>` | same ID, reused | nothing — not new code, **not `.env`** |
| `up -d <svc>` | recreated if config/image changed | new image |
| `up -d --force-recreate <svc>` | always recreated | new image **and** `.env` |

`env_file` is read when the container is *created*. `restart` reuses the
existing container, so `.env` edits are invisible to it. Verified: `restart
dashboard` returns the identical container ID.

### Escape hatch: `docker compose cp`

⚠️ **Not the default. Read the caveat before using it.**

`next-signal` is installed editable and the CLI is short-lived, so a copied-in `.py`
takes effect on the *next* invocation — the fastest possible loop for a one-line
fix:

```bash
docker compose cp src/next_signal/workflows/foo.py dashboard:/app/src/next_signal/workflows/foo.py
docker compose exec -T dashboard next-signal <cmd>
```

**Caveats, both mandatory:**

1. It is **lost on recreate** — it lives only in the container's writable layer.
2. It is **not in the image**. You have verified something that does not ship.

Never report a result from a hot-patched container. Always finish with a real
`build` + `up -d` and re-run the check. If you would not remember to do that,
skip this section entirely and just rebuild — it costs seconds.

---

## Reaching each service

### `exec` is the default, `run --rm` is for one-shots

```bash
docker compose exec -T dashboard next-signal doctor        # reuse running container
docker compose run --rm -T dashboard next-signal list      # fresh container, ~4.8s
```

Use `run --rm` when the target service is not running, when you do not want to
touch the serving container, or for the one-shot `bootstrap` service. `run` does
not publish ports, so it will not collide with the running dashboard.

`bootstrap` is a one-shot that exits 0 after setup: the main DB schema, the
runtime goals file on `/state` (seeded from `goals.example.yaml` only when
absent), and gbrain's *database* — not gbrain itself. Bootstrap deliberately
does not run `gbrain init` on a first-time volume (the embedding model sizes
the schema permanently and no credential can exist yet), so a freshly bootstrap
stack has an empty gbrain database and `next-signal knowledge gbrain-init
--embedding-model <provider>:<model>` is a separate, explicit step. None of it
spends model tokens. `exec` against `bootstrap` fails:

```
service "bootstrap" is not running
```

Use `run --rm bootstrap ...`, or just target `dashboard` — same image.

### Database

Postgres is **not published to the host** — `localhost:5432` is refused. All
inspection goes through the service container:

```bash
docker compose exec -T postgres psql -U next_signal -d next_signal -c '\dt'
```

`-d next_signal` is **mandatory**. psql defaults to a database named after the
user, and `next-signal` does not exist — omitting it fails with
`database "next_signal" does not exist`.

Two databases on the one server: `next_signal` (next-signal's own) and `gbrain`
(gbrain's store, `GBRAIN_DATABASE_URL`).

Six business tables: `radar_items`, `radar_analyses`, `radar_pushed_topics`,
`radar_recaps`, `knowledge_reviews`, `schedule_state` — the keys of
`next_signal.core.db.BUSINESS_TABLE_COLUMNS`, which `next-signal doctor` checks the live
schema against. (`knowledge_tag_labels` was listed here but exists in no DDL,
no query, and no database.)

`schedule_state` is the scheduler's durable state, one row per job. It is the
fastest way to see what an unattended run is doing — `last_status` is `running`
from the moment a slot is claimed until the chain ends:

```bash
docker compose exec -T postgres psql -U next_signal -d next_signal \
  -c 'select job, last_slot_at, last_run_at, last_status, last_error from schedule_state;'
```

**Agno's tables (sessions / memory / traces) are provisioned lazily** — they only
appear once an agent has run against that database. Their absence is not
breakage, and does not mean bootstrap failed.

**Always `\d <table>` before writing a query.** Guessing column names wastes a
round trip — `knowledge_reviews` has `next_due_at`, not `due_at`.

```bash
docker compose exec -T postgres psql -U next_signal -d next_signal -c '\d radar_items'
```

### Dashboard

Published on `127.0.0.1:3000` (loopback by default — `DASHBOARD_BIND_ADDRESS`
widens it). Pages: `/`, `/radar`, `/radar/[id]`, `/knowledge`, `/goals`,
`/subscriptions`, `/settings`, `/design`. All read-only to render.

**`/` answers 307, not 200** — it redirects rather than rendering. Assert on
`307` for it, or a sweep that demands 200 everywhere reports a working stack as
broken.

Three `GET` routes are read-only — safe to poll freely:

- `/api/radar/run` — analyze progress (`{running, done, total}`)
- `/api/radar/recap?since=&until=` — recap status
- `/api/radar/export` — rendered signal digest

`/api/coding-agents/auth/<provider>` is **not** in that set. Its `GET` is a
status read, but `POST` starts a real provider login session, `PUT` feeds it an
authorization code, and `DELETE` cancels it. Do not poll it as a health check.

`next start` logs almost nothing per request, so **do not verify a page from the
container logs** — use the HTTP status plus a content assertion.

---

## Spending model tokens on purpose

Most verification needs no model call at all. Pick from the left column unless
the change is specifically in a model path.

| Model-free — verify freely | Spends tokens |
|---|---|
| `next-signal list`, `next-signal doctor` | `next-signal run-agent` |
| `next-signal knowledge review` | `next-signal knowledge ingest` |
| `next-signal info-radar pull` / `sweep` | `next-signal run-workflow knowledge_ingest` |
| `next-signal info-radar subscriptions --json` | `next-signal info-radar analyze` |
| all dashboard pages, all `/api/radar/*` GETs | `next-signal info-radar recap` |
| `next-signal coding-agent doctor` | `next-signal coding-agent run` |
| `psql`, `gbrain` health | |

Dashboard controls map the same way: **Review** and **Pull** are free;
**Analyze**, **Recap**, and **Re-index** are not.

**Embedding is only free while the embedder is local.** The dedup gate inside
`info-radar analyze` embeds every kept item, and `~/.next-signal/embedding.json`
decides where that goes. On the default `omlx` provider it is local inference —
GPU time, no bill, nothing leaves the machine. Selecting `openai` or an
OpenAI-compatible endpoint makes the same step a **paid off-machine call, once
per kept item**, including on unattended scheduler runs. Check the selected
provider before assuming the embedding half of a run is free:

```bash
docker compose exec dashboard next-signal doctor   # prints the resolved embedder identity
```

`doctor` itself stays free under every provider — it reports configuration and
never issues an embedding request.

**The `scheduler` service spends tokens with nobody typing a command.** It is
the one entry here that is not something you run — `docker compose up` starts
it, and if `~/.next-signal/schedule.json` has `enabled: true` it fires
`info_radar_pull` → `info_radar_analysis` at each configured time, on whatever
engine `~/.next-signal/engine.json` selects. Two consequences when verifying:

- A run you did not start can appear mid-verification. `docker compose logs
  scheduler` and the `schedule_state` row say whether one is in flight
  (`last_status = 'running'`).
- To verify anything else without that risk, either leave the schedule disabled
  (an absent file reads as disabled) or `docker compose stop scheduler` first.

`next-signal info-radar pull` is the workhorse for verifying the collector path — real
network, real DB writes, no model, and idempotent (re-running reports items as
skipped rather than duplicating them).

The safe list is only true while `src/next_signal/collectors/` stays free of
`build_from_name` / `get_model` / `get_embedder`. If you add a model call to a
path listed as free, update this table in the same change.

---

## Two things that look like failures but aren't

### `next-signal doctor` exits 1 by design

Under the cloud-only container profile, the local chat endpoint, the unselected
embedder, an uninitialised GBrain, and any unset model key report ✗ and force a
non-zero exit — that is the normal state of a stack nobody has configured yet.
**Read the check lines, not the exit code.** The stack is healthy when
`DATABASE_URL`, `Postgres`, `configured agents`, and `registered tools` all
show ✔.

The GBrain line reads `not initialised — knowledge search is unavailable; run
next-signal knowledge gbrain-init --embedding-model <provider>:<model>` on a
fresh volume. This does not mean `gbrain doctor --fast` is broken or missing —
`next-signal doctor` deliberately does not trust it here, because it reports a
healthy brain and exits 0 even when none exists.

### `sh -lc` erases `next-signal` from PATH

A login shell re-sources `/etc/profile` and drops the Dockerfile's
`/app/.venv/bin`:

```bash
docker compose exec -T dashboard sh -lc 'command -v next-signal'   # → empty. WRONG.
docker compose exec -T dashboard sh -c  'command -v next-signal'   # → /app/.venv/bin/next-signal
```

Use `sh -c`, or exec `next-signal` directly with no shell at all. If `next-signal` is suddenly
"not found", this is why — the image is fine.

---

## Watching dashboard-triggered work

Dashboard server actions spawn `next-signal` **detached** and return immediately. The
toast says *started*, never *completed* — it carries no information about
success.

The action log is under the container's `$HOME`, which is `/root` — **not**
`/state`:

```bash
docker compose exec -T dashboard tail -n 40 /root/.next-signal/dashboard-actions.log
```

It does **not survive a recreate**, because `$HOME` is not on a volume. So:

- Use the log for live progress and stack traces.
- Take durable evidence from the **database**, never from the log.

For a long analyze run, poll `GET /api/radar/run` rather than tailing.

---

## Tests do not run in the container

Neither suite nor runner reaches the image, on either side:

- **Python** — `.dockerignore` excludes `tests/`, `uv sync --no-dev` omits pytest.
  `pytest` inside the container fails with `Failed to spawn: pytest`.
- **Dashboard** — `.dockerignore` excludes `**/*.test.ts` (they live beside the
  source, so `tests/` does not cover them), and `pnpm prune --prod` after
  `pnpm build` drops `tsx` along with the linters and type tooling. `typescript`
  itself is a runtime dependency on purpose: Next reads `next.config.ts` at
  startup and re-installs it on every boot otherwise.

**Unit tests run on the host** — `uv run pytest -q`, and `pnpm test` in
`dashboard/`. Containers are for runtime and end-to-end verification only. Do not
try to reconcile these; it is the intended split.

---

## Host shell differences

Everything above is identical on every host — it happens inside the same Linux
image. Only the wrapper you type differs.

**macOS means zsh** (default since Catalina). The guidance below deliberately
avoids every construct where zsh and bash disagree, so it holds either way.

| Need | macOS / Linux (zsh) | Windows PowerShell |
|---|---|---|
| HTTP status | `curl -fsS -o /dev/null -w '%{http_code}' <url>` | `(Invoke-WebRequest <url> -UseBasicParsing).StatusCode` |
| file hash | `shasum -a 256 <f>` | `(Get-FileHash <f>).Hash` |
| capture output | `> out.txt 2>&1` | `> out.txt 2>&1` |
| truncate output | `head -n 20` | `Select-Object -First 20` |

### Hazard 1 — quote the remote command in single quotes

zsh, bash, **and** PowerShell all expand `$VAR` inside double quotes on the
*host*, before Docker ever sees the string:

```powershell
docker compose exec -T dashboard sh -c "echo $HOME"    # → C:Usersjiach  WRONG
docker compose exec -T dashboard sh -c 'echo $HOME'    # → /root        correct
```

Better still, skip the shell — no interpolation layer, nothing to escape:

```bash
docker compose exec -T dashboard printenv HOME
```

### Hazard 2 — never read an exit code through a truncating pipe

This one is **mirrored**: same rule, opposite failure on each host.

| | default pipeline status | failure mode |
|---|---|---|
| zsh / bash | status of the *last* command (`head`) → `0` | **false pass** — docker's failure is swallowed |
| PowerShell | `$LASTEXITCODE` from the native command → `255` | **false fail** — a success looks broken |

The zsh/bash direction is the dangerous one: `$?` after a piped
`docker compose exec` reads `0` no matter what happened upstream. Measured:
a large stream through `head -n 5` gives `PIPESTATUS=(1 0)` with a pipeline exit
of `0`.

**The portable fix is the same everywhere — redirect, then check unpiped:**

```bash
docker compose exec -T dashboard next-signal doctor > out.txt 2>&1
echo $?          # honest status; $LASTEXITCODE in PowerShell
```

Do not reach for `pipefail` or `PIPESTATUS` — the array is `${PIPESTATUS[0]}` in
bash but `${pipestatus[1]}` in zsh, and you do not need either.

Note the hazard is intermittent: small outputs fit the pipe buffer and never
trigger it. That is exactly why it needs a rule rather than intuition.

### On `-T`

`-T` disables TTY allocation and keeps output clean for non-interactive callers.
Use it. But it is **not** an exit-code fix — verified: with and without `-T`, an
unpiped command exits 0. The pipe is the hazard, not the TTY.

> Verification note: every container-side claim here was probed against the
> running stack, and the POSIX column — pipeline exit semantics, the `curl`
> status form, `shasum -a 256`, the readiness poll — was executed in real bash.
> Container behavior is host-independent (same Linux image), so none of it needs
> re-testing per host. The single untested assumption is that a macOS user is on
> zsh rather than an opted-in bash, which is inconsequential because nothing here
> uses a construct where the two differ.

---

## What counts as evidence

**A clean exit is not verification.** "It ran without error" says nothing about
whether the change works. Tie the evidence to the change:

- **Wrote a row?** Query the table.
- **Changed a page?** HTTP status **plus** an assertion on the content.
- **Changed a code path?** A specific log line proving it executed.

State what you ran and what you observed. If you could not verify something, say
so plainly — an unverified claim reported as verified is worse than an admitted
gap.

### Worked example (model-free, instant)

Run the command, then prove it landed:

```bash
docker compose exec -T dashboard next-signal knowledge review
# → knowledge review: enrolled=1 unenrolled=0 due=0     (first run)
# → knowledge review: enrolled=0 unenrolled=0 due=0     (already enrolled — idempotent)

docker compose exec -T postgres psql -U next_signal -d next_signal \
  -c 'select doc_path, captured_at, stage, next_due_at from knowledge_reviews;'
# → the enrolled row, with its scheduled next_due_at
```

The CLI line alone is a claim, and note that it *changes with prior state* —
`enrolled=0` on a re-run means "already done", not "nothing happened". The row is
the evidence, and it reads the same either way. When a summary line and a table
disagree about whether work happened, trust the table.

### Readiness poll after a recreate

`up -d` returns before Next.js is serving. Poll rather than sleeping:

```bash
for i in $(seq 1 30); do
  code=$(curl -fsS -o /dev/null -w '%{http_code}' http://localhost:3000/radar) && \
    [ "$code" = "200" ] && { echo "ready"; break; }
  sleep 0.5
done
```

```powershell
foreach ($i in 1..30) {
  try { if ((Invoke-WebRequest http://localhost:3000/radar -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200) { "ready"; break } }
  catch { Start-Sleep -Milliseconds 500 }
}
```

### Route smoke check

After any `dashboard/` change, sweep all seven and confirm each answers as noted
— `/` redirects (307), the other six render (200):

`/` (307) · `/radar` · `/knowledge` · `/goals` · `/subscriptions` · `/settings` · `/design`

```bash
for p in / /radar /knowledge /goals /subscriptions /settings /design; do
  printf "%-16s %s\n" "$p" "$(curl -fsS -o /dev/null -w '%{http_code}' http://localhost:3000$p)"
done
```
