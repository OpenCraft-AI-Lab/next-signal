"""Info-radar collector runner.

For each enabled source: subprocess.run with timeout → parser → upsert. Per-source
failure isolation (see design D9): one source's CLI error or schema mismatch does
not abort the run; the runner only exits non-zero if **every** enabled source failed.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from paca.collectors.info_radar import store
from paca.collectors.info_radar.loader import SourceSpec, load_sources
from paca.core.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class SourceResult:
    name: str
    written: int
    skipped: int
    error: str | None  # one-line message, None on success


def run_all(only: str | None = None) -> list[SourceResult]:
    """Run every enabled source (or just ``only`` if specified).

    Always best-effort sweeps expired rows at the end (regardless of per-source
    outcomes). The caller (CLI / workflow shell) decides exit code based on
    whether all results errored.
    """
    specs = load_sources()
    if only is not None:
        specs = [s for s in specs if s.name == only]
        if not specs:
            raise RuntimeError(f"info-radar: no source named {only!r} in sources.yaml")

    results: list[SourceResult] = []
    for spec in specs:
        if not spec.enabled:
            log.info("info_radar_source_skipped_disabled", source=spec.name)
            continue
        results.append(_run_one(spec))

    # Best-effort retention sweep. Failure here logs but does not affect results.
    try:
        deleted = store.sweep_expired()
        if deleted:
            log.info("info_radar_sweep", deleted=deleted)
    except Exception as e:  # noqa: BLE001
        log.error("info_radar_sweep_failed", error=str(e))

    return results


def _run_one(spec: SourceSpec) -> SourceResult:
    log.info("info_radar_source_start", source=spec.name, argv=spec.argv)
    try:
        completed = subprocess.run(
            spec.argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=spec.timeout_sec,
        )
    except FileNotFoundError as e:
        msg = f"launcher not found: {e}"
        log.error("info_radar_source_failed", source=spec.name, error=msg)
        return SourceResult(spec.name, 0, 0, msg)
    except subprocess.TimeoutExpired as e:
        msg = f"timed out after {e.timeout}s"
        log.error("info_radar_source_failed", source=spec.name, error=msg)
        return SourceResult(spec.name, 0, 0, msg)

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()[:300]
        msg = f"exit {completed.returncode}: {stderr or '<no stderr>'}"
        log.error("info_radar_source_failed", source=spec.name, error=msg)
        return SourceResult(spec.name, 0, 0, msg)

    try:
        items = spec.parser(completed.stdout, spec.name)
    except Exception as e:  # noqa: BLE001
        msg = f"parser {spec.parser_name!r} raised: {e}"
        log.error("info_radar_source_failed", source=spec.name, error=msg)
        return SourceResult(spec.name, 0, 0, msg)

    try:
        written, skipped = store.upsert_items(spec.name, items)
    except Exception as e:  # noqa: BLE001
        msg = f"upsert failed: {e}"
        log.error("info_radar_source_failed", source=spec.name, error=msg)
        return SourceResult(spec.name, 0, 0, msg)

    log.info(
        "info_radar_source_done",
        source=spec.name,
        written=written,
        skipped=skipped,
        total=len(items),
    )
    return SourceResult(spec.name, written, skipped, None)


def all_failed(results: list[SourceResult]) -> bool:
    """True iff at least one source ran and every result has an error."""
    return bool(results) and all(r.error is not None for r in results)


__all__ = ["SourceResult", "run_all", "all_failed"]
