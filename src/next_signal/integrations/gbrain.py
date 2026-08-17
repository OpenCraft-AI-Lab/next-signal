"""GBrain CLI bridge for long-term markdown knowledge."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from next_signal.core.paths import PROJECT_ROOT
from next_signal.core.secrets import child_env
from next_signal.integrations._helpers import to_jsonable, truncate

_DEFAULT_TIMEOUT = 60


def resolve_gbrain_home(value: str) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path.resolve())


NOT_INITIALISED_HINT = (
    "GBrain has not been initialised, so knowledge search is unavailable. "
    "Container bootstrap deliberately leaves it uninitialised, because the "
    "embedding model sizes the schema permanently and bootstrap runs before "
    "anyone can choose one. Initialise it with the model you want: "
    "`next-signal knowledge gbrain-init --embedding-model <provider>:<model>`."
)

# Embedding providers GBrain can be pointed at, mapped to the credential each
# one reads from its own environment. A local runner takes an endpoint rather
# than a key, so it maps to None and works against an empty credential store.
# The model string is `<provider>:<model>`; the provider half fixes which
# credential — if any — a spawn needs.
_PROVIDER_CREDENTIAL: dict[str, str | None] = {
    "openai": "OPENAI_API_KEY",
    "voyage": "VOYAGE_API_KEY",
    "google": "GOOGLE_GENERATIVE_AI_API_KEY",
    "ollama": None,
    "lmstudio": None,
    "llama-server": None,
}

EMBEDDING_PROVIDERS: tuple[str, ...] = tuple(sorted(_PROVIDER_CREDENTIAL))


def provider_of(embedding_model: str) -> str:
    """Provider half of a `<provider>:<model>` string, lowercased."""
    return embedding_model.split(":", 1)[0].strip().lower()


def credential_for_model(embedding_model: str) -> str | None:
    """Credential the model's provider reads, or None when it needs none.

    An unrecognised provider also resolves to None. This sits on the read path
    for every gbrain call, so an unknown provider degrades to injecting nothing
    and letting gbrain report; `gbrain-init` validates the provider up front,
    where the operator is actually choosing one.
    """
    return _PROVIDER_CREDENTIAL.get(provider_of(embedding_model))


def _home(gbrain_home: str | None = None) -> str:
    """Resolve GBRAIN_HOME without going through `gbrain_env`, which needs this."""
    value = (gbrain_home if gbrain_home is not None else os.environ.get("GBRAIN_HOME", "")).strip()
    return resolve_gbrain_home(value) if value else ""


def brain_config(*, gbrain_home: str | None = None) -> dict[str, Any] | None:
    """GBrain's own config file, or None when it is absent or unreadable."""
    home = _home(gbrain_home)
    if not home:
        return None
    try:
        parsed = json.loads((Path(home) / ".gbrain" / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def brain_initialised(*, gbrain_home: str | None = None) -> bool | None:
    """Whether a brain exists: True, False, or None when it can't be determined.

    Read from GBrain's own config file because nothing else reports it: `gbrain
    doctor --fast` scores a brain that does not exist as healthy and exits 0,
    and a search against one prints "No results." and exits 0 too.

    The three-way return keeps "no brain" separate from "we could not find out",
    so an unreadable config degrades to attempting the work rather than refusing.
    """
    home = _home(gbrain_home)
    if not home:
        return None
    if not (Path(home) / ".gbrain" / "config.json").exists():
        return False
    return None if brain_config(gbrain_home=gbrain_home) is None else True


def configured_embedding_model(*, gbrain_home: str | None = None) -> str | None:
    """The embedding model an initialised brain was built with, if any."""
    value = (brain_config(gbrain_home=gbrain_home) or {}).get("embedding_model")
    return value.strip() if isinstance(value, str) and value.strip() else None


def gbrain_env(
    *, gbrain_home: str | None = None, embedding_model: str | None = None
) -> dict[str, str]:
    """Child environment for a gbrain spawn, scoped to the selected provider.

    `embedding_model` overrides what the brain's config says, for the one caller
    that runs before a brain exists: `gbrain-init` knows the provider the
    operator just chose.
    """
    model = embedding_model or configured_embedding_model(gbrain_home=gbrain_home)
    credential = credential_for_model(model) if model else None
    env = child_env([credential] if credential else [])
    gbrain_home = (gbrain_home if gbrain_home is not None else env.get("GBRAIN_HOME", "")).strip()
    gbrain_url = env.get("GBRAIN_DATABASE_URL", "").strip()

    if gbrain_home:
        env["GBRAIN_HOME"] = resolve_gbrain_home(gbrain_home)
        if not env.get("GBRAIN_DATABASE_URL"):
            env.pop("DATABASE_URL", None)
    if gbrain_url:
        env["GBRAIN_DATABASE_URL"] = gbrain_url
        env.pop("DATABASE_URL", None)
    return env


def _gbrain_bin() -> str:
    configured = os.environ.get("GBRAIN_BIN", "").strip()
    if configured:
        return configured
    found = shutil.which("gbrain")
    if not found:
        raise RuntimeError("gbrain CLI not found; set GBRAIN_BIN or install/link gbrain")
    return found


def _run_gbrain(
    args: list[str],
    *,
    timeout: int = _DEFAULT_TIMEOUT,
    stdin: str | None = None,
) -> dict[str, Any]:
    cmd = [_gbrain_bin(), *args]
    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            env=gbrain_env(),
            input=stdin,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        return {"ok": False, "error": f"gbrain timed out after {e.timeout}s", "command": args}

    return to_jsonable(
        {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "command": args,
            "stdout": truncate(result.stdout.strip(), 20000),
            "stderr": truncate(result.stderr.strip(), 4000),
        }
    )


# Han ideograph ranges (BMP). GBrain keyword search is tsvector-backed and
# doesn't tokenize CJK, so a Chinese query matches nothing useful; such queries
# route to hybrid `query` (vector + RRF), which is script-agnostic.
_CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")


def _has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def gbrain_search(query: str, limit: int = 5) -> dict[str, Any]:
    """Search GBrain pages through the local gbrain CLI.

    Han-bearing queries route to hybrid ``query`` because keyword search
    (tsvector) can't tokenize CJK and returns no results; ASCII queries stay on
    the faster keyword path.
    """
    if _has_cjk(query):
        return gbrain_query(query, limit=limit)
    return _run_gbrain(["search", query, "--limit", str(max(1, min(20, limit)))])


def gbrain_get(slug: str) -> dict[str, Any]:
    """Read one GBrain page by slug through the local gbrain CLI."""
    return _run_gbrain(["get", slug])


def gbrain_query(question: str, *, limit: int | None = None) -> dict[str, Any]:
    """Run GBrain hybrid query (vector + keyword + multi-query expansion)."""
    args = ["query", question]
    if limit is not None:
        args += ["--limit", str(max(1, min(50, limit)))]
    return _run_gbrain(args, timeout=120)


def _slug_from_path(path: Path) -> str:
    return gbrain_slug_for_path(path)


def gbrain_slug_for_path(path: Path | str) -> str:
    """Return a GBrain-safe slug derived from a wiki-relative path.

    Folds the per-article subfolder layout `<dir>/<dir>.md` into `<dir>` so a
    self-contained article folder gets the same flat slug as the legacy
    single-file layout would have produced.
    """
    parts = Path(path).with_suffix("")
    if parts.parent.name and parts.parent.name == parts.name:
        parts = parts.parent
    raw = parts.as_posix().strip("/")
    value = raw.lower()
    needs_hash = bool(re.search(r"[^a-z0-9._/ -]", value))
    slug = re.sub(r"[^a-z0-9._-]+", "-", value).strip("-")
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        slug = "page"
    if needs_hash:
        suffix = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
        slug = f"{slug}-{suffix}"
    return slug


def gbrain_ingest(path: str, kind: str = "markdown", slug: str | None = None) -> dict[str, Any]:
    """Import a local markdown file or directory into GBrain."""
    if kind != "markdown":
        raise RuntimeError(f"unsupported gbrain ingest kind: {kind}")
    source = Path(path)
    if source.is_file():
        page_slug = _slug_from_path(Path(slug)) if slug else _slug_from_path(Path(source.name))
        put = _run_gbrain(["put", page_slug], timeout=120, stdin=source.read_text(encoding="utf-8"))
        if not put.get("ok"):
            return put
        embed = _run_gbrain(["embed", page_slug], timeout=300)
        return to_jsonable(
            {
                "ok": bool(embed.get("ok")),
                "command": ["put", page_slug, "&&", "embed", page_slug],
                "stdout": "\n".join(filter(None, [put.get("stdout"), embed.get("stdout")])),
                "stderr": "\n".join(filter(None, [put.get("stderr"), embed.get("stderr")])),
                "returncode": embed.get("returncode"),
                "embedding_ok": bool(embed.get("ok")),
                "slug": page_slug,
            }
        )
    return _run_gbrain(["import", path], timeout=300)
