"""Unit tests for the best-effort Pillow OG/cover cards."""

import builtins

from sift import card


def test_static_card_is_1200x630_png(tmp_path):
    out = tmp_path / "og.png"
    assert card.render_static_card(out) is True
    from PIL import Image

    with Image.open(out) as im:
        assert im.format == "PNG"
        assert im.size == (1200, 630)


def test_issue_card_writes_png(tmp_path):
    out = tmp_path / "2026-26.png"
    ok = card.render_issue_card(
        out,
        week="2026-26",
        range_label="Jun 22–28, 2026",
        headline="GLM-5.2 beats Claude in cyber benchmarks, a step change for open agents",
        category_counts={"models_research": 4, "tooling": 2, "policy": 2, "infra": 1, "business": 1},
        story_count=10,
        feed_count=20,
    )
    assert ok is True
    assert out.exists()
    from PIL import Image

    with Image.open(out) as im:
        assert im.size == (1200, 630)


def test_card_best_effort_returns_false_without_pillow(tmp_path, monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError("Pillow not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    # No exception escapes; the run must continue with a False result.
    assert card.render_static_card(tmp_path / "og.png") is False
    assert card.render_issue_card(
        tmp_path / "w.png",
        week="2026-26",
        range_label="Jun 22–28, 2026",
        headline="x",
        category_counts={"tooling": 1},
        story_count=1,
        feed_count=1,
    ) is False
