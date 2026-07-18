"""Raw knowledge artifact persistence."""

from __future__ import annotations

import shutil
from pathlib import Path

from paca.core import paths


def raw_dir(source_type: str, digest: str) -> Path:
    path = paths.WIKI_RAW_DIR / source_type / digest
    path.mkdir(parents=True, exist_ok=True)
    return path


def copy_raw_file(value: str, digest: str, source_type: str) -> Path:
    source = _agent_tmp_file(value)
    if not source.exists() or not source.is_file():
        raise RuntimeError(f"local file not found: {value}")
    dest = raw_dir(source_type, digest) / source.name
    shutil.copy2(source, dest)
    return dest


def write_raw_text(source_type: str, digest: str, name: str, text: str) -> Path:
    path = raw_dir(source_type, digest) / name
    path.write_text(text, encoding="utf-8")
    return path


def _agent_tmp_file(value: str) -> Path:
    source = Path(value).expanduser().resolve()
    tmp_root = paths.AGENT_TMP_DIR.expanduser().resolve()
    try:
        source.relative_to(tmp_root)
    except ValueError as e:
        raise RuntimeError(
            "local knowledge files must be staged under "
            f"{tmp_root}; refusing to read {source}"
        ) from e
    return source
