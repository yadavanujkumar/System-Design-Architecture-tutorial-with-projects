"""
Pub/Sub Message Queue — Project 5
===================================
Demonstrates: publish/subscribe pattern, topics, consumer groups with
              independent offsets, message retention, and replay.

Inspired by Apache Kafka's log-based model.
"""

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """A single message stored in a topic's log."""
    offset: int
    value: Any
    key: str | None = None
    timestamp: float = field(default_factory=time.time)
    headers: dict[str, str] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __repr__(self) -> str:  # pragma: no cover
        return f"Message(offset={self.offset}, key={self.key!r}, value={self.value!r})"


# ---------------------------------------------------------------------------
# Topic
# ---------------------------------------------------------------------------

class Topic:
    """
    An ordered, append-only log of :class:`Message` objects.

    Args:
        name:              Topic name.
        retention_seconds: How long (in seconds) messages are kept.
                           ``None`` means keep forever.
    """

    def __init__(self, name: str, retention_seconds: float | None = None) -> None:
        self.name = name
        self._retention_seconds = retention_seconds
        self._messages: list[Message] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _purge_expired(self) -> None:
        """Remove messages older than retention_seconds (must hold lock)."""
        if self._retention_seconds is None:
            return
        cutoff = time.time() - self._retention_seconds
        self._messages = [m for m in self._messages if m.timestamp >= cutoff]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, value: Any, key: str | None = None,
               headers: dict[str, str] | None = None) -> Message:
        """Append a message and return it."""
        with self._lock:
            self._purge_expired()
            offset = self._messages[-1].offset + 1 if self._messages else 0
            msg = Message(
                offset=offset,
                value=value,
                key=key,
                headers=headers or {},
            )
            self._messages.append(msg)
            return msg

    def read(self, from_offset: int, batch_size: int = 1) -> list[Message]:
        """
        Return up to *batch_size* messages starting at *from_offset*.

        If fewer messages exist the list will be shorter than *batch_size*.
        """
        with self._lock:
            self._purge_expired()
            result = []
            for msg in self._messages:
                if msg.offset >= from_offset:
                    result.append(msg)
                    if len(result) >= batch_size:
                        break
            return result

    def __len__(self) -> int:
        with self._lock:
            self._purge_expired()
            return len(self._messages)

    @property
    def latest_offset(self) -> int:
        """Offset of the most recently appended message, or -1 if empty."""
        with self._lock:
            return self._messages[-1].offset if self._messages else -1


# ---------------------------------------------------------------------------
# Message Broker
# ---------------------------------------------------------------------------

class MessageBroker:
    """
    Central broker that manages topics and consumer-group offsets.

    Args:
        default_retention_seconds: Applied to every new topic unless
                                    overridden.  ``None`` = keep forever.

    Example::

        broker = MessageBroker()
        broker.create_topic("orders")
        broker.publish("orders", "item-123", key="user-42")
        broker.publish("orders", "item-456", key="user-7")

        msgs = broker.consume("orders", group="billing", batch_size=2)
        for m in msgs:
            print(m.offset, m.value)  # 0 item-123 / 1 item-456

        msgs = broker.consume("orders", group="shipping", batch_size=1)
        print(msgs[0].value)          # item-123  (independent offset)
    """

    def __init__(self, default_retention_seconds: float | None = None) -> None:
        self._default_retention = default_retention_seconds
        self._topics: dict[str, Topic] = {}
        # (topic_name, group_name) → next offset to consume
        self._offsets: dict[tuple[str, str], int] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Topic management
    # ------------------------------------------------------------------

    def create_topic(self, name: str,
                     retention_seconds: float | None = None) -> Topic:
        """
        Create and register a new topic.

        If the topic already exists the existing instance is returned.
        """
        with self._lock:
            if name not in self._topics:
                retention = retention_seconds if retention_seconds is not None \
                    else self._default_retention
                self._topics[name] = Topic(name, retention)
            return self._topics[name]

    def list_topics(self) -> list[str]:
        """Return a sorted list of topic names."""
        with self._lock:
            return sorted(self._topics)

    def delete_topic(self, name: str) -> None:
        """
        Delete a topic and all its consumer-group offsets.

        Raises ``KeyError`` if the topic does not exist.
        """
        with self._lock:
            if name not in self._topics:
                raise KeyError(f"Topic '{name}' does not exist")
            del self._topics[name]
            stale = [k for k in self._offsets if k[0] == name]
            for k in stale:
                del self._offsets[k]

    # ------------------------------------------------------------------
    # Producing
    # ------------------------------------------------------------------

    def publish(self, topic_name: str, value: Any, *,
                key: str | None = None,
                headers: dict[str, str] | None = None,
                auto_create: bool = True) -> Message:
        """
        Publish *value* to *topic_name*.

        Args:
            topic_name:  Target topic.
            value:       Message payload (any Python object).
            key:         Optional routing key for ordering guarantees.
            headers:     Optional key/value metadata.
            auto_create: If ``True`` (default) the topic is created
                         automatically when it does not exist.

        Returns:
            The :class:`Message` that was appended.

        Raises:
            KeyError: If the topic does not exist and *auto_create* is
                      ``False``.
        """
        with self._lock:
            if topic_name not in self._topics:
                if not auto_create:
                    raise KeyError(f"Topic '{topic_name}' does not exist")
                self._topics[topic_name] = Topic(
                    topic_name, self._default_retention
                )
            topic = self._topics[topic_name]
        return topic.append(value, key=key, headers=headers)

    # ------------------------------------------------------------------
    # Consuming
    # ------------------------------------------------------------------

    def consume(self, topic_name: str, group: str,
                batch_size: int = 1) -> list[Message]:
        """
        Consume up to *batch_size* messages from *topic_name* for *group*.

        The group's offset is advanced after each successful read.

        Args:
            topic_name: Topic to read from.
            group:      Consumer group identifier.
            batch_size: Maximum messages to return.

        Returns:
            List of :class:`Message` objects (may be shorter than *batch_size*
            if fewer messages are available).

        Raises:
            KeyError: If *topic_name* does not exist.
        """
        with self._lock:
            if topic_name not in self._topics:
                raise KeyError(f"Topic '{topic_name}' does not exist")
            topic = self._topics[topic_name]
            offset_key = (topic_name, group)
            current_offset = self._offsets.get(offset_key, 0)

        messages = topic.read(current_offset, batch_size)

        if messages:
            next_offset = messages[-1].offset + 1
            with self._lock:
                self._offsets[(topic_name, group)] = next_offset

        return messages

    def seek(self, topic_name: str, group: str, offset: int) -> None:
        """
        Reset the offset for *group* on *topic_name* to *offset*.

        Set *offset* to 0 to replay from the beginning.

        Raises:
            KeyError: If *topic_name* does not exist.
            ValueError: If *offset* is negative.
        """
        if offset < 0:
            raise ValueError("offset must be non-negative")
        with self._lock:
            if topic_name not in self._topics:
                raise KeyError(f"Topic '{topic_name}' does not exist")
            self._offsets[(topic_name, group)] = offset

    def get_offset(self, topic_name: str, group: str) -> int:
        """Return the current read offset for *group* on *topic_name*."""
        with self._lock:
            return self._offsets.get((topic_name, group), 0)

    def lag(self, topic_name: str, group: str) -> int:
        """
        Return the number of unread messages for *group* on *topic_name*.

        A lag of 0 means the group is fully caught up.
        """
        with self._lock:
            if topic_name not in self._topics:
                raise KeyError(f"Topic '{topic_name}' does not exist")
            topic = self._topics[topic_name]
            latest = topic.latest_offset
            if latest == -1:
                return 0
            current = self._offsets.get((topic_name, group), 0)
            return max(0, latest - current + 1)
