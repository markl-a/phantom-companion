"""P1-M2 — SQLite-backed cache for built :class:`AggregateWindow`s.

Building a window scans the mesh tree; doing that on every report run is
wasteful once a span is settled. :class:`WindowCache` memoises a window keyed
by its day span (plus the schema version, so a schema bump invalidates stale
rows) and stores the serialized JSON so a warm read reconstructs a window that
is *equal* to the cold build — not merely close.

The cache is intentionally content-addressed by the requested day list rather
than by mtime: fixtures and the weekly report ask for fixed historical spans,
so a hit is always correct. Callers that need freshness for *today* should
request without caching or evict the open-ended key themselves.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .schema import SCHEMA_VERSION, AggregateWindow, aggregate_window


def _key_for(days: list[str]) -> str:
    """Stable cache key for a day span (order-independent)."""
    ordered = sorted(set(days))
    return f"v{SCHEMA_VERSION}:" + ",".join(ordered)


class WindowCache:
    """A tiny SQLite key→window store. Safe to re-open over the same file."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS window_cache (
                key            TEXT PRIMARY KEY,
                schema_version INTEGER NOT NULL,
                payload        TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "WindowCache":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def has(self, days: list[str]) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM window_cache WHERE key = ?", (_key_for(days),)
        )
        return cur.fetchone() is not None

    def _load(self, days: list[str]) -> AggregateWindow | None:
        cur = self._conn.execute(
            "SELECT payload FROM window_cache WHERE key = ?", (_key_for(days),)
        )
        row = cur.fetchone()
        if row is None:
            return None
        payload: dict[str, Any] = json.loads(row[0])
        return AggregateWindow.from_dict(payload)

    def _store(self, days: list[str], window: AggregateWindow) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO window_cache (key, schema_version, payload) "
            "VALUES (?, ?, ?)",
            (
                _key_for(days),
                SCHEMA_VERSION,
                json.dumps(window.to_dict(), sort_keys=True, ensure_ascii=False),
            ),
        )
        self._conn.commit()

    def get_or_build(
        self,
        days: list[str],
        mesh_root: Path | None = None,
        health_by_day: dict[str, dict[str, Any]] | None = None,
        output_by_day: dict[str, dict[str, Any]] | None = None,
    ) -> AggregateWindow:
        """Return the cached window for ``days`` or build + cache it.

        A warm read is reconstructed from stored JSON and is equal to the cold
        build (verified by the cache-equivalence test).
        """
        cached = self._load(days)
        if cached is not None:
            return cached
        window = aggregate_window(
            days,
            mesh_root=mesh_root,
            health_by_day=health_by_day,
            output_by_day=output_by_day,
        )
        self._store(days, window)
        return window

    def evict(self, days: list[str]) -> None:
        self._conn.execute(
            "DELETE FROM window_cache WHERE key = ?", (_key_for(days),)
        )
        self._conn.commit()


__all__ = ["WindowCache"]
