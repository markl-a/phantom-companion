"""WindowCache.evict() — untested public method: build/cache/evict/rebuild cycle."""
from __future__ import annotations

from phantom_companion.cache import WindowCache


def test_get_or_build_stores_evict_clears_then_reget_rebuilds(tmp_path):
    days = ["2026-06-27"]
    with WindowCache(tmp_path / "cache.db") as cache:
        window = cache.get_or_build(days, mesh_root=tmp_path)
        assert cache.has(days) is True

        cache.evict(days)
        assert cache.has(days) is False

        rebuilt = cache.get_or_build(days, mesh_root=tmp_path)
        assert cache.has(days) is True
        assert rebuilt.to_dict() == window.to_dict()


def test_evict_is_a_noop_for_an_uncached_key(tmp_path):
    with WindowCache(tmp_path / "cache.db") as cache:
        cache.evict(["2026-01-01"])  # never cached — must not raise
        assert cache.has(["2026-01-01"]) is False


def test_evict_does_not_affect_a_different_cached_span(tmp_path):
    with WindowCache(tmp_path / "cache.db") as cache:
        cache.get_or_build(["2026-06-27"], mesh_root=tmp_path)
        cache.get_or_build(["2026-06-28"], mesh_root=tmp_path)

        cache.evict(["2026-06-27"])

        assert cache.has(["2026-06-27"]) is False
        assert cache.has(["2026-06-28"]) is True
