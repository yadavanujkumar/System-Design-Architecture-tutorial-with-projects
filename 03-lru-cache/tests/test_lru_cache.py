"""Tests for the LRU Cache implementation."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lru_cache import LRUCache


class TestLRUCacheBasic:
    def test_put_and_get(self):
        cache = LRUCache(capacity=3)
        cache.put(1, "a")
        assert cache.get(1) == "a"

    def test_miss_returns_sentinel(self):
        cache = LRUCache(capacity=3)
        assert cache.get(99) == LRUCache.MISS

    def test_update_existing_key(self):
        cache = LRUCache(capacity=3)
        cache.put(1, "a")
        cache.put(1, "updated")
        assert cache.get(1) == "updated"

    def test_len_increases_on_put(self):
        cache = LRUCache(capacity=5)
        cache.put(1, "a")
        cache.put(2, "b")
        assert len(cache) == 2

    def test_len_does_not_increase_on_update(self):
        cache = LRUCache(capacity=5)
        cache.put(1, "a")
        cache.put(1, "b")
        assert len(cache) == 1

    def test_contains_true(self):
        cache = LRUCache(capacity=3)
        cache.put("x", 42)
        assert "x" in cache

    def test_contains_false(self):
        cache = LRUCache(capacity=3)
        assert "missing" not in cache

    def test_invalid_capacity_raises(self):
        with pytest.raises(ValueError):
            LRUCache(capacity=0)


class TestLRUCacheEviction:
    def test_evicts_lru_on_overflow(self):
        cache = LRUCache(capacity=3)
        cache.put(1, "a")
        cache.put(2, "b")
        cache.put(3, "c")
        cache.put(4, "d")  # should evict key 1
        assert cache.get(1) == LRUCache.MISS
        assert cache.get(4) == "d"

    def test_get_promotes_to_mru(self):
        cache = LRUCache(capacity=3)
        cache.put(1, "a")
        cache.put(2, "b")
        cache.put(3, "c")
        cache.get(1)        # promote 1 — now MRU
        cache.put(4, "d")   # should evict 2 (now LRU)
        assert cache.get(1) == "a"
        assert cache.get(2) == LRUCache.MISS

    def test_put_update_promotes_to_mru(self):
        cache = LRUCache(capacity=3)
        cache.put(1, "a")
        cache.put(2, "b")
        cache.put(3, "c")
        cache.put(1, "A")   # update promotes 1 to MRU
        cache.put(4, "d")   # should evict 2
        assert cache.get(1) == "A"
        assert cache.get(2) == LRUCache.MISS

    def test_keys_ordered_mru_to_lru(self):
        cache = LRUCache(capacity=3)
        cache.put(1, "a")
        cache.put(2, "b")
        cache.put(3, "c")
        assert cache.keys() == [3, 2, 1]

    def test_keys_after_get_reorder(self):
        cache = LRUCache(capacity=3)
        cache.put(1, "a")
        cache.put(2, "b")
        cache.put(3, "c")
        cache.get(1)
        assert cache.keys() == [1, 3, 2]

    def test_capacity_one(self):
        cache = LRUCache(capacity=1)
        cache.put(1, "a")
        cache.put(2, "b")
        assert cache.get(1) == LRUCache.MISS
        assert cache.get(2) == "b"


class TestLRUCacheDelete:
    def test_delete_existing_key(self):
        cache = LRUCache(capacity=3)
        cache.put(1, "a")
        assert cache.delete(1) is True
        assert cache.get(1) == LRUCache.MISS

    def test_delete_reduces_len(self):
        cache = LRUCache(capacity=3)
        cache.put(1, "a")
        cache.delete(1)
        assert len(cache) == 0

    def test_delete_missing_key_returns_false(self):
        cache = LRUCache(capacity=3)
        assert cache.delete(99) is False

    def test_delete_allows_reinsertion(self):
        cache = LRUCache(capacity=1)
        cache.put(1, "a")
        cache.delete(1)
        cache.put(2, "b")
        assert len(cache) == 1
        assert cache.get(2) == "b"


class TestLRUCachePeek:
    def test_peek_does_not_promote(self):
        cache = LRUCache(capacity=3)
        cache.put(1, "a")
        cache.put(2, "b")
        cache.put(3, "c")
        cache.peek(1)       # should NOT move 1 to MRU
        cache.put(4, "d")   # should evict 1
        assert cache.get(1) == LRUCache.MISS

    def test_peek_returns_value(self):
        cache = LRUCache(capacity=3)
        cache.put(42, "hello")
        assert cache.peek(42) == "hello"

    def test_peek_miss_returns_sentinel(self):
        cache = LRUCache(capacity=3)
        assert cache.peek(99) == LRUCache.MISS
