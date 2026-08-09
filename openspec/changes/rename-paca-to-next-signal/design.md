## Context

`next-signal` already owns the outward-facing name: GitHub repo, `pyproject` dist name, Postgres database `next_signal`, state root `~/.next-signal`, dashboard brand marks. What is left is the identifier layer — Python package, CLI binary, `PACA_*` env prefix, dashboard cookies and launcher symbols. A full-repo scan (regex `(?<![A-Za-z])paca`, case-insensitive, which correctly skips the `alpaca` and `digitalpaca` substrings) finds **1483 occurrences in 235 files**; 179 of those in 38 files sit under `openspec/changes/archive/` and are excluded, leaving **1304 in 197 files**.

Two constraints shape the whole approach:

1. **The same token maps to two different targets.** `paca.core.db` must become `next_signal.core.db` (underscore — Python module), while `paca doctor` must become `next-signal doctor` (hyphen — console script). A single global find-and-replace is therefore wrong in both directions.
2. **`openspec/specs/dashboard-shell/spec.md` currently forbids this change.** It states that the `paca` name "SHALL remain unchanged as the Python package, the CLI binary, the `PACA_*` environment prefix, and the subprocess launcher symbols." That is a live requirement, written when the brand-icon work deliberately scoped itself to the visible layer. It has to be removed, not quietly contradicted.

The repo has no active changes and a clean working tree apart from four untracked skill directories, so this can land as one sequenced change.

## Goals / Non-Goals

**Goals:**

- Zero `paca` occurrences outside `openspec/changes/archive/` when the change is done.
- No behaviour change. Every edit is an identifier rename; pipelines, prompts, scoring, and the data model are untouched.
- The rename is mechanically reproducible and reviewable — a reviewer can re-run the transform and get the same diff, rather than trusting 197 hand edits.
- English and Chinese docs land together, per the repo's bilingual rule.
- The three operator migration steps that no script can perform are written down before implementation starts.

**Non-Goals:**

- Rewriting `openspec/changes/archive/**`. Archived changes describe what was true when they shipped; editing them would make them describe code that never existed under those names.
- Renaming the operator's external `digitalpaca-wiki` / `digitalpaca-wiki-raw` repositories. Only the two prose references inside this repo are neutralised.
- Keeping a `paca` alias or deprecation shim. There is one operator and one deployment; a compatibility layer would be permanent cost for a one-time cutover.
- Touching the `Alpaca*` mark names in `dashboard-shell`. Those are a different word and already appear only in a prohibition clause.

## Decisions

### Ordered, category-scoped transform instead of one global replace

A scripted rewriter applies disjoint patterns in a fixed order, each with a lookbehind that protects `alpaca` / `digitalpaca`:

1. `PACA_[A-Z_]+` → per-variable target from the mapping table. Uppercase, so it cannot collide with anything below.
2. `(?<![A-Za-z])paca\.` → `next_signal.` — imports, dotted module strings (`"paca.os_app:app"`, `__import__(f"paca.tools.…")`, monkeypatch targets), YAML `factory:` / `run_now:` / `tool_fn:` values, and dotted paths in prose.
3. `(?<![A-Za-z])paca/` → `next_signal/` — path prose such as `src/paca/tools/<domain>/`.
4. `(?<![A-Za-z/_-])paca(?=\s+(doctor|list|serve|dashboard|run-agent|run-workflow|knowledge|info-radar))` → `next-signal` — CLI invocations.
5. Whatever is left is reviewed by hand; it is bare prose mentions, `logTag` defaults, and `Dockerfile` / `docker-compose` / `launch.json` argv entries.

*Alternative considered:* `sed -i 's/paca/next-signal/g'`. Rejected — it produces `next-signal.core.db` (invalid Python), corrupts `digitalpaca-wiki`, and gives no way to distinguish module from command.

*Alternative considered:* 197 hand edits. Rejected — a rename this size is exactly where hand editing drops occurrences, and the transform is trivially verifiable by re-running the scan.

**Ordering constraint:** dashboard file and symbol renames (`spawn-paca.ts`, `spawnPacaDetached`) run **before** step 2, because `spawn-paca.ts` would otherwise match `paca\.` on its own extension.

### Domain names where a domain exists, `NEXT_SIGNAL_` where none does

The repo already has unprefixed domain env vars: `GBRAIN_BIN`, `FOLO_TOKEN`, `OPENCLI_BIN`, `INFO_RADAR_TIMEZONE`. `PACA_GBRAIN_HOME` sitting next to `GBRAIN_BIN` is the anomaly, not the pattern. So domain variables drop the prefix and process-global ones take `NEXT_SIGNAL_`.

*Alternative considered:* `NEXT_SIGNAL_*` for all thirteen. Simpler to review, but re-introduces the `NEXT_SIGNAL_GBRAIN_HOME` / `GBRAIN_BIN` mismatch.

*Alternative considered:* drop the prefix from all thirteen. Rejected because `STATE_DIR` and `LOG_LEVEL` are generic enough to be set by an unrelated tool in a shared shell or container environment, and both are read at import time in `core/paths.py` and `core/logging.py` where a wrong value fails confusingly.

### `ns_` cookie prefix rather than bare names

Cookies are scoped by host, **not** by port. On `localhost` the dashboard shares a cookie jar with every other local dev server, so a bare `locale` cookie is a real collision. `ns_locale` / `ns_recap_collapsed` keeps namespacing at two characters.

### Delta specs generated from the existing spec text, not retyped

All twenty live specs name `paca` in normative positions. Their deltas are produced by extracting each requirement block that contains the pattern, applying the same transform, and emitting it under `## MODIFIED Requirements`. OpenSpec replaces the whole requirement at archive time, so a delta must carry the complete block — generating it removes the transcription risk of copying long requirement bodies by hand.

`dashboard-shell` is the exception and is hand-written: its "the `paca` name SHALL remain unchanged" clause becomes a `## REMOVED Requirements` entry with a reason and migration note, since deleting a requirement is a judgement, not a substitution.

### Package renamed with `git mv`, not delete-and-recreate

`git mv src/paca src/next_signal` keeps rename detection intact, so the review diff shows 56 renames plus content edits rather than 112 add/delete pairs.

## Risks / Trade-offs

**An existing `pgdata` volume keeps the `paca` Postgres role** → `POSTGRES_USER` is only honoured by `initdb` on an empty data directory, so flipping the compose default breaks connections against a volume that already exists. Mitigation: a migration step runs `ALTER ROLE paca RENAME TO next_signal;` before the new default takes effect. Documented in the migration plan and in `docs/containerized-deployment.md` (both languages).

**The git-ignored `.env` needs a hand edit** → it sets `PACA_LOG_LEVEL`, `PACA_WIKI_DIR`, `PACA_WIKI_RAW_DIR`. Left alone, the first run after the rename fails with `RuntimeError: WIKI_DIR is required`. Mitigation: the loud failure is the intended behaviour (no silent default), and `docs/operations.md` carries the full mapping table. The rewriter **excludes `.env` by name** — see the next two risks for why letting it near operator values was a mistake.

**A separator does not end a word: `-paca` and `_paca` are not module paths** → the first implementation guarded the module rules with `(?<![A-Za-z])`, which permits a preceding `-`. Run against a machine whose home directory is `/Users/supreme-paca/`, it rewrote that path to `/Users/supreme-next_signal/` inside `.env`, pointing `WIKI_DIR` at a directory that does not exist. Mitigation: the module lookbehinds are `(?<![A-Za-z_-])`, and `.env` is excluded outright — operator values are arbitrary strings that happen to contain the word, not identifiers.

**Literal substitutions bypass the lookbehind that protects `digitalpaca`** → applying the literal table with plain `str.replace` let `paca-wiki-raw` match inside the operator's external repo name `digitalpaca-wiki-raw`, yielding `digitalns-wiki-raw` in seven files. Mitigation: literals are applied as guarded `re.sub` with the same `(?<![A-Za-z])` prefix as every other rule.

**The rewriter is one-shot, and a second run damages the migration guides** → those guides must print the old names beside the new ones, which is precisely what the transform removes. Mitigation: the script is **deleted** once the leftover report comes back clean. Keeping a tool in `scripts/` whose only remaining effect is to corrupt documentation is worse than losing it, and the transform itself is recorded above — that record, not the code, is the durable artifact.

**A partial transform leaves a half-renamed tree that still imports** → e.g. YAML `factory:` values are resolved at runtime, not import time, so a missed `configs/workflows/*.yaml` entry passes `pytest` collection and only fails when a workflow is invoked. The same holds for the `uvicorn` target in `cli.py`, the console-script target in `pyproject.toml`, and the env var names the dashboard hardcodes alongside Python's. Mitigation: `next-signal list` was the verification gate during implementation; mutation testing afterwards showed 18 of 28 rename surfaces had no automated cover, so `tests/test_shipped_refs.py` now resolves every string reference in the shipped tree. A manual gate catches the rename it was written for and nothing after it.

**Stale bytecode shadows the rename** → `src/paca/__pycache__` and `dashboard/.next` survive a `git mv` and can mask a broken import. Mitigation: remove both before verification, per the existing `CLAUDE.md` guidance on `.next` cache hygiene.

**Cookie rename silently resets operator UI state** → the dashboard falls back to the default English locale and an expanded recap panel once. Accepted: it is one click to restore, and versioned cookie names are not worth carrying for a single operator.

**Docs drift between EN and ZH** → 16 doc files in mirrored pairs, plus four READMEs. Mitigation: the transform runs over both trees in the same pass, and the per-file occurrence counts are compared pairwise afterwards.

## Migration Plan

Ordered so that each step is verifiable before the next depends on it:

1. **Env vars first.** Uppercase patterns are disjoint from everything else, so this lands cleanly on its own. Verify: no `PACA_` outside the archive.
2. **Package move + imports.** `git mv`, run the transform, `uv sync` to reinstall editable under the new module name. Verify: `uv run pytest -q` green, and `uv run next-signal list` resolves every workflow factory from YAML.
3. **CLI name.** Verify: `uv run next-signal doctor` runs and reports the same three known ✗ checks as before.
4. **Dashboard.** File and symbol renames, cookies, package name, tmpdir prefixes. Verify: `pnpm build` plus the three `lib/*.test.ts` suites that read the renamed env vars.
5. **Docs, both languages,** plus `CLAUDE.md` and `.claude/`. Verify: EN/ZH per-file counts match pairwise.
6. **Live specs.** Verify: `openspec validate --strict`.
7. **Container end-to-end,** following the `docker-verify` skill: rebuild the image (the source is baked in, not bind-mounted, so an un-rebuilt container verifies stale code), then `docker compose exec dashboard next-signal doctor` and a model-free `next-signal info-radar pull`.

**Operator steps outside the repo** — edit `.env`; run the `ALTER ROLE` above against an existing volume; expect the dashboard locale and recap panel to reset once.

**Rollback:** the whole change is one branch with no data migration beyond the reversible `ALTER ROLE`. Reverting the branch and running `uv sync` restores the previous state; the role rename reverses with the symmetric `ALTER ROLE next_signal RENAME TO paca;`.

## Open Questions

None blocking. Two decisions were taken by the owner before this document and are recorded in the proposal: the CLI is `next-signal` with no short alias, and `openspec/changes/archive/**` stays untouched.
