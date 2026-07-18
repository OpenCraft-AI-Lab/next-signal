#!/usr/bin/env sh
# Container-only bootstrap for the cloud-LLM docker stack (see
# docs/containerized-deployment.md). Runs on the `bootstrap` compose service,
# gated on Postgres health. Idempotent — safe to re-run on every `up`.
#
# 1) paca's main Postgres schema (pgvector + business tables).
# 2) gbrain's dedicated database + one-time init, using its POSTGRES engine.
#    The bun-compiled gbrain binary can't run PGLite (extension bundles aren't
#    embedded), and pgvector already ships `vector` + `pg_trgm`, so gbrain lives
#    in its own DB on the same server.
set -eu

echo "[bootstrap] paca main DB schema"
python scripts/bootstrap_db.py

if [ -n "${PACA_GBRAIN_DATABASE_URL:-}" ]; then
  echo "[bootstrap] gbrain database + init (Postgres engine)"
  # Create the gbrain database if absent (maintenance connection = main DB),
  # reusing bootstrap_db.py's create_database_if_missing instead of
  # reimplementing the CREATE DATABASE logic here.
  python - <<'PY'
import os, sys, urllib.parse

sys.path.insert(0, "scripts")
from bootstrap_db import create_database_if_missing

name = urllib.parse.urlparse(os.environ["PACA_GBRAIN_DATABASE_URL"]).path.lstrip("/")
create_database_if_missing(os.environ["DATABASE_URL"], name)
PY

  # Init gbrain against Postgres. Mirror paca.integrations.gbrain.gbrain_env:
  # set GBRAIN_DATABASE_URL and drop DATABASE_URL so gbrain never touches the
  # main DB. Full init on first run; migrate-only (no clobber) afterwards.
  GBRAIN_HOME="${PACA_GBRAIN_HOME:-/state/gbrain}"
  if [ -f "$GBRAIN_HOME/.gbrain/config.json" ]; then
    init_arg="--migrate-only"
  else
    init_arg="--non-interactive"
  fi
  env -u DATABASE_URL \
      GBRAIN_HOME="$GBRAIN_HOME" \
      GBRAIN_DATABASE_URL="$PACA_GBRAIN_DATABASE_URL" \
      gbrain init "$init_arg"
fi

echo "[bootstrap] complete"
