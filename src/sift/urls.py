"""URL safety helpers: scheme allowlisting (anti-XSS) and SSRF host checks.

`html.escape` is the wrong tool for URL-attribute safety — it leaves dangerous
schemes like ``javascript:`` intact. These helpers gate URLs by scheme before
they reach an href, and by resolved host before they reach an HTTP request.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

ALLOWED_SCHEMES = ("http", "https")
# Browsers ignore leading control/space bytes before a scheme, so strip them
# before deciding whether a URL is "really" http(s).
_LEADING_JUNK = "".join(chr(c) for c in range(0x21))


def _clean(url: str) -> str:
    return url.strip().lstrip(_LEADING_JUNK)


def is_http_url(url: str) -> bool:
    """True only for well-formed http/https URLs with a host (scheme allowlist)."""
    try:
        parts = urlsplit(_clean(url))
    except ValueError:
        return False
    return parts.scheme.lower() in ALLOWED_SCHEMES and bool(parts.netloc)


def safe_href(url: str) -> str:
    """Return the URL for rendering only if it is http(s); otherwise '#'.

    Use at every HTML href sink so an attacker-controlled feed link can never
    become a ``javascript:``/``data:`` href in the published or emailed digest.
    """
    return url if is_http_url(url) else "#"


def is_safe_fetch_target(url: str) -> bool:
    """http(s) scheme AND host does not resolve to a private/internal address.

    Blocks SSRF to loopback, RFC1918, link-local (incl. cloud metadata
    169.254.169.254), reserved, and multicast ranges. If the host cannot be
    resolved here, returns True and lets the real request fail naturally rather
    than blocking a transient DNS hiccup.
    """
    if not is_http_url(url):
        return False
    host = urlsplit(_clean(url)).hostname
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True
