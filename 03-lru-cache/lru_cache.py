"""
LRU Cache — Project 3
=====================
Demonstrates: doubly-linked list + hash map for O(1) get/put, eviction policy.

The LRUCache class uses a sentinel head and tail node so that every
insert/remove operation is uniform (no special-casing for empty list).

Layout of the doubly-linked list:
    head (sentinel) <-> [MRU node] <-> ... <-> [LRU node] <-> tail (sentinel)
"""


# ---------------------------------------------------------------------------
# Internal doubly-linked list node
# ---------------------------------------------------------------------------

class _Node:
    """A node in the doubly-linked list that backs the LRU Cache."""

    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key=None, value=None):
        self.key = key
        self.value = value
        self.prev: "_Node | None" = None
        self.next: "_Node | None" = None


# ---------------------------------------------------------------------------
# LRU Cache
# ---------------------------------------------------------------------------

class LRUCache:
    """
    Least-Recently-Used cache with O(1) get and put operations.

    Args:
        capacity: Maximum number of items the cache can hold (must be ≥ 1).

    Example::

        cache = LRUCache(capacity=3)
        cache.put(1, "a")
        cache.put(2, "b")
        cache.put(3, "c")
        cache.get(1)          # "a"  — moves key 1 to MRU position
        cache.put(4, "d")     # evicts key 2 (LRU)
        cache.get(2)          # -1   — already evicted
    """

    MISS = -1  # sentinel returned on cache miss

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self._capacity = capacity
        self._size = 0
        # Map key → node for O(1) lookup
        self._map: dict[object, _Node] = {}
        # Sentinel nodes avoid edge-case checks
        self._head = _Node()  # most-recently-used side
        self._tail = _Node()  # least-recently-used side
        self._head.next = self._tail
        self._tail.prev = self._head

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key) -> object:
        """
        Return the cached value for *key*, or ``LRUCache.MISS`` (-1) on miss.

        Accessing a key promotes it to the most-recently-used position.
        """
        if key not in self._map:
            return self.MISS
        node = self._map[key]
        self._move_to_head(node)
        return node.value

    def put(self, key, value) -> None:
        """
        Insert or update *key* with *value*.

        If the cache is at capacity the least-recently-used item is evicted
        before the new item is inserted.
        """
        if key in self._map:
            node = self._map[key]
            node.value = value
            self._move_to_head(node)
        else:
            if self._size == self._capacity:
                self._evict_lru()
            node = _Node(key, value)
            self._map[key] = node
            self._add_to_head(node)
            self._size += 1

    def peek(self, key) -> object:
        """
        Return the cached value for *key* **without** changing its recency.

        Returns ``LRUCache.MISS`` (-1) on a miss.
        """
        node = self._map.get(key)
        return node.value if node else self.MISS

    def delete(self, key) -> bool:
        """
        Remove *key* from the cache.

        Returns ``True`` if the key existed, ``False`` otherwise.
        """
        if key not in self._map:
            return False
        self._remove_node(self._map.pop(key))
        self._size -= 1
        return True

    def __len__(self) -> int:
        return self._size

    def __contains__(self, key) -> bool:
        return key in self._map

    def keys(self) -> list:
        """Return all keys from most-recently-used to least-recently-used."""
        result = []
        node = self._head.next
        while node is not self._tail:
            result.append(node.key)
            node = node.next
        return result

    # ------------------------------------------------------------------
    # Private helpers — doubly-linked-list manipulation
    # ------------------------------------------------------------------

    def _add_to_head(self, node: _Node) -> None:
        """Insert *node* immediately after the head sentinel (MRU position)."""
        node.prev = self._head
        node.next = self._head.next
        self._head.next.prev = node
        self._head.next = node

    def _remove_node(self, node: _Node) -> None:
        """Unlink *node* from the list."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _move_to_head(self, node: _Node) -> None:
        """Move *node* to the MRU position."""
        self._remove_node(node)
        self._add_to_head(node)

    def _evict_lru(self) -> None:
        """Remove the least-recently-used node (just before the tail sentinel)."""
        lru = self._tail.prev
        self._remove_node(lru)
        del self._map[lru.key]
        self._size -= 1
