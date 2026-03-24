"""
URL Shortener — Project 1
=========================
Demonstrates: Base62 encoding, hash-based deduplication, SQLite persistence,
              click tracking, and link expiry.
"""

import hashlib
import sqlite3
import string
import time
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, redirect, request

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).parent / "urls.db"
BASE62_ALPHABET = string.ascii_letters + string.digits  # a-z A-Z 0-9
MIN_CODE_LENGTH = 6


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    """Return a thread-local SQLite connection with row_factory set."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS urls (
                short_code  TEXT PRIMARY KEY,
                long_url    TEXT NOT NULL,
                clicks      INTEGER NOT NULL DEFAULT 0,
                created_at  REAL NOT NULL,
                expires_at  REAL
            )
            """
        )


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

def _base62_encode(number: int) -> str:
    """Encode a non-negative integer to a Base62 string."""
    if number == 0:
        return BASE62_ALPHABET[0]
    chars: list[str] = []
    while number:
        number, remainder = divmod(number, 62)
        chars.append(BASE62_ALPHABET[remainder])
    return "".join(reversed(chars))


def _url_to_code(long_url: str, length: int = MIN_CODE_LENGTH) -> str:
    """
    Derive a short code from a URL using MD5.

    Takes the first ``length`` characters of the Base62-encoded MD5 digest.
    The caller increases ``length`` on collision.
    """
    digest = hashlib.md5(long_url.encode()).hexdigest()
    number = int(digest, 16)
    encoded = _base62_encode(number)
    return encoded[:length]


# ---------------------------------------------------------------------------
# Core service logic
# ---------------------------------------------------------------------------

def shorten_url(long_url: str, ttl_seconds: float | None = None) -> str:
    """
    Return (or create) a short code for *long_url*.

    If the URL was already shortened the existing code is returned.
    If a code collision with a *different* URL occurs the code length is
    extended by one character until a free slot is found.
    """
    conn = get_db()
    try:
        # Check whether this exact URL already has a code
        row = conn.execute(
            "SELECT short_code FROM urls WHERE long_url = ?", (long_url,)
        ).fetchone()
        if row:
            return row["short_code"]

        # Derive a code; retry with longer codes on collision
        length = MIN_CODE_LENGTH
        while True:
            code = _url_to_code(long_url, length)
            existing = conn.execute(
                "SELECT long_url FROM urls WHERE short_code = ?", (code,)
            ).fetchone()
            if existing is None:
                break  # free slot found
            if existing["long_url"] == long_url:
                return code  # same URL already stored (race condition safety)
            length += 1  # collision with a different URL — try longer code

        now = time.time()
        expires_at = (now + ttl_seconds) if ttl_seconds is not None else None
        conn.execute(
            "INSERT INTO urls (short_code, long_url, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (code, long_url, now, expires_at),
        )
        conn.commit()
        return code
    finally:
        conn.close()


def resolve_url(short_code: str) -> dict | None:
    """
    Look up *short_code* and increment its click counter.

    Returns the row dict on success, or ``None`` when not found or expired.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM urls WHERE short_code = ?", (short_code,)
        ).fetchone()
        if row is None:
            return None
        if row["expires_at"] is not None and time.time() > row["expires_at"]:
            return None  # expired
        conn.execute(
            "UPDATE urls SET clicks = clicks + 1 WHERE short_code = ?",
            (short_code,),
        )
        conn.commit()
        return dict(row)
    finally:
        conn.close()


def get_stats(short_code: str) -> dict | None:
    """Return stats for *short_code* without incrementing clicks."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM urls WHERE short_code = ?", (short_code,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.route("/shorten", methods=["POST"])
def api_shorten():
    """Create a short URL.

    Request body (JSON):
        url          (str, required)  — the long URL to shorten
        ttl_seconds  (float, optional) — seconds until the link expires
    """
    data = request.get_json(silent=True) or {}
    long_url = data.get("url", "").strip()
    if not long_url:
        return jsonify({"error": "Missing 'url' field"}), 400

    ttl = data.get("ttl_seconds")
    code = shorten_url(long_url, ttl_seconds=ttl)
    short_url = request.host_url.rstrip("/") + "/" + code
    return jsonify({"short_code": code, "short_url": short_url}), 201


@app.route("/<short_code>")
def api_redirect(short_code: str):
    """Redirect to the original URL."""
    row = resolve_url(short_code)
    if row is None:
        return jsonify({"error": "Short URL not found or expired"}), 404
    return redirect(row["long_url"], code=302)


@app.route("/stats/<short_code>")
def api_stats(short_code: str):
    """Return stats for a short code without following the redirect."""
    row = get_stats(short_code)
    if row is None:
        return jsonify({"error": "Short URL not found"}), 404
    return jsonify(
        {
            "short_code": row["short_code"],
            "long_url": row["long_url"],
            "clicks": row["clicks"],
            "created_at": datetime.fromtimestamp(
                row["created_at"], tz=timezone.utc
            ).isoformat(),
            "expires_at": (
                datetime.fromtimestamp(row["expires_at"], tz=timezone.utc).isoformat()
                if row["expires_at"]
                else None
            ),
        }
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
