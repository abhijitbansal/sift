"""Unit tests for URL safety helpers (scheme allowlist + SSRF host checks)."""

import socket

import pytest

from sift import urls


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/feed.xml",
        "http://example.com",
        "  https://example.com/x  ",
    ],
)
def test_is_http_url_accepts_http_and_https(url):
    assert urls.is_http_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "file:///etc/passwd",
        "ftp://example.com",
        "",
        "not a url",
        "https://",  # no netloc
    ],
)
def test_is_http_url_rejects_other_schemes(url):
    assert urls.is_http_url(url) is False


def test_safe_href_passes_http_urls():
    assert urls.safe_href("https://example.com/x") == "https://example.com/x"


def test_safe_href_neutralizes_javascript():
    assert urls.safe_href("javascript:alert(document.cookie)") == "#"


def test_is_safe_fetch_target_rejects_loopback_and_link_local():
    # Literal IPs: getaddrinfo resolves them locally (no network).
    assert urls.is_safe_fetch_target("http://127.0.0.1/x") is False
    assert urls.is_safe_fetch_target("http://169.254.169.254/latest/meta-data/") is False


def test_is_safe_fetch_target_rejects_private_ip():
    assert urls.is_safe_fetch_target("http://10.0.0.5/feed") is False
    assert urls.is_safe_fetch_target("http://192.168.1.1/feed") is False


def test_is_safe_fetch_target_rejects_non_http_scheme():
    assert urls.is_safe_fetch_target("javascript:alert(1)") is False


def test_is_safe_fetch_target_allows_public_host(monkeypatch):
    monkeypatch.setattr(
        urls.socket,
        "getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )
    assert urls.is_safe_fetch_target("https://example.com/feed") is True


def test_is_safe_fetch_target_allows_when_unresolvable(monkeypatch):
    def boom(*a, **k):
        raise socket.gaierror("no such host")

    monkeypatch.setattr(urls.socket, "getaddrinfo", boom)
    # Cannot resolve here → let the real request fail naturally rather than block.
    assert urls.is_safe_fetch_target("https://nonexistent.invalid/feed") is True
