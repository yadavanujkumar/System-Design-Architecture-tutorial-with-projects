# System Design Architecture — Tutorial with Projects

A hands-on tutorial covering the most important **System Design** concepts, each paired with a working Python implementation you can run, study, and extend.

---

## Table of Contents

1. [What is System Design?](#what-is-system-design)
2. [Core Concepts](#core-concepts)
3. [Projects](#projects)
4. [How to Run](#how-to-run)

---

## What is System Design?

System Design is the process of defining the **architecture, components, modules, interfaces, and data flows** of a system to satisfy specified requirements. It bridges business requirements and engineering implementation.

Key goals:
- **Scalability** — handle growing load gracefully
- **Availability** — stay up even when parts fail
- **Reliability** — produce correct results consistently
- **Performance** — respond quickly under load
- **Maintainability** — easy to change and operate

---

## Core Concepts

| Concept | Description |
|---|---|
| **Horizontal Scaling** | Add more machines to distribute load |
| **Vertical Scaling** | Upgrade existing machines (CPU/RAM) |
| **Load Balancing** | Distribute requests evenly across servers |
| **Caching** | Store frequently-accessed data close to consumers |
| **Consistent Hashing** | Minimise key remapping when nodes join/leave |
| **Rate Limiting** | Protect services from abuse and overload |
| **Message Queues** | Decouple producers and consumers asynchronously |
| **CAP Theorem** | A distributed system can guarantee at most 2 of: Consistency, Availability, Partition Tolerance |
| **Database Sharding** | Split a large database across multiple machines |
| **Replication** | Maintain copies of data on multiple nodes |

---

## Projects

### [Project 1 — URL Shortener](./01-url-shortener/)

**Concepts demonstrated:** hashing, storage, redirect logic, Base62 encoding, collision handling.

A fully functional URL shortening service (similar to bit.ly) built with Flask and SQLite. Supports:
- Creating short codes for long URLs
- Redirecting short codes to original URLs
- Click-count tracking
- Expiry support

### [Project 2 — Rate Limiter](./02-rate-limiter/)

**Concepts demonstrated:** Token Bucket algorithm, Sliding Window algorithm, thread safety.

Two production-grade rate-limiting algorithms implemented in Python:
- **Token Bucket** — allows bursts up to a configured capacity
- **Sliding Window Counter** — smooth per-second request limiting

### [Project 3 — LRU Cache](./03-lru-cache/)

**Concepts demonstrated:** doubly-linked list, hash map, O(1) get/put, eviction policy.

An O(1) Least-Recently-Used cache backed by a doubly-linked list and a dictionary — the same structure used in operating systems, browsers, and CDNs.

### [Project 4 — Consistent Hashing](./04-consistent-hashing/)

**Concepts demonstrated:** hash ring, virtual nodes, node addition/removal, minimal key remapping.

A hash ring with virtual node support. Adding or removing a server only remaps a small fraction of keys — critical for distributed caches and databases.

### [Project 5 — Pub/Sub Message Queue](./05-message-queue/)

**Concepts demonstrated:** publish/subscribe pattern, topics, consumer groups, offset tracking, async decoupling.

An in-memory message broker inspired by Apache Kafka. Supports multiple topics, multiple consumer groups with independent offsets, and message retention.

---

## How to Run

### Prerequisites

```
Python 3.8+
pip
```

### Install dependencies

Each project has its own `requirements.txt`. For example:

```bash
cd 01-url-shortener
pip install -r requirements.txt
python app.py
```

### Run tests

Each project includes a `tests/` directory with `pytest` tests:

```bash
# Run all tests across all projects
pip install pytest
pytest

# Run tests for one project
pytest 01-url-shortener/tests/
```

---

## Architecture Diagrams

### URL Shortener

```
Client ──► [API Server] ──► [SQLite / Database]
                │
                └──► Base62(hash(long_url)) → short_code
```

### Rate Limiter (Token Bucket)

```
Request ──► Check bucket
              │
         tokens > 0 ?
           ├── Yes → consume token, allow request
           └── No  → reject (429 Too Many Requests)
```

### LRU Cache

```
GET(key):  HashMap O(1) lookup → move node to head → return value
PUT(key):  HashMap insert → add node to head → evict tail if over capacity
```

### Consistent Hash Ring

```
         node-A (0°)
        /            \
   node-C            node-B
    (240°)           (120°)
        \            /
         key maps to nearest node clockwise
```

### Pub/Sub Message Queue

```
Producer ──► Topic ──► [msg1, msg2, msg3 ...]
                              │
               ┌──────────────┼──────────────┐
            Group-A        Group-B        Group-C
           (offset=2)     (offset=3)     (offset=1)
```
