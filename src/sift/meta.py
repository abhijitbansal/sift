"""Open Graph / Twitter head block — the static-raster large-image card that
makes Microsoft Teams / Slack render a titled link preview instead of a bare URL.

Verified against the known-good claude-skills page (2026-06): the single trigger
is a qualifying large-image card — a PNG/JPG ``og:image`` with declared
``og:image:width``/``height`` plus ``twitter:card=summary_large_image``. SVG or
animated-GIF images, or missing dimensions, do not qualify. No JSON-LD / canonical
is needed (the known-good page has none)."""

from __future__ import annotations

from html import escape
from urllib.parse import urljoin


def abs_url(base: str, rel: str) -> str:
    """Absolute URL for a site-relative path against a trailing-slash base.

    ``abs_url("https://x/sift/", "digests/2026-26.html")`` →
    ``"https://x/sift/digests/2026-26.html"``; an empty ``rel`` returns ``base``.
    """
    return urljoin(base, rel)


def og_tags(
    *,
    title: str,
    description: str,
    url: str,
    image: str,
    image_alt: str,
    width: int = 1200,
    height: int = 630,
    site_name: str = "Sift",
) -> str:
    """The OG/Twitter ``<head>`` block as an HTML string. All values are
    attribute-escaped; ``image`` must be an absolute https PNG/JPG URL."""

    def e(value: object) -> str:
        return escape(str(value), quote=True)

    return "\n".join(
        [
            '<meta property="og:type" content="website">',
            f'<meta property="og:site_name" content="{e(site_name)}">',
            f'<meta property="og:title" content="{e(title)}">',
            f'<meta property="og:description" content="{e(description)}">',
            f'<meta property="og:url" content="{e(url)}">',
            f'<meta property="og:image" content="{e(image)}">',
            f'<meta property="og:image:width" content="{int(width)}">',
            f'<meta property="og:image:height" content="{int(height)}">',
            f'<meta property="og:image:alt" content="{e(image_alt)}">',
            '<meta name="twitter:card" content="summary_large_image">',
            f'<meta name="twitter:title" content="{e(title)}">',
            f'<meta name="twitter:description" content="{e(description)}">',
            f'<meta name="twitter:image" content="{e(image)}">',
        ]
    )
