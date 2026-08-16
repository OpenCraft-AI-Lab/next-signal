## 1. Credential store core

- [x] 1.1 Add `src/next_signal/core/secrets.py`: `CREDENTIAL_NAMES` (the seven names), `load_secrets()`, `get_secret(name)`, `require_secret(name)`, `save_secret(name, value)`, `delete_secret(name)`. Path is `STATE_ROOT / "secrets.json"`. Absent file reads as an empty store; present-but-unparseable or non-string values raise `RuntimeError` naming the file.
- [x] 1.2 Implement the atomic write: temp file in the same directory carrying pid + uuid, `chmod 0600` before `os.replace`. Mirror the collision reasoning already documented in `dashboard/lib/state-file.ts`.
- [x] 1.3 Add `child_env(names)` to `core/secrets.py`: copy `os.environ`, overlay the named credentials read now, omit any that are absent, and return the dict. It must never write to `os.environ`.
- [x] 1.4 `tests/test_secrets.py`: absent file → empty; malformed file → `RuntimeError`; round-trip save/read; atomic replace leaves no temp file; `child_env` omits absent names and leaves `os.environ` unmodified. Use `tmp_path` + `monkeypatch.setenv("NEXT_SIGNAL_STATE_DIR", ...)`, no mocks.

## 2. Python credential consumers

- [x] 2.1 `core/omlx.py`: resolve `api_key` from the store instead of `os.environ`, keeping `OMLX_BASE_URL` on the environment and `OMLX_API_KEY` optional.
- [x] 2.2 `core/models.py::_build_deepseek`: read `DEEPSEEK_API_KEY` from the store; keep `DEEPSEEK_BASE_URL` on the environment (F4 moves it).
- [x] 2.3 `core/models.py`: pass `api_key=` explicitly in `_build_claude`, `_build_openai`, and `_build_gemini`, raising `RuntimeError` naming the credential *before* constructing the model, so agno's internal `getenv` fallback can never resolve one.
- [x] 2.4 `core/models.py::_required_credential`: read from the store; rewrite the message to point at Settings instead of `.env` + restart.
- [x] 2.5 `integrations/knowledge/github.py`: read `GITHUB_TOKEN` from the store at both call sites; anonymous fallback when absent is unchanged.
- [x] 2.6 `integrations/info_radar/folo.py`: require `FOLO_TOKEN` from the store and raise before spawning when absent; pass `env=child_env(["FOLO_TOKEN"])` on all three `subprocess.run` call sites.
- [x] 2.7 `core/secrets.py` write path calls `next_signal.core.models.reset_cache()` so `_build`'s `lru_cache` cannot hold a superseded credential. Keep the import local to avoid a `core` import cycle.
- [x] 2.8 Verify no credential name is read from the environment anywhere: `grep -rn "ANTHROPIC_API_KEY\|OPENAI_API_KEY\|GOOGLE_API_KEY\|DEEPSEEK_API_KEY\|OMLX_API_KEY\|GITHUB_TOKEN\|FOLO_TOKEN" src/` returns only store reads, `CREDENTIAL_NAMES`, and `child_env` call sites.
- [x] 2.9 Extend the integration smoke tests for the touched adapters: a missing credential raises naming the credential, and the message points at Settings.

## 3. CLI diagnostics

- [x] 3.1 `interfaces/cli.py::doctor`: report credential presence from the store for each of the seven; drop the `.env`-and-restart guidance from the messages.
- [x] 3.2 `interfaces/cli.py::_check_embedder`: read the selected provider's credential from the store; keep `OMLX_API_KEY` optional.
- [x] 3.3 `interfaces/cli.py::_check_folo`: fail when `FOLO_TOKEN` is absent from the store, and stop describing a cached session as sufficient.
- [x] 3.4 Confirm `doctor` prints no credential value or fragment on any path.

## 4. Dashboard state layer

- [x] 4.1 `dashboard/lib/state-file.ts`: add an optional mode so callers can write `0600`; existing callers keep current behavior.
- [x] 4.2 Add `dashboard/lib/secrets.ts`, the TS mirror of `core/secrets.py` — same file path, same name set, same strictness — following the `embedding-preferences.ts` mirror convention.
- [x] 4.3 Add `dashboard/lib/actions/secrets.ts`: `getCredentialPresence()` returning `Record<name, boolean>`, `saveCredential(name, value)`, `deleteCredential(name)`. No action returns a credential value.
- [x] 4.4 `dashboard/lib/secrets.test.ts`: parse strictness, presence mapping, and that no value is ever included in a returned payload.

## 5. Dashboard UI

- [x] 5.1 Add `dashboard/components/settings/credentials-section.tsx`: one write-only control per credential, presence indicator, save + clear, toast on success, rollback on failure — matching the commit-acknowledgement contract of the existing sections.
- [x] 5.2 Each control names what breaks while the credential is unset.
- [x] 5.3 `dashboard/app/settings/page.tsx`: resolve presence server-side via the new action; drop the `process.env.DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `embedding.openaiCompatible.apiKeyEnv` probes.
- [x] 5.4 `engine-section.tsx` and `embedding-section.tsx`: keep the presence indicator, point it at the Credentials section, and remove the "edit `.env`, then restart / recreate" copy.
- [x] 5.5 `dashboard/lib/i18n/dictionaries.ts`: new Credentials strings and revised engine/embedding strings, **both locales**; remove the two existing `.env` sentences at the English and Chinese entries.
- [x] 5.6 Reuse existing design-system primitives; add no `/design` entry.

## 6. Folo browser sign-in

> Ships as its **own commit**, on top of groups 1-5. Everything above must be
> complete and working with manual entry before this group starts, so the sign-in
> is reviewable and revertable on its own.

- [x] 6.1 Add `dashboard/lib/folo-auth.ts`: build the sign-in URL with `cli_callback` pointing at the dashboard's own callback route, exchange the returned one-time token for a session token via Folo's one-time-token endpoint, and read the session token from the response. Keep the whole handshake in this one module so a contract change is one edit.
- [x] 6.2 Add the callback route under `dashboard/app/api/folo/`: accept the one-time token, run the exchange, write the session token to the credential store, and return no token in any response.
- [x] 6.3 Bound the flow: same-origin only, one attempt in flight, a time limit, and cancellation — matching the constraints the coding-agent auth endpoints already work under.
- [x] 6.4 Add an HTTPS domain allowlist for the sign-in target; never render an unapproved URL as a navigation target.
- [x] 6.5 Wire the Folo control in the Credentials section: a Connect action, bounded progress, cancel, and a plain error on failure — with the manual input still present and equally usable.
- [x] 6.6 Sign-in strings in `dictionaries.ts`, both locales.
- [x] 6.7 `dashboard/lib/folo-auth.test.ts`: URL construction, allowlist rejection, exchange-failure handling, and that no token appears in any returned payload.
- [x] 6.8 Confirm a failed or cancelled sign-in leaves the credential store untouched and manual entry working.

## 7. Configuration and deployment

- [x] 7.1 `.env.example`: delete the credential entries (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY`, `OMLX_API_KEY`, `GITHUB_TOKEN`, `FOLO_TOKEN`) and the prose that describes them as the configuration path; keep `OMLX_BASE_URL` and `DEEPSEEK_BASE_URL` with a note that F4 moves them.
- [x] 7.2 `docker-compose.yml`: make `env_file` non-required (`- path: .env` + `required: false`) so a fresh clone starts with no `.env`; confirm every Compose substitution still has a default.
- [x] 7.3 Confirm no credential is passed through the `environment:` block of any service.

## 8. Documentation (English + Chinese mirrors)

- [x] 8.1 `docs/operations.md` + `docs/zh/operations.md`: rewrite the credential table to point at Settings; correct the doctor section; drop `~/.folo/config.json` as an auth path; document Folo sign-in plus manual entry; remove the restart-after-`.env` guidance for credentials.
- [x] 8.2 `docs/containerized-deployment.md` + `docs/zh/containerized-deployment.md`: first run needs no `.env`; credentials are entered in the dashboard; `/state/secrets.json` joins the documented state-volume contents.
- [x] 8.3 `docs/modules/core.md` + `docs/zh/modules/core.md`: document `core/secrets.py`, the single-source rule, and `child_env`.
- [x] 8.4 `CLAUDE.md`: add the credential-store rule to the configuration section — credentials in the store, never `.env`, never `os.environ`, never logged.

## 9. Verification in Docker

- [x] 9.1 `uv run pytest -q` green on the host; `uv run ruff check src` clean.
- [x] 9.2 `docker compose build`, then `docker compose up` in a tree with **no** `.env` file — the stack starts.
- [x] 9.3 `docker compose exec dashboard next-signal doctor` — every credential check reports ✗ with a Settings pointer and no value printed.
- [x] 9.4 Save a credential in Settings → Credentials; confirm `/state/secrets.json` exists with mode `0600` and that the page reports presence with no value in the payload.
- [x] 9.5 Confirm cross-container liveness: with the `scheduler` container left running, save a credential from the dashboard and observe the scheduler resolve it on its next use — no restart, no `--force-recreate`.
- [x] 9.6 `docker compose exec scheduler env` — no credential appears in the container environment.
- [x] 9.7 With `FOLO_TOKEN` saved, `docker compose exec dashboard next-signal info-radar subscriptions --json` succeeds; with it cleared, it fails naming the credential before spawning folocli.
- [x] 9.8 Folo sign-in end to end against a real account: Connect writes the session token to the store, the page shows presence with no token in the payload, and `info-radar subscriptions --json` then succeeds. Requires a real Folo login — cannot be verified with fixtures alone. **Verified manually by the operator against a real Folo account.**
