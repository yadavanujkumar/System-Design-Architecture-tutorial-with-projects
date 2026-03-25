# System Design Architecture — Tutorial with Projects

A hands-on tutorial covering the most important **System Design** concepts, each paired with a working Python implementation you can run, study, and extend.

> 📖 **New:** See [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md) for a comprehensive deep-dive into system design theory, principles, and real-world case studies (Netflix, Amazon, Twitter/X, Uber, WhatsApp) with Mermaid diagrams.

---

## Table of Contents

1. [What is System Design?](#what-is-system-design)
2. [Core Concepts](#core-concepts)
3. [Projects](#projects)
4. [How to Run](#how-to-run)
5. [Architecture Diagrams](#architecture-diagrams)

---

## What is System Design?

System Design is the process of defining the **architecture, components, modules, interfaces, and data flows** of a system to satisfy specified requirements. It bridges business requirements and engineering implementation.

Key goals:
- **Scalability** — handle growing load gracefully
- **Availability** — stay up even when parts fail
- **Reliability** — produce correct results consistently
- **Performance** — respond quickly under load
- **Maintainability** — easy to change and operate

```mermaid
flowchart TD
    A[Clarify Requirements] --> B[Estimate Scale]
    B --> C[Define API / Interfaces]
    C --> D[High-Level Architecture]
    D --> E[Deep-Dive Components]
    E --> F[Identify Bottlenecks]
    F --> G[Add Resilience & Observability]
    G --> H[Iterate & Validate]
```

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
| **Circuit Breaker** | Prevent cascading failures when a downstream service is unhealthy |

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

### [Project 6 — Circuit Breaker](./06-circuit-breaker/)

**Concepts demonstrated:** finite state machine, fail-fast, cascading failure prevention, automatic recovery, thread safety.

A production-grade Circuit Breaker implementation inspired by Netflix Hystrix. The breaker moves through three states (CLOSED → OPEN → HALF_OPEN) to protect services from being taken down by failing dependencies.

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
pytest 06-circuit-breaker/tests/
```

---

## Architecture Diagrams

### URL Shortener

```mermaid
sequenceDiagram
    participant C as Client
    participant API as API Server (Flask)
    participant DB as SQLite Database

    C->>API: POST /shorten {"url": "https://example.com/very/long/url"}
    API->>API: Base62(MD5(long_url)) → short_code
    API->>DB: INSERT (short_code, long_url, expires_at)
    API-->>C: {"short_url": "http://localhost/aB3xYz"}

    C->>API: GET /aB3xYz
    API->>DB: SELECT long_url WHERE short_code = 'aB3xYz'
    DB-->>API: long_url
    API-->>C: 302 Redirect → https://example.com/very/long/url
```

### Rate Limiter (Token Bucket)

```mermaid
flowchart TD
    Request[Incoming Request] --> Check{Tokens available?}
    Check -->|Yes: tokens > 0| Consume[Consume 1 token\nAllow request]
    Check -->|No: tokens == 0| Reject[Reject request\n429 Too Many Requests]
    Refill[Background refill\n+rate tokens/sec] --> Bucket[(Token Bucket)]
    Bucket --> Check
```

### LRU Cache

```mermaid
graph LR
    subgraph Cache["LRU Cache (capacity=3)"]
        direction LR
        Head[HEAD sentinel] <--> A[key=C\nMRU] <--> B[key=B] <--> C[key=A\nLRU] <--> Tail[TAIL sentinel]
    end
    HashMap["HashMap\n{A→nodeA, B→nodeB, C→nodeC}"] -.->|O(1) lookup| A & B & C
```

### Consistent Hash Ring

```mermaid
graph TD
    subgraph Ring["Consistent Hash Ring"]
        K1([key: user:42\nhashes to 95°]) -->|clockwise → first node| NA["node-A (120°)"]
        NA --- NB["node-B (240°)"]
        NB --- NC["node-C (360°/0°)"]
        NC --- NA
    end
```

### Pub/Sub Message Queue

```mermaid
graph LR
    Producer -->|publish| Topic[Topic: orders\nmsg1 msg2 msg3 msg4 msg5]
    Topic -->|offset=3| GroupA[Consumer Group A\nEmail Service]
    Topic -->|offset=5| GroupB[Consumer Group B\nAnalytics Service]
    Topic -->|offset=1| GroupC[Consumer Group C\nWarehouse Service]
```

### Circuit Breaker

```mermaid
stateDiagram-v2
    [*] --> Closed : Initial state
    Closed --> Open : failures ≥ threshold
    Open --> HalfOpen : cooldown elapsed
    HalfOpen --> Closed : probe succeeds
    HalfOpen --> Open : probe fails
```
