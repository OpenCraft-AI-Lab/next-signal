#!/usr/bin/env sh
# Container-only bootstrap for the cloud-LLM docker stack (see
# docs/containerized-deployment.md). Runs on the `bootstrap` compose service,
# gated on Postgres health. Idempotent — safe to re-run on every `up`.
#
# 1) next-signal's main Postgres schema (pgvector + business tables).
# 2) gbrain's dedicated database, using its POSTGRES engine, plus migrations for
#    a brain that already exists. Creating the brain itself is NOT done here —
#    see the block below. The bun-compiled gbrain binary can't run PGLite
#    (extension bundles aren't embedded), and pgvector already ships `vector` +
#    `pg_trgm`, so gbrain lives in its own DB on the same server.
# 3) the runtime goals file on the state volume, if it isn't there yet.
set -eu

echo "[bootstrap] next-signal main DB schema"
python scripts/bootstrap_db.py

# Goals are user data on the shared state volume, not image content. Provisioning
# here rather than from a read path keeps `load_goals` a pure read; the step is a
# no-op once the file exists, including when it holds a deliberately empty list.
echo "[bootstrap] info-radar goals file"
python -m next_signal.workflows.info_radar_analysis.provision

if [ -n "${GBRAIN_DATABASE_URL:-}" ]; then
  echo "[bootstrap] gbrain database (Postgres engine)"
  # Create the gbrain database if absent (maintenance connection = main DB),
  # reusing bootstrap_db.py's create_database_if_missing instead of
  # reimplementing the CREATE DATABASE logic here.
  python - <<'PY'
import os, sys, urllib.parse

sys.path.insert(0, "scripts")
from bootstrap_db import create_database_if_missing

name = urllib.parse.urlparse(os.environ["GBRAIN_DATABASE_URL"]).path.lstrip("/")
create_database_if_missing(os.environ["DATABASE_URL"], name)
PY

  # This script handles NO credential, and deliberately does NOT create the
  # brain. Creating it needs an embedding model, and gbrain sizes its Postgres
  # schema from that model at init time — the choice is permanent. A brain made
  # with `--no-embedding` cannot be completed later: `gbrain config set
  # embedding_model` is a no-op on this engine, and `gbrain init --force
  # --embedding-model` exits 0 while silently leaving the brain deferred. So an
  # init here would lock in a choice before anyone can make it.
  #
  # Nor can the model's credential be supplied here. Bootstrap runs before one
  # can exist: the store is written by the dashboard, and the dashboard does not
  # start until this script exits 0. Reading it — even conditionally, "if one
  # happens to be set" — would put credential handling back into a file that
  # cannot reach `next_signal.core.secrets`. A shell-side copy of those helpers
  # is exactly what drifted before: this block used to claim it mirrored
  # `gbrain_env()` while omitting the credential injection that function had
  # gained, so gbrain inherited an environment that by design holds nothing.
  #
  # Only the DATABASE_URL handling is mirrored: set GBRAIN_DATABASE_URL and drop
  # DATABASE_URL so gbrain never touches the main DB. Migrating an existing
  # brain needs no credential, so that keeps running on every boot.
  # Do not "fix" this by reintroducing a key or a reduced init.
  GBRAIN_HOME="${GBRAIN_HOME:-/state/gbrain}"
  if [ -f "$GBRAIN_HOME/.gbrain/config.json" ]; then
    echo "[bootstrap] gbrain migrations"
    env -u DATABASE_URL \
        GBRAIN_HOME="$GBRAIN_HOME" \
        GBRAIN_DATABASE_URL="$GBRAIN_DATABASE_URL" \
        gbrain init --migrate-only
  else
    echo "[bootstrap] gbrain not initialised — knowledge search is unavailable."
    echo "[bootstrap]   initialise it with an embedding model of your choosing:"
    echo "[bootstrap]   next-signal knowledge gbrain-init --embedding-model <provider>:<model>"
  fi
fi

echo "[bootstrap] complete"
