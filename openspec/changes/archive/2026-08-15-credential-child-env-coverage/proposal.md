## Why

The `core-credentials` spec's "Child processes receive credentials only when
named" requirement was satisfied on paper but missed a real failure shape: it
reads naturally as covering the case where *our code* reads a credential and
hands it to a child. It does not say anything explicit about the case where
*our code spawns a third-party program that reads its own credential from
whatever environment it inherits* — our module never names the credential at
all, so a plain grep for credential names finds nothing wrong.

That gap shipped two real bugs on the `credential-store` branch:
`src/next_signal/integrations/gbrain.py`'s `gbrain_env()` and
`dashboard/lib/actions/knowledge.ts`'s `searchKnowledge()` both built a
subprocess environment with a blind `os.environ.copy()` / `{...process.env}`
for a spawn of the external `gbrain` binary, which reads `OPENAI_API_KEY` from
its own environment to authenticate its `embed` step. A stale, comment-poisoned
`.env` value rode that unscoped copy straight into gbrain's subprocess and was
sent as an invalid `Bearer` token. Both were fixed directly (commits `1212800`,
`668645d`) by routing through `child_env(["OPENAI_API_KEY"])` (Python) and a
`gbrainEnv()` mirror (TS).

The archived `credential-store` change's own design doc explains why this was
missed: its consumer survey named exactly one instance of "a child process
reads a credential from its own environment" (`folo.py`) and its rationale for
the `child_env` pattern asserted `gbrain_env()` "already build[s] child
environments explicitly" — which was false at the time. That incorrect premise
is why `gbrain.py` never appeared in the original task list. The spec itself
must close this gap explicitly, in the repo, where it is visible to any
developer — not just recorded in one assistant's private memory.

## What Changes

- Tighten `core-credentials`'s "Child processes receive credentials only when
  named" requirement so it explicitly covers both failure shapes: our code
  reading a credential, and our code spawning a third-party program that reads
  a credential-shaped variable from its own inherited environment.
- Add a requirement that every subprocess spawn must either (a) omit `env`
  entirely — only correct when the target program needs no credential, and
  that must be verified, not assumed — or (b) build its environment through a
  scoped child-env helper that strips every known credential name before
  re-adding only the ones the call site names.
- Add a scenario using the actual gbrain incident shape (a spawned external
  binary that reads a credential-shaped variable on its own) so the
  requirement is checkable against a concrete case, not just the abstract rule
  already on the books.

No code changes: `gbrain.py` and `knowledge.ts` already conform after the two
fix commits. This change brings the spec's contract up to what the
implementation already does, so the next developer (or agent) auditing a new
integration has the closed version of the rule in the repo, not just in a
private memory file.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `core-credentials`: the "Child processes receive credentials only when
  named" requirement gains explicit coverage of third-party programs that read
  their own credential from an inherited environment, plus a scenario for that
  failure shape.

## Impact

- **Spec only**: `openspec/specs/core-credentials/spec.md` (delta in this
  change, synced on archive). No source files change.
- Verification is that the current code already satisfies the tightened
  requirement (`src/next_signal/integrations/gbrain.py::gbrain_env`,
  `dashboard/lib/actions/knowledge.ts::gbrainEnv`), not new implementation
  work.
