"""The one file that holds provider credentials.

Credentials live in ``$NEXT_SIGNAL_STATE_DIR/secrets.json`` (``/state/secrets.json``
in a container), a flat ``NAME -> value`` object the dashboard writes and every
process reads *at call time*. Nothing here ever touches ``os.environ``: the
dashboard and the scheduler are separate containers, so one cannot alter the
other's environment, but both see the same state volume. Reading on use is what
lets a credential saved in the browser reach a running scheduler with no
restart and no ``--force-recreate``.

Two rules this module exists to keep:

- **No credential is ever read from the environment.** There is no fallback and
  no import path, deliberately -- either would need a module that legitimately
  reads credential env vars, which turns an absolute rule into a judgment call
  and lets a stale ``.env`` satisfy a credential the dashboard reports as unset.
- **No credential value is ever logged or returned to a browser.** Callers get a
  value or an error naming the credential; presence is the only thing that
  crosses to a client.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

from next_signal.core.paths import STATE_ROOT

SECRETS_FILE = STATE_ROOT / "secrets.json"

# Every credential this system resolves, by name. The set is closed: the
# settings page renders one control per entry, so a credential absent from here
# would be one no operator could enter. `EMBEDDING_API_KEY` replaces no
# environment variable — it is the fixed name for whatever OpenAI-compatible
# embedding endpoint an operator configures.
CREDENTIAL_NAMES: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "DEEPSEEK_API_KEY",
    "OMLX_API_KEY",
    "EMBEDDING_API_KEY",
    "GITHUB_TOKEN",
    "FOLO_TOKEN",
)

_VALID_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


def _resolved(path: Path | None) -> Path:
    """Resolve the store location at call time, never at import.

    ``SECRETS_FILE`` is read here rather than bound as a default argument so a
    test (or a process that relocates its state directory) can redirect it.
    """
    return path if path is not None else SECRETS_FILE


def _validated_name(name: str) -> str:
    if not _VALID_NAME.fullmatch(name):
        raise RuntimeError(
            "credential name must be 1-64 uppercase letters, digits, or "
            f"underscores, starting with a letter: {name!r}"
        )
    return name


def load_secrets(path: Path | None = None) -> dict[str, str]:
    """Read the whole store. Absent file is an empty store; anything else is loud.

    A fresh install has no credentials, so absence is a valid permanent state --
    not an error and not something this function repairs. A file that exists but
    cannot be parsed is a different thing entirely and must not degrade to "no
    credentials configured", which would present as a missing key rather than a
    broken file.
    """
    path = _resolved(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise RuntimeError(f"cannot read credential store {path}: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid credential store {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid credential store {path}: must be a JSON object")
    for key, value in data.items():
        if not isinstance(value, str):
            raise RuntimeError(
                f"invalid credential store {path}: {key} is "
                f"{type(value).__name__}, expected a string"
            )
    return data


def get_secret(name: str, path: Path | None = None) -> str:
    """Return a credential, or ``""`` when it is not configured."""
    return load_secrets(path).get(_validated_name(name), "").strip()


def require_secret(name: str, path: Path | None = None) -> str:
    """Return a credential, or raise naming it and where to set it."""
    value = get_secret(name, path)
    if not value:
        raise RuntimeError(
            f"{name} is not configured. Set it on the dashboard settings page "
            "(Settings -> Credentials)."
        )
    return value


def save_secret(name: str, value: str, path: Path | None = None) -> None:
    """Store one credential, replacing any previous value."""
    selected = value.strip()
    if not selected:
        raise RuntimeError(f"refusing to store an empty value for {name}")
    secrets = load_secrets(path)
    secrets[_validated_name(name)] = selected
    _write(secrets, _resolved(path))


def delete_secret(name: str, path: Path | None = None) -> None:
    """Remove one credential. Removing an absent credential is a no-op."""
    secrets = load_secrets(path)
    if secrets.pop(_validated_name(name), None) is None:
        return
    _write(secrets, _resolved(path))


def _write(secrets: dict[str, str], path: Path) -> None:
    """Publish the store atomically, owner-readable only.

    The temp name carries the pid and a uuid rather than a fixed ``.tmp`` suffix
    -- the same reasoning as ``dashboard/lib/state-file.ts``. Two saves in flight
    would share one temp path, and the first rename consumes it, so the second
    fails with ENOENT: the file is intact either way, but the caller reports a
    failed save and rolls its control back to a value that is no longer on disk.

    The file is *created* 0600 rather than chmod'd afterwards, so a credential is
    never briefly world-readable. On Windows the mode maps onto ACLs only
    nominally; the guarantee is scoped to the Linux container, which is the
    supported deployment.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    payload = json.dumps(secrets, indent=2, sort_keys=True) + "\n"
    fd = os.open(tmp, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def child_env(names: list[str], path: Path | None = None) -> dict[str, str]:
    """Build the environment for one subprocess that needs credentials.

    For external programs whose only credential channel is an environment
    variable (``folocli``). Per spawn rather than process-global: the read
    happens now, so a saved credential is live immediately, and a credential
    reaches only the children whose call site named it. The dashboard spawns CLI
    children with the parent's whole environment, so materializing credentials
    into ``os.environ`` would hand every secret to every child -- including the
    coding-agent CLIs, which run with ``inherit_env: []`` on purpose.

    Every known credential is *stripped* from the copied environment first, and
    only the requested ones are put back from the store. Inheriting is not
    neutral: anything that calls ``load_dotenv`` pulls a leftover ``.env`` into
    this process, and without the strip that stale value would reach the child
    and authenticate it — from the environment, which is the one source this
    system does not read.

    An absent credential is then omitted rather than passed empty: how a
    third-party program treats an empty variable is not ours to define. Callers
    that require one check with ``require_secret`` before spawning.
    """
    env = os.environ.copy()
    secrets = load_secrets(path)
    for name in set(CREDENTIAL_NAMES) | set(secrets):
        env.pop(name, None)
    for name in names:
        value = secrets.get(_validated_name(name), "").strip()
        if value:
            env[name] = value
    return env
