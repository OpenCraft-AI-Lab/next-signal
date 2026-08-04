## 1. Skill scaffold

- [x] 1.1 Create `.claude/skills/docker-verify/SKILL.md` with frontmatter matching
      `code-review/SKILL.md` conventions (`name`, `description`, `license: MIT`,
      `metadata.author: paca`, `metadata.version: "1.0"`). The `description` must
      carry the trigger phrasing an agent will match on — verifying a change in
      Docker, running the CLI/dashboard/DB in containers, checking whether the
      container is running current code.
- [x] 1.2 Write the opening framing: this stack is verified in containers per
      `CLAUDE.md`; link `docs/containerized-deployment.md` for topology and state
      that the skill covers navigation and evidence, not setup.

## 2. Core content — the rebuild/recreate matrix

- [x] 2.1 Write the "what did you edit → which loop" decision table from
      `design.md`, including measured timings (no-op build 3s, `up -d` 4.3s,
      `run --rm` 4.8s) so the rebuild loop is not mistaken for expensive.
- [x] 2.2 Document the three path classes with their evidence: live
      (`/wiki`, `/wiki-raw`, `/state`), image-baked (`/app` — `src/`, `configs/`,
      `prompts/`, `scripts/`, `dashboard/`), and excluded (`tests/`, `docs/`,
      `openspec/` per `.dockerignore`).
- [x] 2.3 Document the staleness check — compare `docker image inspect
      next-signal:latest --format '{{.Id}}'` against `docker inspect
      next-signal-dashboard-1 --format '{{.Image}}'` — and state the rule that
      `build` alone never updates a running container.
- [x] 2.4 Document `restart` vs `up -d` vs `up -d --force-recreate`, including
      that `restart` keeps the container ID so `.env` is not re-read.
- [x] 2.5 Document `docker compose cp` as an explicitly-labelled escape hatch for
      single-file Python/config edits, with the mandatory "rebuild before you
      report, it is lost on recreate" caveat.

## 3. Core content — access and safety

- [x] 3.1 Document service access: `exec -T` as default, `run --rm` for one-shots
      and for the exited `bootstrap` service, and the `service "bootstrap" is not
      running` error an agent will hit.
- [x] 3.2 Document DB access: Postgres is unpublished so inspection goes through
      `docker compose exec -T postgres psql -U paca -d next_signal`; `-d` is
      mandatory. Note the two databases (`next_signal`, `gbrain`), the six
      business tables, that agno tables are provisioned lazily and their absence
      is not breakage, and the rule to run `\d <table>` before writing a query.
- [x] 3.3 Write the LLM-cost safety map: model-free (`list`, `doctor`,
      `knowledge review`, `info-radar pull|sweep|subscriptions`, all dashboard
      pages, all `/api/radar/*` GETs) vs. model-invoking (`run-agent`,
      `knowledge ingest`, `run-workflow knowledge_ingest`, `info-radar analyze`,
      `info-radar recap`), plus the dashboard-control equivalents.
- [x] 3.4 Document the `sh -lc` PATH trap with the observed contrast, and the
      `paca doctor` exit-code semantics (non-zero by design under cloud-only;
      read the check lines, not the exit code).
- [x] 3.5 Document dashboard action observability: actions are detached and
      report "started" not "completed"; the log lives under the container's
      `$HOME` (`/root/.next-signal/dashboard-actions.log`), **not** `/state`, and
      does not survive recreate — so durable evidence comes from the DB.
- [x] 3.6 State the test boundary: no `tests/` and no runner in the image; unit
      tests run on the host via `uv run pytest`, containers are for runtime/E2E.

## 4. Cross-platform host-shell guidance

- [x] 4.1 Write the two-column macOS/Linux (zsh) vs Windows PowerShell idiom
      table (HTTP check, file hash, capture output, truncate output), stating
      that macOS means zsh — default since Catalina.
- [x] 4.2 Write hazard 1 — single-quote the remote command, because zsh, bash and
      PowerShell all expand `$VAR` in double quotes on the host; prefer
      `printenv` to avoid the shell entirely.
- [x] 4.3 Write hazard 2 as a **mirrored** hazard, not a shared one: through a
      truncating pipe, zsh/bash return the last command's status (`0` → false
      pass, the dangerous direction) while PowerShell returns the native
      command's (`255` → false fail). Give the one portable fix — redirect to a
      file, check the unpiped exit code — and do not document `pipefail` or
      `PIPESTATUS`/`pipestatus`, whose indexing differs between bash and zsh.
- [x] 4.4 State that `-T` is recommended for clean non-interactive output, and
      explicitly that it is *not* an exit-code fix — the pipe is.
- [x] 4.5 Mark what remains unverified on macOS (`curl`/`shasum` invocation
      detail, zsh-vs-opted-in-bash) so a later macOS session knows exactly what
      to confirm. The pipeline semantics are already verified and need no re-test.

## 5. Evidence standard

- [x] 5.1 Write the evidence rule: a clean exit is not verification. Require a
      row in the table the code writes, an HTTP status plus a content assertion,
      or a named log line.
- [x] 5.2 Include the model-free worked example end to end:
      `paca knowledge review` → `psql ... select ... from knowledge_reviews`.
- [x] 5.3 Include the dashboard readiness poll (retry `GET /radar` until 200)
      for use after a recreate, and the route/API smoke-check list.

## 6. Wiring and doc sync

- [x] 6.1 Add a pointer to the skill from `CLAUDE.md`'s
      「验证走 Docker（不在宿主机裸跑）」 section — one line, in Chinese, matching
      the surrounding style.
- [x] 6.2 Add a doc-sync row to `.claude/skills/code-review/SKILL.md`:
      `docker-compose.yml` / `Dockerfile` / `.dockerignore` / any new
      `build_from_name`|`get_model`|`get_embedder` call site →
      `.claude/skills/docker-verify/SKILL.md`.
- [x] 6.3 Update `docs/containerized-deployment.md` — mark host-specific guidance
      as such and cross-link the skill for change-verification workflows.
- [x] 6.4 Mirror 6.3 into `docs/zh/containerized-deployment.md` in the same
      change, per the bilingual rule. **Both language versions ship together.**

## 7. Verification

- [x] 7.1 Re-run every command the skill tells an agent to run, in the real
      stack, and confirm the documented output still matches. Fix any drift.
      *Drift found and fixed: the worked example printed `enrolled=0` on re-run
      (idempotent), not `enrolled=1` — the skill now shows both and uses the
      discrepancy to teach that the DB row, not the summary line, is the
      evidence. Also executed the full POSIX column in Git Bash (`curl`,
      `shasum`, readiness poll, pipeline exit codes), so the verification note
      and the design.md risk were both narrowed accordingly.*
- [x] 7.2 Confirm no application behavior changed: `git diff --stat` touches only
      `.claude/`, `CLAUDE.md`, `docs/`, and `openspec/` — no `src/`, `dashboard/`,
      `Dockerfile`, or `docker-compose.yml`. *Confirmed: 4 files, +29 lines, plus
      two new untracked dirs (`.claude/skills/docker-verify/`,
      `openspec/changes/docker-verify-skill/`).*
- [x] 7.3 Run `uv run pytest -q` on the host to confirm the suite is still green
      (expected: unaffected — this change ships no code). *338 passed, 13 skipped
      in 6.33s.*
- [x] 7.4 Run `openspec validate docker-verify-skill` and resolve any findings.
      *Valid; no findings.*
