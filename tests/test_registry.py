"""Tests for collectors/registry.py — the platform_id -> collector class
mapping every other part of the pipeline (worker.collect_all,
config/platforms.py's resolved plans) relies on.
"""

from collectors.base import PlatformCollector
from collectors.registry import COLLECTORS, get_collector


def test_get_collector_returns_instance_for_known_platform():
    collector = get_collector("google_maps")
    assert collector is not None
    assert isinstance(collector, PlatformCollector)


def test_get_collector_returns_none_for_unknown_platform():
    assert get_collector("totally_made_up_platform") is None


def test_get_collector_returns_a_fresh_instance_each_call():
    a = get_collector("google_maps")
    b = get_collector("google_maps")
    assert a is not b  # no shared mutable state across calls


def test_every_registered_collector_platform_id_matches_its_dict_key():
    for platform_id, cls in COLLECTORS.items():
        instance = cls()
        assert instance.platform_id == platform_id, (
            f"registry key {platform_id!r} maps to a collector whose "
            f"platform_id is {instance.platform_id!r} — CollectionResult "
            f"objects it returns would be mislabeled"
        )


def test_every_registered_collector_is_a_platform_collector_subclass():
    for cls in COLLECTORS.values():
        assert issubclass(cls, PlatformCollector)
