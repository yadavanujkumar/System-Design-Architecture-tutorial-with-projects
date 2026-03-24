# Project 2 — Rate Limiter

## Overview

A **Rate Limiter** protects services from being overwhelmed by restricting how many requests a client can make in a time window. This project demonstrates two battle-tested algorithms:

| Algorithm | Pros | Cons |
|---|---|---|
| **Token Bucket** | Allows short bursts; simple | Bucket state must be stored per-client |
| **Sliding Window Counter** | Smooth, no burst spikes | Slightly higher memory per client |

## System Design

```
Incoming request
      │
      ▼
 Rate Limiter
      │
   allowed?
   ├── Yes → forward to upstream service
   └── No  → 429 Too Many Requests
```

### Token Bucket Algorithm

```
bucket_capacity = 10 tokens
refill_rate     = 2 tokens/second

On each request:
  1. tokens += (now - last_refill) * refill_rate
  2. tokens  = min(tokens, capacity)
  3. if tokens >= 1: tokens -= 1; allow
     else: reject
```

### Sliding Window Counter Algorithm

```
window_size  = 1 second
max_requests = 5 per window

On each request:
  1. Drop timestamps older than (now - window_size)
  2. If len(timestamps) < max_requests: allow and record timestamp
     Else: reject
```

## Running Tests

```bash
pip install pytest
pytest tests/
```

## Extending to Production

- Store bucket/window state in **Redis** using atomic Lua scripts (prevents race conditions)
- Apply limits per user ID, API key, or IP address
- Return `Retry-After` header so clients know when to retry
- Use a distributed lock or Redis INCR + EXPIRE for cluster deployments
