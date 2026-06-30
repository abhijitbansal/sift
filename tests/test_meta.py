"""Unit tests for the OG/Twitter head block."""

from sift.meta import abs_url, og_tags


def test_abs_url_joins_trailing_slash_base():
    base = "https://x.test/sift/"
    assert abs_url(base, "digests/2026-26.html") == "https://x.test/sift/digests/2026-26.html"
    assert abs_url(base, "") == base


def test_og_tags_has_static_image_card_signals():
    tags = og_tags(
        title="T",
        description="D",
        url="https://x.test/sift/",
        image="https://x.test/sift/og.png",
        image_alt="A",
    )
    assert 'property="og:image" content="https://x.test/sift/og.png"' in tags
    assert 'property="og:image:width" content="1200"' in tags
    assert 'property="og:image:height" content="630"' in tags
    assert 'name="twitter:card" content="summary_large_image"' in tags
    assert 'name="twitter:image" content="https://x.test/sift/og.png"' in tags


def test_og_tags_escapes_quotes():
    tags = og_tags(title='a"b', description="d", url="u", image="i", image_alt="x")
    assert "&quot;" in tags
    assert 'a"b' not in tags
