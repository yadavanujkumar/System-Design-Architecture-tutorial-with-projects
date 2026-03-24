"""
Consistent Hashing — Project 4
================================
Demonstrates: hash ring, virtual nodes, O(log N) key lookup via bisect,
              minimal key remapping on node add/remove.
"""

import bisect
import hashlib
from collections import defaultdict


# ---------------------------------------------------------------------------
# Consistent Hash Ring
# ---------------------------------------------------------------------------

class ConsistentHashRing:
    """
    A consistent hash ring with configurable virtual nodes.

    Each physical node is placed at *virtual_nodes* positions on the ring
    (derived by hashing ``"<node>#<replica_index>"``).  Key lookup walks the
    ring clockwise to the first virtual node — its physical node handles
    the key.

    Args:
        virtual_nodes: Number of virtual replicas per physical node.
                       Higher values improve load balance.  Default: 150.

    Example::

        ring = ConsistentHashRing(virtual_nodes=100)
        ring.add_node("server-1")
        ring.add_node("server-2")
        ring.add_node("server-3")

        node = ring.get_node("my-cache-key")   # e.g. "server-2"
        ring.remove_node("server-2")
        node = ring.get_node("my-cache-key")   # now routes to "server-1" or "server-3"
    """

    def __init__(self, virtual_nodes: int = 150) -> None:
        if virtual_nodes < 1:
            raise ValueError("virtual_nodes must be at least 1")
        self._virtual_nodes = virtual_nodes
        # Sorted list of hash positions
        self._ring: list[int] = []
        # position → physical node name
        self._position_to_node: dict[int, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_node(self, node: str) -> None:
        """
        Add *node* to the ring.

        Places *virtual_nodes* replicas at deterministic positions derived
        from ``"<node>#<i>"``.  Idempotent — adding the same node twice has
        no effect.
        """
        for i in range(self._virtual_nodes):
            position = self._hash(f"{node}#{i}")
            if position not in self._position_to_node:
                bisect.insort(self._ring, position)
            self._position_to_node[position] = node

    def remove_node(self, node: str) -> None:
        """
        Remove *node* and all its virtual replicas from the ring.

        Raises ``KeyError`` if *node* is not present.
        """
        if not self._has_node(node):
            raise KeyError(f"Node '{node}' is not in the ring")
        for i in range(self._virtual_nodes):
            position = self._hash(f"{node}#{i}")
            if position in self._position_to_node:
                idx = bisect.bisect_left(self._ring, position)
                if idx < len(self._ring) and self._ring[idx] == position:
                    self._ring.pop(idx)
                del self._position_to_node[position]

    def get_node(self, key: str) -> str:
        """
        Return the node responsible for *key*.

        Raises ``RuntimeError`` if the ring is empty.
        """
        if not self._ring:
            raise RuntimeError("Ring is empty — add at least one node first")
        position = self._hash(key)
        idx = bisect.bisect(self._ring, position) % len(self._ring)
        return self._position_to_node[self._ring[idx]]

    def get_nodes(self) -> list[str]:
        """Return the sorted list of unique physical node names."""
        return sorted(set(self._position_to_node.values()))

    def key_distribution(self, keys: list[str]) -> dict[str, int]:
        """
        Return a mapping of node → number of keys routed to that node.

        Useful for visualising load balance.
        """
        distribution: dict[str, int] = defaultdict(int)
        for key in keys:
            distribution[self.get_node(key)] += 1
        return dict(distribution)

    def __len__(self) -> int:
        """Return the number of physical nodes in the ring."""
        return len(self.get_nodes())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash(value: str) -> int:
        """Return a 32-bit unsigned integer hash of *value* using MD5."""
        digest = hashlib.md5(value.encode()).digest()
        # Use first 4 bytes as a big-endian unsigned integer
        return int.from_bytes(digest[:4], "big")

    def _has_node(self, node: str) -> bool:
        """Return True if at least one virtual replica of *node* exists."""
        return any(n == node for n in self._position_to_node.values())
