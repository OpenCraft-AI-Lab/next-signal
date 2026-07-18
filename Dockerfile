# syntax=docker/dockerfile:1

# Containerized cloud-LLM build for next-signal.
# See docs/containerized-deployment.md for the design rationale.
#
# OS-agnostic: every base image is multi-arch, nothing here assumes the host
# OS/arch. Build with `docker compose build` (or `docker buildx build`).
#
# Peer tools (gbrain, opencli) are cloned from upstream at pinned refs — a new
# user only needs THIS repo. Override the refs with --build-arg if needed.
# gbrain ships no release tags, so it is pinned to a master commit SHA;
# opencli uses a real release tag. Both refs may be a SHA, tag, or branch.
ARG GBRAIN_REF=a25209bbb2bacf1b88e06fd5282b27f1bf4a3e7a
ARG OPENCLI_REF=v1.8.1

# ---------------------------------------------------------------------------
# Stage 1 — build the gbrain single-file binary (needs Bun).
# ---------------------------------------------------------------------------
FROM oven/bun:1 AS gbrain-build
ARG GBRAIN_REF
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
# Fetch by exact ref (SHA/tag/branch). `clone --branch` rejects raw SHAs, and
# gbrain has no tags, so init + fetch the pinned ref instead.
RUN git init -q . \
    && git remote add origin https://github.com/garrytan/gbrain.git \
    && git fetch -q --depth 1 origin "${GBRAIN_REF}" \
    && git checkout -q FETCH_HEAD
RUN bun install --frozen-lockfile \
    && bun run build            # package.json → `bun build --compile --outfile bin/gbrain`
# Result: /src/bin/gbrain (self-contained executable)

# ---------------------------------------------------------------------------
# Stage 2 — build OpenCLI (HTTP-only; no browser). Needs Node + npm.
# ---------------------------------------------------------------------------
FROM node:22-bookworm-slim AS opencli-build
ARG OPENCLI_REF
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git clone --depth 1 --branch "${OPENCLI_REF}" https://github.com/jackwener/OpenCLI.git .
# `npm install` runs the `prepare` hook which builds dist/src/main.js.
RUN npm install --no-audit --no-fund \
    && npm prune --omit=dev      # drop dev deps; keep runtime deps for main.js
# Result: /src/dist/src/main.js + /src/node_modules (runtime only)

# ---------------------------------------------------------------------------
# Stage 3 — Python deps + editable paca install (uv).
# The project is installed EDITABLE at /app so paca.core.paths.PROJECT_ROOT
# (parents[3] of paths.py) resolves to /app at runtime. Keep WORKDIR=/app
# identical in the runtime stage or the editable link breaks.
# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS py-build
# Pin uv for reproducibility; bump deliberately.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
# 1) Dependency layer — cached until the lockfile changes.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
# 2) Project layer — source + declarative config the runtime reads by path.
COPY src ./src
COPY configs ./configs
COPY prompts ./prompts
COPY scripts ./scripts
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev
# Result: /app/.venv (deps + editable paca) and the source tree at /app.

# ---------------------------------------------------------------------------
# Stage 4 — build the Next.js dashboard (pnpm).
# ---------------------------------------------------------------------------
FROM node:22-bookworm-slim AS dash-build
# PACA_WIKI_DIR is a dummy value so build-time path guards don't throw.
ENV NEXT_TELEMETRY_DISABLED=1 \
    PACA_WIKI_DIR=/wiki
RUN corepack enable
WORKDIR /app/dashboard
# Dependency layer — cached until the lockfile changes.
COPY dashboard/package.json dashboard/pnpm-lock.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile --ignore-scripts
# Source + production build.
COPY dashboard/ ./
RUN pnpm build
# Result: /app/dashboard with .next/ + node_modules/.

# ---------------------------------------------------------------------------
# Stage 5 — runtime. Python is primary; Node is layered in for the dashboard,
# opencli, and folocli (npx). No browser, no Bun, no build toolchains.
# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime
# ffmpeg: whisper / yt-dlp audio. libgomp1: torch runtime. tini: PID-1 signals.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates ffmpeg libgomp1 tini \
    && rm -rf /var/lib/apt/lists/*
# Layer in the Node 22 runtime (node + npm + npx + corepack) and enable pnpm.
COPY --from=node:22-bookworm-slim /usr/local/bin/ /usr/local/bin/
COPY --from=node:22-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
# Enable only the pnpm shim — a bare `corepack enable` also tries to wire a
# `yarn` shim, but the copied yarn symlink dangles here and aborts it. Bake in
# the pinned pnpm so the runtime `pnpm start` needs no network on first boot.
RUN corepack enable pnpm && corepack prepare pnpm@11.8.0 --activate

WORKDIR /app
# Python venv + source (editable paca) — must land at the same /app path.
COPY --from=py-build /app /app
# Built dashboard (overlays the dashboard dir with node_modules + .next).
COPY --from=dash-build /app/dashboard /app/dashboard
# Peer tools.
COPY --from=gbrain-build /src/bin/gbrain /usr/local/bin/gbrain
COPY --from=opencli-build /src /opt/opencli
# uv binary — the dashboard launches paca CLI children via `uv run paca`
# (dashboard/lib/actions/spawn-paca.ts et al.), so uv must be on PATH at
# runtime, not just in the py-build stage.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    NEXT_TELEMETRY_DISABLED=1 \
    GBRAIN_BIN=/usr/local/bin/gbrain \
    OPENCLI_BIN=/opt/opencli/dist/src/main.js \
    PACA_STATE_DIR=/state \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_NO_SYNC=1
RUN chmod +x /usr/local/bin/gbrain && mkdir -p /state

# tini reaps the pnpm/next/uvicorn child trees cleanly on SIGTERM.
ENTRYPOINT ["/usr/bin/tini", "--"]
# Default command; docker-compose overrides per service.
CMD ["paca", "dashboard", "--start", "--port", "3000"]
