# Project 4 — Consistent Hashing

## Overview

**Consistent Hashing** solves the key-remapping problem in distributed caches and databases.  With a naive modulo hash (`key % N`), *every* key must be remapped when a node is added or removed.  Consistent hashing limits remapping to only `K/N` keys on average (where K = total keys, N = nodes).

## System Design

```
Hash Ring (0 to 2³²−1)

        0
       ╱╲
      ╱  ╲
    node-A  node-B
      ╲  ╱
       ╲╱
      node-C

  key → hash → walk clockwise → first node encountered = responsible node
```

### Virtual Nodes

Each physical node is mapped to **V** virtual positions on the ring. This:
- Evenly distributes load even with few physical nodes
- Reduces hotspots when nodes have different capacities
- Minimises variance in key distribution

### Adding / Removing Nodes

```
Before (nodes A, B, C):  K/3 keys each
Add node D:              only K/4 keys move from existing nodes to D
Remove node B:           only B's keys move to the next node clockwise
```

## Running Tests

```bash
pip install pytest
pytest tests/
```

## Production Usage

Consistent hashing is used in:
- **Amazon DynamoDB** — partition key routing
- **Apache Cassandra** — token ring
- **Memcached / Twemproxy** — client-side key routing
- **Nginx upstream hash** — `hash $request_uri consistent`
- **Chord DHT** — peer-to-peer distributed hash tables
