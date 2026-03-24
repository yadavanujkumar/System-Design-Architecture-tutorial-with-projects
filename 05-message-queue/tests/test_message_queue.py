"""Tests for the Pub/Sub Message Queue implementation."""

import time
import threading
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from message_queue import Message, Topic, MessageBroker


# ---------------------------------------------------------------------------
# Topic tests
# ---------------------------------------------------------------------------

class TestTopic:
    def test_append_returns_message(self):
        topic = Topic("test")
        msg = topic.append("hello")
        assert isinstance(msg, Message)
        assert msg.value == "hello"
        assert msg.offset == 0

    def test_offset_increments(self):
        topic = Topic("test")
        m0 = topic.append("a")
        m1 = topic.append("b")
        assert m1.offset == m0.offset + 1

    def test_read_from_offset(self):
        topic = Topic("test")
        topic.append("a")
        topic.append("b")
        topic.append("c")
        msgs = topic.read(from_offset=1, batch_size=10)
        assert len(msgs) == 2
        assert msgs[0].value == "b"

    def test_read_respects_batch_size(self):
        topic = Topic("test")
        for i in range(5):
            topic.append(i)
        msgs = topic.read(from_offset=0, batch_size=2)
        assert len(msgs) == 2

    def test_len(self):
        topic = Topic("test")
        for i in range(3):
            topic.append(i)
        assert len(topic) == 3

    def test_latest_offset_empty(self):
        topic = Topic("test")
        assert topic.latest_offset == -1

    def test_latest_offset(self):
        topic = Topic("test")
        topic.append("x")
        topic.append("y")
        assert topic.latest_offset == 1

    def test_retention_expires_messages(self):
        topic = Topic("test", retention_seconds=0.01)
        topic.append("old")
        time.sleep(0.02)
        topic.append("new")
        msgs = topic.read(from_offset=0, batch_size=10)
        values = [m.value for m in msgs]
        assert "old" not in values
        assert "new" in values

    def test_message_has_id_and_timestamp(self):
        topic = Topic("test")
        msg = topic.append("payload", key="k1", headers={"h": "v"})
        assert msg.message_id
        assert msg.timestamp > 0
        assert msg.key == "k1"
        assert msg.headers == {"h": "v"}


# ---------------------------------------------------------------------------
# Broker — topic management
# ---------------------------------------------------------------------------

class TestBrokerTopicManagement:
    def test_create_and_list_topics(self):
        broker = MessageBroker()
        broker.create_topic("a")
        broker.create_topic("b")
        assert broker.list_topics() == ["a", "b"]

    def test_create_topic_idempotent(self):
        broker = MessageBroker()
        t1 = broker.create_topic("t")
        t2 = broker.create_topic("t")
        assert t1 is t2

    def test_delete_topic(self):
        broker = MessageBroker()
        broker.create_topic("t")
        broker.delete_topic("t")
        assert "t" not in broker.list_topics()

    def test_delete_nonexistent_topic_raises(self):
        broker = MessageBroker()
        with pytest.raises(KeyError):
            broker.delete_topic("ghost")


# ---------------------------------------------------------------------------
# Broker — publishing
# ---------------------------------------------------------------------------

class TestBrokerPublish:
    def test_publish_auto_creates_topic(self):
        broker = MessageBroker()
        broker.publish("new-topic", "hello")
        assert "new-topic" in broker.list_topics()

    def test_publish_without_auto_create_raises(self):
        broker = MessageBroker()
        with pytest.raises(KeyError):
            broker.publish("missing", "data", auto_create=False)

    def test_publish_returns_message(self):
        broker = MessageBroker()
        msg = broker.publish("t", "value", key="k")
        assert msg.value == "value"
        assert msg.key == "k"


# ---------------------------------------------------------------------------
# Broker — consuming
# ---------------------------------------------------------------------------

class TestBrokerConsume:
    def test_consume_returns_messages(self):
        broker = MessageBroker()
        broker.publish("t", "a")
        broker.publish("t", "b")
        msgs = broker.consume("t", group="g", batch_size=2)
        assert [m.value for m in msgs] == ["a", "b"]

    def test_consume_advances_offset(self):
        broker = MessageBroker()
        broker.publish("t", "a")
        broker.consume("t", group="g")
        assert broker.get_offset("t", "g") == 1

    def test_consume_returns_next_batch(self):
        broker = MessageBroker()
        for i in range(4):
            broker.publish("t", i)
        broker.consume("t", group="g", batch_size=2)
        msgs = broker.consume("t", group="g", batch_size=2)
        assert [m.value for m in msgs] == [2, 3]

    def test_consume_returns_empty_when_caught_up(self):
        broker = MessageBroker()
        broker.publish("t", "a")
        broker.consume("t", group="g")
        assert broker.consume("t", group="g") == []

    def test_two_groups_are_independent(self):
        broker = MessageBroker()
        broker.publish("t", "x")
        msgs_a = broker.consume("t", group="a")
        msgs_b = broker.consume("t", group="b")
        assert msgs_a[0].value == "x"
        assert msgs_b[0].value == "x"

    def test_consume_nonexistent_topic_raises(self):
        broker = MessageBroker()
        with pytest.raises(KeyError):
            broker.consume("ghost", group="g")


# ---------------------------------------------------------------------------
# Broker — seek / offset / lag
# ---------------------------------------------------------------------------

class TestBrokerSeekAndLag:
    def test_seek_to_zero_allows_replay(self):
        broker = MessageBroker()
        broker.publish("t", "a")
        broker.publish("t", "b")
        broker.consume("t", group="g", batch_size=2)
        broker.seek("t", group="g", offset=0)
        msgs = broker.consume("t", group="g", batch_size=2)
        assert [m.value for m in msgs] == ["a", "b"]

    def test_seek_negative_raises(self):
        broker = MessageBroker()
        broker.create_topic("t")
        with pytest.raises(ValueError):
            broker.seek("t", group="g", offset=-1)

    def test_seek_nonexistent_topic_raises(self):
        broker = MessageBroker()
        with pytest.raises(KeyError):
            broker.seek("ghost", group="g", offset=0)

    def test_lag_full(self):
        broker = MessageBroker()
        broker.publish("t", "a")
        broker.publish("t", "b")
        assert broker.lag("t", "g") == 2

    def test_lag_zero_when_caught_up(self):
        broker = MessageBroker()
        broker.publish("t", "a")
        broker.consume("t", group="g")
        assert broker.lag("t", "g") == 0

    def test_lag_empty_topic(self):
        broker = MessageBroker()
        broker.create_topic("t")
        assert broker.lag("t", "g") == 0


# ---------------------------------------------------------------------------
# Thread-safety
# ---------------------------------------------------------------------------

class TestBrokerThreadSafety:
    def test_concurrent_publish(self):
        broker = MessageBroker()
        broker.create_topic("t")

        def publish_batch():
            for i in range(50):
                broker.publish("t", i)

        threads = [threading.Thread(target=publish_batch) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All 200 messages should be present with unique offsets
        msgs = broker.consume("t", group="counter", batch_size=300)
        assert len(msgs) == 200
        offsets = [m.offset for m in msgs]
        assert len(set(offsets)) == 200  # all unique
