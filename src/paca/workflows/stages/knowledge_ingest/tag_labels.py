"""Persisted display-alias translation memory for knowledge tags.

Tag KEYS stay canonical lowercase English (stable GBrain cross-language join
keys). This module records a localized DISPLAY label per ``(tag, locale)`` in
``knowledge_tag_labels``, generated once via the ``knowledge_tag_translator``
agent and reused on every render. It is best-effort chrome: a translation or DB
failure logs and degrades to the English key, and never fails the ingest.

``en`` is short-circuited — the English label IS the key, so the dashboard's
key fallback already renders it and no row is generated.
"""

from __future__ import annotations

import logging

import psycopg

from paca.agents.loader import build_from_name
from paca.agents.structured import run_structured
from paca.core.db import database_url
from paca.workflows.stages.knowledge_ingest.schemas import TagLabel

log = logging.getLogger(__name__)


def ensure_tag_labels(tags: list[str], locale: str) -> None:
    """Ensure a ``knowledge_tag_labels`` row exists for each ``(tag, locale)``.

    Existing pairs are skipped (no regeneration). Best-effort: a lookup,
    translation, or write failure is logged and skipped without raising.
    """
    if not tags or locale == "en":
        return
    try:
        existing = _existing_labels(tags, locale)
    except Exception as e:  # noqa: BLE001 — display chrome must never fail ingest
        log.warning("tag_labels_lookup_failed", extra={"locale": locale, "error": str(e)})
        return
    for tag in tags:
        if tag in existing:
            continue
        try:
            label = _translate_tag(tag, locale)
            _upsert_label(tag, locale, label)
        except Exception as e:  # noqa: BLE001
            log.warning(
                "tag_label_failed",
                extra={"tag": tag, "locale": locale, "error": str(e)},
            )


def _existing_labels(tags: list[str], locale: str) -> set[str]:
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tag FROM knowledge_tag_labels WHERE locale = %s AND tag = ANY(%s)",
                (locale, list(tags)),
            )
            return {row[0] for row in cur.fetchall()}


def _upsert_label(tag: str, locale: str, label: str) -> None:
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO knowledge_tag_labels (tag, locale, label)
                VALUES (%s, %s, %s)
                ON CONFLICT (tag, locale) DO NOTHING
                """,
                (tag, locale, label),
            )
        conn.commit()


def _translate_tag(tag: str, locale: str) -> str:
    agent = build_from_name("knowledge_tag_translator", locale)
    result = run_structured(agent, tag, TagLabel)
    return result.label.strip() or tag


__all__ = ["ensure_tag_labels"]
