# Project 5 — Pub/Sub Message Queue

## Overview

A **Pub/Sub Message Queue** decouples producers from consumers.  Producers send messages to named **topics**; consumers join **consumer groups** and process messages independently, each maintaining their own read offset — exactly like Apache Kafka.

## System Design

```
Producer A ──► Topic "orders"  ──► Consumer Group "billing"  (offset=5)
                                └──► Consumer Group "shipping" (offset=3)

Producer B ──► Topic "events"  ──► Consumer Group "analytics" (offset=12)
```

### Key Concepts

| Concept | Description |
|---|---|
| **Topic** | Named channel; messages are appended in order |
| **Message** | Payload + metadata (id, timestamp, key, headers) |
| **Consumer Group** | Set of consumers sharing an independent read offset per topic |
| **Offset** | Index into the topic's message log |
| **Retention** | Messages are kept for N seconds or until manually deleted |
| **Replay** | Any group can seek to an earlier offset and re-read messages |

### Message Flow

```
publish("orders", "item-123")
   → appended at offset 7

consume("orders", group="billing", batch_size=3)
   → returns messages [5, 6, 7]
   → group offset advances to 8

seek("orders", group="billing", offset=0)
   → replay from the beginning
```

## Running Tests

```bash
pip install pytest
pytest tests/
```

## Extending to Production

- Persist messages to disk (write-ahead log) for durability
- Partition topics across multiple brokers for horizontal scalability
- Add consumer rebalancing when group members join/leave
- Implement acknowledgement + dead-letter queue for at-least-once delivery
- Add TLS + SASL authentication
