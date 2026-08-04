## Context

`CLAUDE.md` 测试 section requires runtime / end-to-end verification to happen in
Docker. `docs/containerized-deployment.md` explains the topology well, but it is
written for an operator standing up the stack on macOS — it answers "what runs
where and why", not "I just changed `tier1.py`, how do I confirm it works".

A live probe of the running stack on 2026-07-28 (Windows 11 host, Docker Compose
v5.2.0, `postgres` up 3 days, `dashboard` rebuilt during the session) established
the facts below. Each was observed, not inferred:

| Probe | Result |
|---|---|
| `mount` inside `dashboard` | only `/state`, `/wiki`, `/wiki-raw` — `/app` is image-baked |
| `docker compose build` then compare image IDs | container stayed on the **old** image |
| `docker compose up -d dashboard` | image IDs match; **4.3s** |
| `docker compose build` (no-op) | **3s** |
| `docker compose run --rm -T dashboard paca list` | **4.8s** |
| `docker compose restart dashboard` | same container ID → `env_file` not re-read |
| `sh -lc 'command -v paca'` | empty — login shell drops `/app/.venv/bin` |
| `sh -c 'command -v paca'` | `/app/.venv/bin/paca` |
| `paca doctor` | exit 1, with only `ANTHROPIC_API_KEY` / `OMLX_BASE_URL` ✗ |
| `uv run pytest --version` in container | `Failed to spawn: pytest`; `/app/tests` absent |
| host TCP `localhost:5432` | refused — port not published |
| `psql -U paca` without `-d` | `database "paca" does not exist` |
| `paca knowledge review` → `psql` | 1 row enrolled, confirmed in `knowledge_reviews` |
| `paca info-radar pull` | 35s, `written=0 skipped=20` — idempotent, no model call |
| 6 dashboard routes + 3 `/api/radar/*` GETs | all 200 |
| `docker compose exec bootstrap` | `service "bootstrap" is not running` |
| `docker compose cp` round trip | clean both directions |

Two host-shell hazards showed up while probing, both of which silently corrupt
results rather than failing loudly:

- `sh -c "echo $HOME"` returned `C:Usersjiach` — PowerShell expanded the *host*
  variable and stripped backslashes before Docker ever saw the string.
- Piping docker output into `Select-Object -First N` returned exit 255 / -1 on
  commands that had actually succeeded. Isolating this showed `-T` was **not** the
  cause: with and without `-T`, an unpiped command exits 0.

## Goals / Non-Goals

**Goals:**

- An agent can go from "I changed X" to "here is evidence it works" without
  rediscovering the stack, and without ever verifying against stale code.
- The expensive mistakes are made loud: stale image, wrong verification loop,
  accidental model spend.
- Model-free verification is the default path; incurring model cost is a
  deliberate, informed choice.
- The guidance works on macOS/Linux and Windows without forking into two
  documents.

**Non-Goals:**

- Replacing `docs/containerized-deployment.md`. That stays the operator/design
  doc; the skill links to it rather than restating the topology.
- Teaching Docker generally. Only project-specific facts and the idioms an agent
  actually types here.
- Changing the image, compose topology, or any application behavior.
- Host-native (`uv run paca serve`) workflows — out of scope by the existing rule.

## Decisions

### A skill, not another doc under `docs/`

The audience is the agent, and the trigger is behavioral ("verify this change").
That is what `.claude/skills/` is for, and there is precedent: `code-review`
lives there with no corresponding entry in `openspec/specs/`. It also settles the
language question — `docs/` is bilingual by rule, but agent instructions are
exempt (`CLAUDE.md` names itself and `openspec/specs/` as the two deliberate
exceptions). The skill is written in English to match `code-review/SKILL.md`,
which already instructs the agent to *report* in the user's language.

### Structure: decision matrix first, reference second

The single highest-value artifact is a table mapping "what did you edit" to
"what loop do you run". Everything else is reference material an agent reads on
demand. The skill leads with:

```
edited …                        → loop                                    cost
─────────────────────────────────────────────────────────────────────────────
wiki content, /state            → nothing; already live                    0s
tests/ docs/ openspec/          → nothing; dockerignored (host pytest)     0s
src/ configs/ prompts/          → compose build + up -d <svc>              ~5-20s
dashboard/                      → compose build + up -d (pnpm build slow)  minutes
.env                            → compose up -d --force-recreate           ~5s
nothing (just inspecting)       → compose exec -T, or run --rm             ~5s
```

The measured timings are included deliberately: an agent that believes a rebuild
is expensive will reach for hot-patching, which is the riskier path.

### One cross-platform skill, with a host-shell translation table

The split is clean, so a fork would be waste: **everything inside the container
is identical on both hosts** (same Linux image) — `sh -lc` PATH loss, baked
`/app`, psql flags, `paca doctor` semantics, the LLM map, the action log path.
Only the *host* wrapper differs. So the skill states container facts once, and
carries one table for host idioms:

| Need | macOS / Linux (zsh) | Windows PowerShell |
|---|---|---|
| HTTP check | `curl -fsS -o /dev/null -w '%{http_code}' …` | `Invoke-WebRequest … -UseBasicParsing` |
| file hash | `shasum -a 256 <f>` | `Get-FileHash <f>` |
| capture output | `> out.txt 2>&1` | `> out.txt 2>&1` |
| truncate output | `head -n 20` | `Select-Object -First 20` |

**macOS means zsh.** Default login shell since Catalina (2019). The assumption
costs nothing here because the guidance below deliberately avoids every construct
where zsh and bash disagree — notably `${PIPESTATUS[0]}` (bash, 0-indexed) vs
`${pipestatus[1]}` (zsh, 1-indexed), which the skill does not use at all.

Of the two headline hazards, the first is genuinely identical across platforms
and the second is **mirrored** — same rule, opposite failure direction:

- **Quote the remote command in single quotes.** zsh, bash, and PowerShell all
  expand `$VAR` inside double quotes on the *host*. `'…$HOME…'` is correct
  everywhere; better still, avoid the shell — `docker compose exec -T dashboard
  printenv HOME` has no interpolation layer at all.
- **Never read an exit code through a truncating pipe.** Verified on both sides,
  and they fail in opposite directions:

  | | default pipeline status | failure mode |
  |---|---|---|
  | zsh / bash | status of the *last* command (`head`) → `0` | **false pass** — docker's real status is swallowed |
  | PowerShell | `$LASTEXITCODE` from the native command → `255` | **false fail** — a successful command looks broken |

  Measured in Git Bash: piping a large stream through `head -n 5` gave
  `PIPESTATUS=(1 0)` with a pipeline exit of `0`; the same pipeline under
  `set -o pipefail` exited `1`. The false-pass direction is the dangerous one —
  an agent checking `$?` after a piped `docker compose exec` sees success no
  matter what happened. The portable fix is the same on every host: **redirect to
  a file and check the exit code of the unpiped command.** No `pipefail`, no
  `PIPESTATUS`, nothing shell-specific.

  Note also that neither shell produces the textbook `141` (128+SIGPIPE) here —
  docker mediates the signal and reports `1`. Small outputs fit the pipe buffer
  and never trigger it at all, which is what makes this hazard intermittent and
  worth an explicit rule.

### `-T` is recommended, but for the right reason

`-T` disables TTY allocation, which keeps output clean for non-interactive
callers. It was tempting to sell it as an exit-code fix; the probe disproved
that. The skill recommends `-T` on honest grounds and separately names the pipe
as the real exit-code hazard.

### `exec` is the default; `run --rm` is for one-shots

`exec` (~instant) reuses the running container. `run --rm` (4.8s) starts a fresh
one, gated on the same dependencies, and does not publish ports — so it is the
safe path when `dashboard` is not running, when the target is the exited
`bootstrap` service, or when a command should not touch the serving container.

### `docker compose cp` documented, but fenced

The round trip works, and because `paca` is installed editable with a
short-lived CLI, a copied-in `.py` takes effect on the next invocation. It is
genuinely the fastest inner loop for a one-line fix. It is also exactly how an
agent ends up reporting a pass on code that is not in the image. The skill
presents it as an explicitly-labelled escape hatch with a mandatory
"rebuild before you report" step, never as the default.

### Evidence standard

"It ran without error" is not verification. The skill requires evidence tied to
the change: a row in the table the code writes, an HTTP status plus a content
assertion, or a specific log line. The `paca knowledge review` → `psql` probe is
included as the worked example because it is model-free and completes instantly.

## Risks / Trade-offs

- **The macOS column is now essentially verified.** Container-side facts carry
  over unchanged because the image is identical. During task 7.1 the whole POSIX
  column was executed in Git Bash on this host — pipeline exit semantics
  (`PIPESTATUS=(1 0)`, pipeline exit `0`), `curl -fsS -o /dev/null -w
  '%{http_code}'`, `shasum -a 256`, and the readiness poll — and that is real
  bash with POSIX-identical semantics in zsh. The only untested assumption left
  is that a macOS user runs zsh rather than an opted-in bash, which is
  inconsequential: the guidance deliberately avoids the one divergence in scope
  (`PIPESTATUS` vs `pipestatus` indexing) by using neither. This risk is
  effectively retired.
- **Snapshot facts go stale.** Timings, table names, and the LLM map are true of
  the stack as probed. Mitigated by adding a doc-sync row (compose/Dockerfile/
  `.dockerignore`/LLM-invoking code → this skill) so `code-review` catches drift,
  and by pointing at commands (`\d <table>`) rather than transcribing schemas —
  the probe itself was bitten by a guessed column name (`due_at` vs `next_due_at`).
- **Overlap with `docs/containerized-deployment.md`.** Two documents describing
  one stack will diverge. Accepted because the audiences differ; contained by
  making the skill link rather than restate, and by limiting the doc edits to
  marking host-specific sections and cross-linking.
- **Skill-count creep.** A second skill is more for an agent to route between.
  Accepted: the trigger ("verify in Docker") is distinct from `code-review`'s
  ("review this diff"), and they compose — review finds the problem, docker-verify
  proves the fix.
- **The LLM map is a safety claim.** It came from grepping `build_from_name` /
  `get_model` / `get_embedder` across `src/paca/` (`collectors/` has zero hits,
  which is what makes `info-radar pull` safe). A new model call added to a
  currently-safe path would silently invalidate it — hence that path is named
  explicitly in the doc-sync row.
