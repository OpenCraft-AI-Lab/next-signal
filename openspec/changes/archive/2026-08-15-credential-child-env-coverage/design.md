## Context

See proposal.md — Why. This is a spec-only change: the code already conforms
(commits `1212800`, `668645d` on `credential-store`). The only design question
is how to phrase the tightened requirement so it is checkable by a future
reader — human or agent — auditing a *new* integration, not just a retrospective
description of the gbrain incident.

## Goals / Non-Goals

**Goals:**

- State the rule so it is testable against source, not just against intent:
  a reviewer should be able to look at any `subprocess.run` / `execFile` /
  `spawn` call site and determine conformance without needing to know whether
  the target program happens to read a credential today.
- Keep the requirement capability- and language-neutral. `core-credentials`
  already covers both the Python store (`core/secrets.py`) and its TS mirror
  (`dashboard/lib/secrets.ts`) under one capability; the tightened wording
  should too, so no parallel requirement is needed in `core-integrations` or
  `dashboard-shell` for the same rule.

**Non-Goals:**

- No new automated check (e.g., a lint rule or CI grep) — the spec update
  itself is the artifact this change ships. Automating the check is a
  separate, later concern if it proves worth the cost.
- No enumeration of every current subprocess spawn site in the spec. The
  requirement is general; `docs/modules/*.md` or code comments are the place
  for a call-site inventory, not the spec.

## Decisions

### State the rule as "unmodified environment copy handed to a program that might read a credential is the defect shape," not "every credential name must be grepped"

**Chosen:** the MODIFIED requirement adds explicit language that the rule
applies "regardless of whether the spawning module itself reads or names the
credential," and that `os.environ.copy()` / `{...process.env}` handed
unmodified to an external program is non-conforming when that program might
read a credential — independent of whether a grep of the spawning module's
source finds a credential name.

**Alternative considered — leave the existing requirement text alone and rely
on the incident being recorded only in `design.md`/memory.** Rejected: this is
exactly what happened the first time. The archived change's own design doc
recorded the `folo.py` instance of this failure shape but the *requirement
text itself* stayed general enough that `gbrain.py`'s non-conforming
`os.environ.copy()` read as compliant on inspection, because nothing pointed a
reviewer at the "third party reads its own credential" failure mode
specifically. A requirement that only future design docs would carry the
lesson is not enforceable against a *new* integration written by someone who
never reads this change's design.md.

### Two new scenarios, not one

**Chosen:** one scenario states the positive requirement (a third-party
program reading its own credential must still get a scoped environment), and
one states the negative check explicitly (an unscoped copy is a defect
*regardless of grep results*) — because the grep-passes-but-is-wrong outcome is
precisely what let this ship, it is worth a scenario of its own rather than
leaving it implied by the first.

### No code or task-list changes

**Chosen:** `tasks.md` records verification against the already-fixed code,
not new implementation steps. Both call sites already build their environment
through `child_env()` / `gbrainEnv()`, confirmed by the existing test suites
(`tests/test_knowledge_adapters.py`, `dashboard/lib/radar-ingest.test.ts`-style
coverage was not added for `gbrainEnv` itself, which the tasks note as a
pre-existing gap out of scope for a spec-only change).

## Risks / Trade-offs

- **A stricter requirement text does not, by itself, prevent a third
  instance.** Mitigated only by being explicit and example-driven enough that
  a reviewer (human or agent) reading `core-credentials` before writing a new
  integration sees the exact failure shape named, not just the abstract rule.
  A lint/grep check remains future work, not this change.
- **Spec churn for a requirement that did not change in effect.** Accepted:
  the requirement's *intent* was always this broad; the text was ambiguous
  enough to miss the case in practice, which is itself the defect being fixed.
