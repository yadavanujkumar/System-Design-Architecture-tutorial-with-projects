"""Tests for the URL Shortener."""

import time
import pytest

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app, init_db, shorten_url, resolve_url, get_stats, _base62_encode, _url_to_code, DB_PATH


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Use an isolated temporary database for every test."""
    import app as app_module
    db = tmp_path / "test_urls.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    init_db()
    yield
    if db.exists():
        db.unlink()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Unit tests — encoding helpers
# ---------------------------------------------------------------------------

def test_base62_encode_zero():
    assert _base62_encode(0) == "a"


def test_base62_encode_positive():
    code = _base62_encode(12345)
    assert all(c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" for c in code)


def test_url_to_code_length():
    code = _url_to_code("https://example.com", length=6)
    assert len(code) == 6


def test_url_to_code_deterministic():
    url = "https://example.com/path"
    assert _url_to_code(url) == _url_to_code(url)


def test_url_to_code_different_urls_differ():
    code1 = _url_to_code("https://example.com/a")
    code2 = _url_to_code("https://example.com/b")
    assert code1 != code2


# ---------------------------------------------------------------------------
# Unit tests — service logic
# ---------------------------------------------------------------------------

def test_shorten_returns_code():
    code = shorten_url("https://example.com")
    assert isinstance(code, str)
    assert len(code) >= 6


def test_shorten_same_url_returns_same_code():
    url = "https://example.com/same"
    assert shorten_url(url) == shorten_url(url)


def test_shorten_different_urls_return_different_codes():
    code1 = shorten_url("https://example.com/a")
    code2 = shorten_url("https://example.com/b")
    assert code1 != code2


def test_resolve_returns_url():
    url = "https://example.com/resolve"
    code = shorten_url(url)
    row = resolve_url(code)
    assert row is not None
    assert row["long_url"] == url


def test_resolve_increments_clicks():
    code = shorten_url("https://example.com/clicks")
    resolve_url(code)
    resolve_url(code)
    stats = get_stats(code)
    assert stats["clicks"] == 2


def test_resolve_unknown_code_returns_none():
    assert resolve_url("xxxxxx") is None


def test_resolve_expired_link_returns_none():
    code = shorten_url("https://example.com/expiry", ttl_seconds=-1)
    assert resolve_url(code) is None


def test_get_stats_returns_metadata():
    url = "https://example.com/stats"
    code = shorten_url(url)
    stats = get_stats(code)
    assert stats["long_url"] == url
    assert stats["clicks"] == 0
    assert stats["created_at"] > 0


# ---------------------------------------------------------------------------
# Integration tests — Flask routes
# ---------------------------------------------------------------------------

def test_api_shorten_success(client):
    resp = client.post("/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert "short_code" in data
    assert "short_url" in data


def test_api_shorten_missing_url(client):
    resp = client.post("/shorten", json={})
    assert resp.status_code == 400


def test_api_redirect_success(client):
    url = "https://example.com/redirect-target"
    resp = client.post("/shorten", json={"url": url})
    code = resp.get_json()["short_code"]
    redir = client.get(f"/{code}")
    assert redir.status_code == 302
    assert redir.headers["Location"] == url


def test_api_redirect_not_found(client):
    resp = client.get("/nonexistent123")
    assert resp.status_code == 404


def test_api_stats_success(client):
    url = "https://example.com/api-stats"
    resp = client.post("/shorten", json={"url": url})
    code = resp.get_json()["short_code"]
    stats = client.get(f"/stats/{code}").get_json()
    assert stats["long_url"] == url
    assert stats["clicks"] == 0


def test_api_stats_not_found(client):
    resp = client.get("/stats/nonexistent")
    assert resp.status_code == 404
