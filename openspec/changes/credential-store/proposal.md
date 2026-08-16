## Why

A new user still cannot start next-signal without opening a text editor: every
provider credential lives in `.env`, and no dashboard control can set one. This
is the last blocking gap in the setup flow — goals and wiki mounts already moved
to user state, so credentials are what remains between a fresh clone and a stack
configured entirely from the browser.

Editing `.env` is also the wrong shape for a running stack. `dashboard` and
`scheduler` are separate containers; a key added to `.env` reaches neither until
`docker compose up -d --force-recreate`, because a process's environment is
fixed at fork. Moving credentials to a state file on the shared volume, read at
call time, removes the recreate step entirely.

## What Changes

- **New credential store.** One file, `$NEXT_SIGNAL_STATE_DIR/secrets.json`, flat
  `NAME → value`, written atomically at mode `0600`. Keys keep their existing
  environment-variable names because child processes require the literal string.
- **New Settings → Credentials section.** Write-only inputs for all seven
  credentials. Only a presence boolean crosses to the browser; no credential
  value is ever sent to the client, and no masked preview or last-4 is rendered.
- **Every credential read moves to the store.** `ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY`, `OMLX_API_KEY`,
  `GITHUB_TOKEN`, `FOLO_TOKEN`. The agno model constructors receive `api_key=`
  explicitly and raise before construction when it is absent, so agno's own
  `getenv` fallback can never resolve a credential behind our back.
- **Child processes get credentials per spawn, not per process.** A
  `child_env(names)` helper reads the store at spawn time and returns the
  environment for one subprocess. Nothing mutates `os.environ`, so no credential
  reaches a child that did not name it. This is the third instance of an existing
  convention (`gbrain_env`, `build_child_env`), not a new abstraction.
- **BREAKING: credential environment variables are no longer read anywhere.**
  There is no migration, no import action, and no environment fallback —
  deliberately, since the repo has no deployed users. After this change, reading
  a credential env var is a defect, which makes the rule checkable by grep.
- **BREAKING: folocli's session file is no longer a supported auth path.** The
  store becomes the only source for `FOLO_TOKEN`, and `folo.py` raises with a
  remediation pointing at Settings before spawning. `~/.folo/config.json` is
  unreachable in the container anyway: no volume backs `/root/.folo`, and
  `folocli login` completes over a loopback callback on an ephemeral port that a
  browser on the host cannot reach inside a container.
- **Browser sign-in for the Folo token.** Folo has no "create API token" page —
  its token is a better-auth session value, so the only manual routes are copying
  a browser cookie or running `folocli login` on the host and reading its config
  file. A paste box alone would therefore leave this credential exactly as
  hand-extracted as it is today. The dashboard hosts the callback itself, which
  works because it is published on the host loopback even though the container is
  not, and writes the resulting session token to the store. The paste box stays
  as the fallback for every credential including this one.
- **`.env` sheds every credential.** Combined with making Compose's `env_file`
  non-required, a first run needs no `.env` file at all in the Docker path.
  Endpoint variables (`OMLX_BASE_URL`, `DEEPSEEK_BASE_URL`) stay for now and move
  in F4; system connection config (`DATABASE_URL`, `GBRAIN_*`, `POSTGRES_*`,
  `*_BIN`, CLI version pins) stays permanently.

Deliberately out of scope: the readiness banner (F5) and the embedding
configuration rework (F4). `api_key_env` keeps its name and continues to identify
the credential — it simply resolves from the store rather than the environment.
F4 replaces the field itself.

## Capabilities

### New Capabilities
- `core-credentials`: the credential store — file location, format, permissions,
  atomic write, call-time resolution, the single-source rule, and the per-spawn
  child-environment helper.

### Modified Capabilities
- `core-models`: OMLX `api_key` no longer comes from `.env`; cloud provider
  constructors receive an explicit `api_key` and raise when it is missing; the
  model cache is invalidated when the store is written.
- `core-embedding`: the OpenAI and compatible providers resolve their credential
  from the store; the "edit `.env` then restart" semantics are replaced by
  call-time resolution; doctor's embedder credential check reads the store.
- `core-integrations`: the integration credential convention changes from
  `_helpers.env(NAME)` to a store read; `env()` remains for non-credential
  configuration only.
- `core-cli`: `doctor` reports credential presence from the store rather than the
  environment, and the folocli check no longer accepts a cached session as auth.
- `knowledge-pipeline`: the GitHub fetcher reads its token from the store;
  anonymous fallback when unset is unchanged.
- `dashboard-shell`: adds the Credentials settings section and its write-only
  contract, plus the assisted Folo browser sign-in and its callback; removes the
  restart-after-`.env`-edit guidance from the existing credential-presence
  requirements.
- `core-container-verification`: the stack starts with no `.env` file present,
  not merely an unedited one.

## Impact

- **New**: `src/next_signal/core/secrets.py`; `dashboard/lib/secrets.ts` mirror;
  `dashboard/lib/actions/secrets.ts`; `dashboard/components/settings/credentials-section.tsx`;
  `dashboard/lib/folo-auth.ts` and a dashboard callback route for the Folo
  sign-in.
- **Modified**: `core/models.py`, `core/omlx.py`, `core/embedding_preferences.py`,
  `integrations/knowledge/github.py`, `integrations/info_radar/folo.py`,
  `interfaces/cli.py` (doctor), `dashboard/lib/state-file.ts` (needs a mode
  option — it cannot produce `0600` today), `dashboard/app/settings/page.tsx`,
  `dashboard/components/settings/{engine,embedding}-section.tsx`,
  `dashboard/lib/i18n/dictionaries.ts` (both locales).
- **Config / deployment**: `.env.example` loses its credential block;
  `docker-compose.yml` marks `env_file` not required.
- **Docs**: `docs/operations.md`, `docs/containerized-deployment.md`,
  `docs/modules/core.md`, and the three Chinese mirrors under `docs/zh/`.
- **Unblocks**: F4 (embedding configuration completeness), which needs the store
  for its API-key field, and then F5 (readiness signal), which reads it.
