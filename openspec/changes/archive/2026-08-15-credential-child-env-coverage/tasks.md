## 1. Spec delta

- [x] 1.1 Write the `core-credentials` MODIFIED requirement tightening "Child
      processes receive credentials only when named" to explicitly cover a
      third-party program reading its own credential from an inherited
      environment.
- [x] 1.2 Add the two new scenarios: a third-party program reading its own
      credential is still scoped, and an unscoped environment copy is a defect
      regardless of grep results.

## 2. Verify the current code already conforms (no implementation expected)

- [x] 2.1 Confirm `src/next_signal/integrations/gbrain.py::gbrain_env` builds
      its subprocess environment through `next_signal.core.secrets.child_env`
      rather than an unscoped `os.environ.copy()` — already true as of commit
      `1212800`.
- [x] 2.2 Confirm `dashboard/lib/actions/knowledge.ts::searchKnowledge` builds
      its `gbrain` spawn's environment through the module-local `gbrainEnv()`
      helper (strips `CREDENTIAL_NAMES`, re-adds only `OPENAI_API_KEY` from the
      store) rather than a bare `process.env` — already true as of commit
      `668645d`.
- [x] 2.3 `grep -rn "os\.environ\.copy()\|{\.\.\.process\.env}" src/
      dashboard/lib dashboard/app` and confirm every remaining hit either
      spawns a program verified to need no credential (e.g. `opencli`,
      `yt-dlp`, coding-agent CLIs behind their own allowlists) or already
      builds its environment through a `child_env`-shaped helper. Swept:
      `core/secrets.py:194`, `radar-ingest.ts:195`, `knowledge.ts:50` are the
      scoped helpers' own base-copy-then-strip implementations; `opencli.py:160`
      needs no credential; `coding-agent-auth.ts:153/243`, `ingest/jobs.ts:114`,
      `actions/radar.ts:55`, `actions/spawn-cli.ts:47` all wrap the internal
      `uv run next-signal ...` CLI, which resolves credentials safely one layer
      down. No unscoped copy reaches a foreign credential-reading binary.
- [x] 2.4 `openspec validate credential-child-env-coverage --strict` passes.

## 3. Archive

- [ ] 3.1 Once reviewed, run the archive workflow to sync the `core-credentials`
      delta into `openspec/specs/core-credentials/spec.md`.
