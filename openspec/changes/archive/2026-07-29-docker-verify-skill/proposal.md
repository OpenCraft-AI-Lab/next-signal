## Why

`CLAUDE.md` mandates that all runtime / end-to-end verification happen in Docker
rather than on the host, but the repo ships no guidance on *how* to navigate the
running stack. An agent handed that rule has to rediscover the container layout
every session, and the failure mode is silent: because `/app` is baked into the
image and not bind-mounted, an agent that edits `src/` and immediately re-runs
`docker compose exec` verifies **stale code** and reports a false pass.

A live probe of the running stack (2026-07-28, Windows host) confirmed that trap
plus a dozen more — a login shell that erases `paca` from `PATH`, a `paca doctor`
that exits non-zero by design, and a `docker compose build` that leaves the
running container on the previous image. None of this is discoverable from
`docker-compose.yml` alone, and `docs/containerized-deployment.md` is written for
an operator on macOS, not for an agent verifying a diff.

## What Changes

- **New agent skill** `.claude/skills/docker-verify/SKILL.md` — how to reach the
  DB, dashboard, and CLI inside the containerized stack, which loop to use for a
  given kind of edit, and how to confirm a change actually landed.
- **Rebuild/recreate decision matrix** — the core content: which host paths are
  live (`/wiki`, `/wiki-raw`, `/state`), which are baked (`/app`: `src/`,
  `configs/`, `prompts/`, `dashboard/`), and which are ignored entirely
  (`tests/`, `docs/`, `openspec/` per `.dockerignore`). Includes the
  `build` → `up -d` and `.env` → `up -d --force-recreate` rules.
- **LLM-cost safety map** — an explicit list of which `paca` subcommands and
  which dashboard controls spawn model calls, so an agent can verify plumbing
  without burning tokens. Derived from the code, not guessed.
- **Cross-platform host-shell guidance** — the container-side facts are identical
  everywhere, but the host quoting/HTTP/hashing idioms differ. The skill carries
  a two-column macOS/Linux vs. Windows PowerShell table for the commands an agent
  actually types, covering the shared hazard classes (host-side `$` expansion,
  early-pipe-exit corrupting exit codes).
- **`CLAUDE.md` pointer** — the 测试 section's "验证走 Docker" rule gains a link to
  the skill so the rule and its how-to are connected.
- **Reconcile `docs/containerized-deployment.md`** (+ its `docs/zh/` mirror) —
  mark the host-specific parts as such and cross-link the skill, keeping both
  language versions in step per the repo's bilingual rule.

No application code, container image, or compose topology changes. This change is
documentation and agent tooling only.

## Capabilities

### New Capabilities

- `core-container-verification`: the contract the containerized stack offers to
  anything verifying against it — which source paths are live vs. image-baked,
  which commands are guaranteed free of model calls, how to reach each service,
  and what counts as evidence that a change landed.

### Modified Capabilities

None. No existing requirement changes behavior; this change documents and
constrains what the stack already does.

## Impact

- **Added**: `.claude/skills/docker-verify/SKILL.md`;
  `openspec/specs/core-container-verification/` (on archive).
- **Edited**: `CLAUDE.md` (one pointer in the 测试 section);
  `docs/containerized-deployment.md` and `docs/zh/containerized-deployment.md`
  (host-specificity notes + cross-link).
- **Unchanged**: `Dockerfile`, `docker-compose.yml`, `scripts/container_bootstrap.sh`,
  all of `src/` and `dashboard/`. Nothing ships differently.
- **Risk**: the skill asserts facts about a live system, so it goes stale if the
  compose topology, `.dockerignore`, or the set of LLM-invoking commands changes.
  Mitigated by adding it to the `code-review` skill's doc-sync map.
- **Verification asymmetry**: every claim was probed on a Windows host against
  the real stack. Container-side claims are OS-independent (same Linux image), but
  the macOS host-shell column is derived from shell semantics rather than
  observed, and is flagged as such in `design.md`.
