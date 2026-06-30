"""Unit tests for config loading and validation."""

import pytest

from sift import config as config_mod

BASE = """
[sift]
interest_profile = "I care about agentic dev tooling."
"""


def write_config(tmp_path, body):
    path = tmp_path / "config.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_minimal_config(tmp_path):
    path = write_config(tmp_path, BASE + """
[[feeds]]
name = "Example"
url = "https://example.com/feed.xml"
""")

    cfg = config_mod.load_config(path)

    assert cfg.model == config_mod.DEFAULT_MODEL
    assert cfg.max_items_per_digest == config_mod.DEFAULT_MAX_ITEMS
    assert cfg.min_score == 1
    assert cfg.mute == ()
    assert cfg.email is None
    assert cfg.feeds[0].weight == 1.0


def test_boost_and_site_url_parsed(tmp_path):
    path = write_config(tmp_path, """
[sift]
interest_profile = "x"
boost = ["Ford", "  "]
site_url = "https://x.test/sift/"
[[feeds]]
name = "Example"
url = "https://example.com/feed.xml"
""")

    cfg = config_mod.load_config(path)

    assert cfg.boost == ("Ford",)  # blank entries are dropped
    assert cfg.site_url == "https://x.test/sift/"


def test_site_url_normalizes_missing_trailing_slash(tmp_path):
    path = write_config(tmp_path, """
[sift]
interest_profile = "x"
site_url = "https://x.test/sift"
[[feeds]]
name = "E"
url = "https://e/feed"
""")

    cfg = config_mod.load_config(path)

    assert cfg.site_url == "https://x.test/sift/"  # trailing slash enforced


def test_site_url_rejects_non_http(tmp_path):
    path = write_config(tmp_path, """
[sift]
interest_profile = "x"
site_url = "ftp://x.test/sift/"
[[feeds]]
name = "E"
url = "https://e/feed"
""")

    with pytest.raises(ValueError, match="site_url"):
        config_mod.load_config(path)


def test_boost_defaults_empty_and_site_url_default(tmp_path):
    path = write_config(tmp_path, BASE + """
[[feeds]]
name = "Example"
url = "https://example.com/feed.xml"
""")

    cfg = config_mod.load_config(path)

    assert cfg.boost == ()
    assert cfg.site_url == config_mod.DEFAULT_SITE_URL


def test_feed_weight_parsed(tmp_path):
    path = write_config(tmp_path, BASE + """
[[feeds]]
name = "Trusted"
url = "https://t"
weight = 2.5
""")

    cfg = config_mod.load_config(path)

    assert cfg.feeds[0].weight == 2.5


def test_zero_feed_weight_rejected(tmp_path):
    path = write_config(tmp_path, BASE + """
[[feeds]]
name = "Bad"
url = "https://b"
weight = 0
""")

    with pytest.raises(ValueError, match="weight must be > 0"):
        config_mod.load_config(path)


def test_mute_and_min_score_parsed(tmp_path):
    path = write_config(tmp_path, """
[sift]
interest_profile = "x"
min_score = 4
mute = ["chatbot drama", "  ", "ai doom"]

[[feeds]]
name = "F"
url = "https://f"
""")

    cfg = config_mod.load_config(path)

    assert cfg.min_score == 4
    assert cfg.mute == ("chatbot drama", "ai doom")  # blank entries dropped


def test_min_score_out_of_range_rejected(tmp_path):
    path = write_config(tmp_path, BASE.replace(
        "interest_profile", "min_score = 11\ninterest_profile"
    ) + """
[[feeds]]
name = "F"
url = "https://f"
""")

    with pytest.raises(ValueError, match="min_score"):
        config_mod.load_config(path)


def test_thinking_defaults_off(tmp_path):
    path = write_config(tmp_path, BASE + """
[[feeds]]
name = "F"
url = "https://f"
""")

    cfg = config_mod.load_config(path)

    assert cfg.thinking == "off"
    assert cfg.effort is None


def test_thinking_and_effort_parsed(tmp_path):
    path = write_config(tmp_path, """
[sift]
interest_profile = "x"
thinking = "adaptive"
effort = "low"

[[feeds]]
name = "F"
url = "https://f"
""")

    cfg = config_mod.load_config(path)

    assert cfg.thinking == "adaptive"
    assert cfg.effort == "low"


def test_invalid_thinking_rejected(tmp_path):
    path = write_config(tmp_path, """
[sift]
interest_profile = "x"
thinking = "sometimes"

[[feeds]]
name = "F"
url = "https://f"
""")

    with pytest.raises(ValueError, match="thinking"):
        config_mod.load_config(path)


def test_invalid_effort_rejected(tmp_path):
    path = write_config(tmp_path, """
[sift]
interest_profile = "x"
effort = "turbo"

[[feeds]]
name = "F"
url = "https://f"
""")

    with pytest.raises(ValueError, match="effort"):
        config_mod.load_config(path)


def test_x_bridge_url_parsed(tmp_path):
    path = write_config(tmp_path, """
[sift]
interest_profile = "x"

[x]
bridge_url = "https://nitter.net/{handle}/rss"

[[feeds]]
name = "F"
url = "https://f"
""")

    cfg = config_mod.load_config(path)

    assert cfg.x_bridge_url == "https://nitter.net/{handle}/rss"


def test_x_bridge_requires_handle_placeholder(tmp_path):
    path = write_config(tmp_path, """
[sift]
interest_profile = "x"

[x]
bridge_url = "https://nitter.net/rss"

[[feeds]]
name = "F"
url = "https://f"
""")

    with pytest.raises(ValueError, match="handle"):
        config_mod.load_config(path)


def test_x_bridge_defaults_none(tmp_path):
    path = write_config(tmp_path, BASE + """
[[feeds]]
name = "F"
url = "https://f"
""")

    assert config_mod.load_config(path).x_bridge_url is None


def test_email_disabled_block(tmp_path):
    path = write_config(tmp_path, BASE + """
[[feeds]]
name = "F"
url = "https://f"

[email]
enabled = false
""")

    cfg = config_mod.load_config(path)

    assert cfg.email is not None
    assert cfg.email.enabled is False


def test_email_enabled_requires_fields(tmp_path):
    path = write_config(tmp_path, BASE + """
[[feeds]]
name = "F"
url = "https://f"

[email]
enabled = true
host = "smtp.example.com"
""")

    with pytest.raises(ValueError, match="missing 'from'"):
        config_mod.load_config(path)


def test_email_enabled_full(tmp_path):
    path = write_config(tmp_path, BASE + """
[[feeds]]
name = "F"
url = "https://f"

[email]
enabled = true
host = "smtp.example.com"
from = "sift@example.com"
to = "me@example.com"
port = 465
use_tls = true
""")

    cfg = config_mod.load_config(path)

    assert cfg.email.enabled is True
    assert cfg.email.host == "smtp.example.com"
    assert cfg.email.sender == "sift@example.com"
    assert cfg.email.recipient == "me@example.com"
    assert cfg.email.port == 465


def test_append_feed_escapes_injection_and_keeps_config_parseable(tmp_path):
    path = write_config(tmp_path, BASE + """
[[feeds]]
name = "F"
url = "https://f"
""")

    # Hostile remote feed title attempting TOML breakout to override the model.
    config_mod.append_feed(path, 'Evil"\nmodel = "pwned', "https://evil.example.com/feed")

    cfg = config_mod.load_config(path)  # must still parse

    assert cfg.model == config_mod.DEFAULT_MODEL  # injection did NOT override model
    assert any("Evil" in f.name for f in cfg.feeds)


def test_append_feed_collapses_whitespace_in_name(tmp_path):
    path = write_config(tmp_path, BASE + """
[[feeds]]
name = "F"
url = "https://f"
""")

    config_mod.append_feed(path, "Multi\nLine\tTitle", "https://ok.example.com/feed")

    cfg = config_mod.load_config(path)

    assert "Multi Line Title" in [f.name for f in cfg.feeds]


def test_append_feed_rolls_back_unchanged_on_unencodable_name(tmp_path):
    path = write_config(tmp_path, BASE + """
[[feeds]]
name = "F"
url = "https://f"
""")
    before = path.read_text(encoding="utf-8")

    with pytest.raises(ValueError):  # lone surrogate can't encode to utf-8
        config_mod.append_feed(path, "bad\ud800title", "https://ok.example.com/feed")

    assert path.read_text(encoding="utf-8") == before  # file untouched, not corrupted


def test_append_feed_rejects_non_http_url(tmp_path):
    path = write_config(tmp_path, BASE + """
[[feeds]]
name = "F"
url = "https://f"
""")

    with pytest.raises(ValueError):
        config_mod.append_feed(path, "Bad", "javascript:alert(1)")


def test_missing_interest_profile_rejected(tmp_path):
    path = write_config(tmp_path, """
[[feeds]]
name = "F"
url = "https://f"
""")

    with pytest.raises(ValueError, match="interest_profile"):
        config_mod.load_config(path)
