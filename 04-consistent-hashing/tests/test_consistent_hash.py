"""Tests for the Consistent Hash Ring implementation."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from consistent_hash import ConsistentHashRing


class TestConsistentHashRingBasic:
    def test_add_node_and_get_node(self):
        ring = ConsistentHashRing(virtual_nodes=50)
        ring.add_node("server-1")
        assert ring.get_node("any-key") == "server-1"

    def test_get_node_empty_ring_raises(self):
        ring = ConsistentHashRing()
        with pytest.raises(RuntimeError):
            ring.get_node("key")

    def test_len_reflects_physical_nodes(self):
        ring = ConsistentHashRing(virtual_nodes=50)
        ring.add_node("a")
        ring.add_node("b")
        assert len(ring) == 2

    def test_get_nodes_returns_sorted_names(self):
        ring = ConsistentHashRing(virtual_nodes=50)
        ring.add_node("c")
        ring.add_node("a")
        ring.add_node("b")
        assert ring.get_nodes() == ["a", "b", "c"]

    def test_invalid_virtual_nodes_raises(self):
        with pytest.raises(ValueError):
            ConsistentHashRing(virtual_nodes=0)

    def test_add_same_node_twice_is_idempotent(self):
        ring = ConsistentHashRing(virtual_nodes=50)
        ring.add_node("server-1")
        ring.add_node("server-1")
        assert len(ring) == 1


class TestConsistentHashRingRouting:
    def test_same_key_always_routes_to_same_node(self):
        ring = ConsistentHashRing(virtual_nodes=100)
        for node in ["a", "b", "c"]:
            ring.add_node(node)
        key = "stable-key"
        node = ring.get_node(key)
        for _ in range(10):
            assert ring.get_node(key) == node

    def test_keys_distributed_across_all_nodes(self):
        ring = ConsistentHashRing(virtual_nodes=150)
        nodes = ["server-1", "server-2", "server-3"]
        for n in nodes:
            ring.add_node(n)
        keys = [f"key-{i}" for i in range(300)]
        dist = ring.key_distribution(keys)
        # Every node should receive some keys
        for n in nodes:
            assert dist.get(n, 0) > 0

    def test_load_balance_within_reasonable_range(self):
        ring = ConsistentHashRing(virtual_nodes=150)
        for i in range(3):
            ring.add_node(f"server-{i}")
        keys = [f"key-{i}" for i in range(3000)]
        dist = ring.key_distribution(keys)
        total = sum(dist.values())
        assert total == 3000
        # Each node should handle between 15% and 52% of keys
        for count in dist.values():
            assert 15 <= (count / total * 100) <= 52


class TestConsistentHashRingRemoval:
    def test_remove_node_reduces_len(self):
        ring = ConsistentHashRing(virtual_nodes=50)
        ring.add_node("a")
        ring.add_node("b")
        ring.remove_node("a")
        assert len(ring) == 1

    def test_remove_node_routes_to_remaining_node(self):
        ring = ConsistentHashRing(virtual_nodes=50)
        ring.add_node("a")
        ring.add_node("b")
        ring.remove_node("b")
        assert ring.get_node("any-key") == "a"

    def test_remove_non_existent_node_raises(self):
        ring = ConsistentHashRing(virtual_nodes=50)
        with pytest.raises(KeyError):
            ring.remove_node("ghost")

    def test_minimal_remapping_on_node_removal(self):
        """Removing one of three nodes should remap ~33% of keys, not all."""
        ring = ConsistentHashRing(virtual_nodes=150)
        nodes = ["a", "b", "c"]
        for n in nodes:
            ring.add_node(n)
        keys = [f"key-{i}" for i in range(900)]
        before = {k: ring.get_node(k) for k in keys}
        ring.remove_node("c")
        after = {k: ring.get_node(k) for k in keys}
        remapped = sum(1 for k in keys if before[k] != after[k])
        # At most ~50% of keys should need remapping (theoretical ~33%)
        assert remapped <= len(keys) * 0.50

    def test_minimal_remapping_on_node_addition(self):
        """Adding a 4th node should remap ~25% of keys, not all."""
        ring = ConsistentHashRing(virtual_nodes=150)
        for n in ["a", "b", "c"]:
            ring.add_node(n)
        keys = [f"key-{i}" for i in range(900)]
        before = {k: ring.get_node(k) for k in keys}
        ring.add_node("d")
        after = {k: ring.get_node(k) for k in keys}
        remapped = sum(1 for k in keys if before[k] != after[k])
        # At most ~40% of keys should need remapping (theoretical ~25%)
        assert remapped <= len(keys) * 0.40
