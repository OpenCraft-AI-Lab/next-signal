---
name: docker-verify
description: How to verify a change against next-signal's containerized stack (Postgres, dashboard, paca CLI). Use this skill whenever runtime or end-to-end verification is needed in Docker — running the paca CLI or a workflow in a container, inspecting the database, checking a dashboard page or API route, confirming that a change actually landed, or working out whether the container is running current code after an edit. Also use it before running anything that might spend model tokens, to pick a model-free command instead.
license: MIT
metadata:
  author: paca
  version: "1.0"
---

# Verifying in Docker (paca)

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
| wiki content, `/state` | nothing — already live | 0s |
| `tests/`, `docs/`, `openspec/` | nothing — dockerignored, never in the image | 0s |
| `src/`, `configs/`, `prompts/`, `scripts/` | `docker compose build <svc>` + `up -d <svc>` | ~5–20s |
| `dashboard/` | `docker compose build <svc>` + `up -d <svc>` | minutes (`pnpm build`) |
| `.env` | `docker compose up -d --force-recreate <svc>` | ~5s |
| nothing — just inspecting | `docker compose exec -T <svc> <cmd>` | instant |

Measured on a warm cache: no-op build **3s**, `up -d dashboard` **4.3s**,
`run --rm dashboard paca list` **4.8s**. The Python rebuild loop is cheap — do
not avoid it. Only `dashboard/` edits are genuinely slow, because `pnpm build`
re-runs.

### The three path classes

- **Live** — `/wiki`, `/wiki-raw` (bind mounts), `/state` (named volume).
  Host and container see the same bytes immediately. No rebuild, no recreate.
- **Image-baked** — `/app`: `src/`, `configs/`, `prompts/`, `scripts/`,
  `dashboard/`. Requires build + recreate.
- **Excluded** — `tests/`, `docs/`, `openspec/` are in `.dockerignore`. They
  never enter the build context, so editing them cannot invalidate the cache and
  cannot be verified in a container.

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

`paca` is installed editable and the CLI is short-lived, so a copied-in `.py`
takes effect on the *next* invocation — the fastest possible loop for a one-line
fix:

```bash
docker compose cp src/paca/workflows/foo.py dashboard:/app/src/paca/workflows/foo.py
docker compose exec -T dashboard paca <cmd>
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
docker compose exec -T dashboard paca doctor        # reuse running container
docker compose run --rm -T dashboard paca list      # fresh container, ~4.8s
```

Use `run --rm` when the target service is not running, when you do not want to
touch the serving container, or for the one-shot `bootstrap` service. `run` does
not publish ports, so it will not collide with the running dashboard.

`bootstrap` is a one-shot that exits 0 after schema setup. `exec` against it
fails:

```
service "bootstrap" is not running
```

Use `run --rm bootstrap ...`, or just target `dashboard` — same image.

### Database

Postgres is **not published to the host** — `localhost:5432` is refused. All
inspection goes through the service container:

```bash
docker compose exec -T postgres psql -U paca -d next_signal -c '\dt'
```

`-d next_signal` is **mandatory**. psql defaults to a database named after the
user, and `paca` does not exist — omitting it fails with
`database "paca" does not exist`.

Two databases on the one server: `next_signal` (paca's own) and `gbrain`
(gbrain's store, `PACA_GBRAIN_DATABASE_URL`).

Five business tables: `radar_items`, `radar_analyses`, `radar_pushed_topics`,
`radar_recaps`, `knowledge_reviews` — the keys of
`paca.core.db.BUSINESS_TABLE_COLUMNS`, which `paca doctor` checks the live
schema against. (`knowledge_tag_labels` was listed here but exists in no DDL,
no query, and no database.)

**Agno's tables (sessions / memory / traces) are provisioned lazily** — they only
appear once an agent has run against that database. Their absence is not
breakage, and does not mean bootstrap failed.

**Always `\d <table>` before writing a query.** Guessing column names wastes a
round trip — `knowledge_reviews` has `next_due_at`, not `due_at`.

```bash
docker compose exec -T postgres psql -U paca -d next_signal -c '\d radar_items'
```

### Dashboard

Published on `localhost:3000`. Pages: `/`, `/radar`, `/knowledge`, `/goals`,
`/subscriptions`, `/design`. All read-only to render.

Three API routes, all `GET`, all read-only — safe to poll freely:

- `/api/radar/run` — analyze progress (`{running, done, total}`)
- `/api/radar/recap?since=&until=` — recap status
- `/api/radar/export` — rendered signal digest

`next start` logs almost nothing per request, so **do not verify a page from the
container logs** — use the HTTP status plus a content assertion.

---

## Spending model tokens on purpose

Most verification needs no model call at all. Pick from the left column unless
the change is specifically in a model path.

| Model-free — verify freely | Spends tokens |
|---|---|
| `paca list`, `paca doctor` | `paca run-agent` |
| `paca knowledge review` | `paca knowledge ingest` |
| `paca info-radar pull` / `sweep` | `paca run-workflow knowledge_ingest` |
| `paca info-radar subscriptions --json` | `paca info-radar analyze` |
| all dashboard pages, all `/api/radar/*` GETs | `paca info-radar recap` |
| `psql`, `gbrain` health | |

Dashboard controls map the same way: **Review** and **Pull** are free;
**Analyze**, **Recap**, and **Re-index** are not.

`paca info-radar pull` is the workhorse for verifying the collector path — real
network, real DB writes, no model, and idempotent (re-running reports items as
skipped rather than duplicating them).

The safe list is only true while `src/paca/collectors/` stays free of
`build_from_name` / `get_model` / `get_embedder`. If you add a model call to a
path listed as free, update this table in the same change.

---

## Two things that look like failures but aren't

### `paca doctor` exits 1 by design

Under the cloud-only container profile, `OMLX_BASE_URL` and any unset model key
report ✗ and force a non-zero exit. **Read the check lines, not the exit code.**
The stack is healthy when `DATABASE_URL`, `Postgres`, `configured agents`, and
`registered tools` all show ✔.

### `sh -lc` erases `paca` from PATH

A login shell re-sources `/etc/profile` and drops the Dockerfile's
`/app/.venv/bin`:

```bash
docker compose exec -T dashboard sh -lc 'command -v paca'   # → empty. WRONG.
docker compose exec -T dashboard sh -c  'command -v paca'   # → /app/.venv/bin/paca
```

Use `sh -c`, or exec `paca` directly with no shell at all. If `paca` is suddenly
"not found", this is why — the image is fine.

---

## Watching dashboard-triggered work

Dashboard server actions spawn `paca` **detached** and return immediately. The
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

There is no `tests/` directory and no runner in the image (`.dockerignore`
excludes the suite; `uv sync --no-dev` omits pytest). `pytest` inside the
container fails with `Failed to spawn: pytest`.

**Unit tests run on the host** — `uv run pytest -q`. Containers are for runtime
and end-to-end verification only. Do not try to reconcile these; it is the
intended split.

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
docker compose exec -T dashboard paca doctor > out.txt 2>&1
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
docker compose exec -T dashboard paca knowledge review
# → knowledge review: enrolled=1 unenrolled=0 due=0     (first run)
# → knowledge review: enrolled=0 unenrolled=0 due=0     (already enrolled — idempotent)

docker compose exec -T postgres psql -U paca -d next_signal \
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

After any `dashboard/` change, sweep all six and confirm every one is 200:

`/` · `/radar` · `/knowledge` · `/goals` · `/subscriptions` · `/design`
