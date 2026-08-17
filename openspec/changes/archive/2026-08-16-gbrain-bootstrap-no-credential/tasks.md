## 1. Establish the real behaviour first

- [x] 1.1 Confirm the failure: `docker compose -p nsfresh up` against a clean project (no existing `pstate`), expecting `bootstrap` to exit 1 on `gbrain init --non-interactive`. Keep the log — it is the before-state evidence.
- [x] 1.2 Establish what GBrain actually does in each state, before writing any handling: whether `--no-embedding` can be completed later, what `gbrain doctor --fast` reports with no brain, and what a search returns. Results are recorded in `design.md` → Resolved Questions and decide the design; do not write handling that contradicts them.

## 2. Bootstrap defers initialisation

- [x] 2.1 `scripts/container_bootstrap.sh`: remove the first-time `gbrain init` invocation entirely. When `$GBRAIN_HOME/.gbrain/config.json` is absent, print that GBrain is not initialised and name the command that initialises it, then exit zero.
- [x] 2.2 Keep `create_database_if_missing` and the `--migrate-only` branch untouched, so an already-initialised install still gets its migrations on every boot and is otherwise unaffected.
- [x] 2.3 Replace the stale "Mirror `next_signal.integrations.gbrain.gbrain_env`" comment: bootstrap deliberately mirrors only the `DATABASE_URL` handling and holds no credential at all. Say why deferral rather than `--no-embedding`, so neither the injection nor the reduced init is "restored" later as a fix.
- [x] 2.4 Verify: `grep -nE "API_KEY|TOKEN|secrets.json" scripts/container_bootstrap.sh` returns nothing.

## 3. The initialisation command

- [x] 3.1 `integrations/gbrain.py`: replace `embedding_disabled()` / `EMBEDDING_DISABLED_HINT` with a brain-initialised probe returning "initialised" / "not initialised" / "unknown", reading `$GBRAIN_HOME/.gbrain/config.json`. Keep the three-way return so callers can distinguish "not set up" from "could not tell".
- [x] 3.2 `integrations/gbrain.py`: make `gbrain_env()` inject the credential the **selected** provider needs, resolved from the configured embedding model, instead of always `OPENAI_API_KEY`. A local provider resolves to no credential and must work against an empty store.
- [x] 3.3 `interfaces/cli.py`: add `knowledge gbrain-init --embedding-model <provider>:<model> [--embedding-dimensions N]`. `--embedding-model` is required with no default; `--embedding-dimensions` is an optional override of GBrain's derived value. No force flag.
- [x] 3.4 `gbrain-init` refuses against an already-initialised brain, naming the model in use and changing nothing.
- [x] 3.5 Verify: `uv run pytest -q` green, plus a smoke test for the refusal path and one for a local provider resolving to no credential.

## 4. Report the uninitialised state

- [x] 4.1 `interfaces/cli.py::_check_gbrain`: report the three states — not initialised (naming `gbrain-init`), initialised but the selected provider's credential is absent (naming that credential), and ready. Do not delegate to `gbrain doctor`, which reports healthy and exits zero with no brain.
- [x] 4.2 `tools/knowledge/search.py`: raise naming the uninitialised brain rather than returning an empty list. Only a definite "not initialised" blocks; an indeterminate state proceeds with the search.
- [x] 4.3 Verify: `uv run pytest -q` green, and adapt the three tests in `tests/test_knowledge_search.py` to the new predicate.

## 5. Docs, both languages

- [x] 5.1 `docs/containerized-deployment.md` + `docs/zh/`: first run needs no credential; GBrain is not initialised at all, and knowledge search needs one explicit step.
- [x] 5.2 `docs/operations.md` + `docs/zh/`: the new `doctor` states, and how to choose a provider and run `gbrain-init` — including that the model choice is permanent and that local providers need no key.
- [x] 5.3 `docs/modules/knowledge.md` + `docs/zh/`: the uninitialised state, its loud-search contract, and the locked-at-init embedding model.
- [x] 5.4 `.claude/skills/docker-verify/SKILL.md`: update the expected fresh-stack `doctor` output to the uninitialised-GBrain line.
- [x] 5.5 Confirm no document still names `gbrain config set embedding_model` as the recovery, since it is a no-op on this engine.

## 6. Verify the real acceptance test

- [x] 6.1 `docker compose -p nsfresh down -v` then `docker compose -p nsfresh up -d` with an empty credential store: bootstrap exits 0, and `dashboard` and `scheduler` both reach Started. This is the change's reason for existing.
- [x] 6.2 `docker compose -p nsfresh exec dashboard next-signal doctor`: GBrain reports as uninitialised and names knowledge search; the stack is otherwise healthy.
- [x] 6.3 Confirm the dashboard answers on its port in that fresh project — the previously dead path now reachable.
- [x] 6.4 Run `gbrain-init` with a **local** provider against the empty store and confirm the command succeeds and injects no credential. This is the credential-free path; whether the resulting brain can actually reach the local runner and embed is out of scope (no endpoint configuration exists yet — see `proposal.md` Non-Goals), so do not require a working search here.
- [x] 6.5 Run `gbrain-init` with a cloud provider whose credential is saved, and confirm `doctor` distinguishes "initialised but not ready" before the key is saved from "ready" after.
- [x] 6.6 Confirm `gbrain-init` refuses on the now-initialised brain, naming the model in use.
- [x] 6.7 Re-run `docker compose up` on the developer's normal project to confirm the `--migrate-only` path is unchanged, then `docker compose -p nsfresh down -v` to remove the throwaway volume.
