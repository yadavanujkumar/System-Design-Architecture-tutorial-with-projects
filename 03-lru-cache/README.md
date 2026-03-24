# Project 3 — LRU Cache

## Overview

A **Least-Recently-Used (LRU) Cache** automatically evicts the least-recently-accessed item when it reaches capacity.  It is used everywhere from operating system page tables to CDN edge nodes and browser memory management.

## System Design

```
Operations:
  get(key)       → value  or  -1 (miss)
  put(key, value) → (evicts LRU item if at capacity)
```

Both operations run in **O(1)** time using two data structures:

| Structure | Role |
|---|---|
| `dict` (hash map) | O(1) key → node lookup |
| Doubly-linked list | O(1) move-to-head and tail removal |

### How it works

```
capacity = 3

put(1, "a")  →  [1]
put(2, "b")  →  [2, 1]
put(3, "c")  →  [3, 2, 1]
get(1)       →  [1, 3, 2]   (1 moved to head — recently used)
put(4, "d")  →  [4, 1, 3]   (2 evicted — it was LRU)
```

The **head** is the most-recently-used item; the **tail** is the least-recently-used.

## Running Tests

```bash
pip install pytest
pytest tests/
```

## Real-world Usage

- **CPU L1/L2 caches** — hardware LRU replacement policy
- **Database buffer pool** — PostgreSQL, MySQL keep hot pages in memory
- **CDN edge caches** — Varnish, Nginx, Cloudflare
- **Browser HTTP cache** — Chrome, Firefox evict old assets
- **Redis** — `maxmemory-policy allkeys-lru` option
