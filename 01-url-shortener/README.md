# Project 1 — URL Shortener

## Overview

A URL shortening service (like bit.ly or tinyurl.com) converts a long URL into a short, shareable code. This project demonstrates:

- **Base62 encoding** for compact, URL-safe short codes
- **Hash-based deduplication** — the same long URL always maps to the same code
- **SQLite persistence** — survives restarts
- **Click tracking** — records how many times each link was visited
- **Link expiry** — optional TTL per short link

## System Design

```
POST /shorten
  Body: { "url": "https://example.com/very/long/path" }
  Response: { "short_code": "aB3xZ9", "short_url": "http://localhost:5000/aB3xZ9" }

GET /<short_code>
  → 302 redirect to original URL
  (or 404 / 410 if not found / expired)

GET /stats/<short_code>
  Response: { "url": "...", "clicks": 42, "created_at": "..." }
```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| MD5 of URL → first 6 Base62 chars | Deterministic; avoids duplicate rows for the same URL |
| Collision retry | If 6-char code collides with different URL, extend to 7, 8… chars |
| SQLite | Zero-dependency storage; swap for PostgreSQL/MySQL in production |
| 302 redirect | Allows click tracking before forwarding (301 would be cached) |

## Running Locally

```bash
pip install -r requirements.txt
python app.py
# Server starts at http://localhost:5000
```

### Example requests

```bash
# Shorten a URL
curl -X POST http://localhost:5000/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.github.com/very/long/repository/path"}'

# Follow the short link
curl -L http://localhost:5000/<short_code>

# View stats
curl http://localhost:5000/stats/<short_code>
```

## Running Tests

```bash
pip install pytest
pytest tests/
```
