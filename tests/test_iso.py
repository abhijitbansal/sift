"""Unit tests for the isometric SVG generator.

Every graphic on the site is generated here rather than committed as a binary,
so these tests guard the properties that make that safe: valid standalone SVG,
deterministic output, palette-driven color, and geometry that stays inside its
own viewBox (a clipped hero is the one failure mode a screenshot would catch
late).
"""

import re
import xml.etree.ElementTree as ET

import pytest

from sift import iso, theme

SVG_BUILDERS = {
    "hero_sieve": lambda pal: iso.hero_sieve(pal),
    "stage_fetch": lambda pal: iso.stage_block("fetch", pal),
    "stage_filter": lambda pal: iso.stage_block("filter", pal),
    "stage_dedup": lambda pal: iso.stage_block("dedup", pal),
    "stage_rank": lambda pal: iso.stage_block("rank", pal),
    "stage_weight": lambda pal: iso.stage_block("weight", pal),
    "stage_deliver": lambda pal: iso.stage_block("deliver", pal),
    "stage_render": lambda pal: iso.stage_block("render", pal),
    "glyph_models": lambda pal: iso.category_glyph("models_research", pal),
    "glyph_tooling": lambda pal: iso.category_glyph("tooling", pal),
    "glyph_infra": lambda pal: iso.category_glyph("infra", pal),
    "glyph_policy": lambda pal: iso.category_glyph("policy", pal),
    "glyph_business": lambda pal: iso.category_glyph("business", pal),
    "mark": lambda pal: iso.mark(pal),
}


@pytest.fixture
def pal():
    return theme.palette()


@pytest.mark.parametrize("name", sorted(SVG_BUILDERS))
def test_every_graphic_is_parseable_svg(name, pal):
    svg = SVG_BUILDERS[name](pal)

    root = ET.fromstring(svg)

    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.get("viewBox")


@pytest.mark.parametrize("name", sorted(SVG_BUILDERS))
def test_every_graphic_is_deterministic(name, pal):
    first = SVG_BUILDERS[name](pal)

    second = SVG_BUILDERS[name](pal)

    assert first == second


@pytest.mark.parametrize("name", sorted(SVG_BUILDERS))
def test_every_graphic_carries_an_accessible_label(name, pal):
    svg = SVG_BUILDERS[name](pal)

    root = ET.fromstring(svg)

    assert root.get("role") == "img"
    assert root.get("aria-label")


@pytest.mark.parametrize("name", sorted(SVG_BUILDERS))
def test_geometry_stays_inside_the_viewbox(name, pal):
    svg = SVG_BUILDERS[name](pal)
    root = ET.fromstring(svg)
    _, _, width, height = (float(v) for v in root.get("viewBox").split())

    xs, ys = _drawn_extents(root)

    # A small bleed is fine (glow ellipses are meant to fade off-frame); real
    # clipping of the solid geometry is not.
    assert min(xs) >= -width * 0.02, f"{name} clips on the left"
    assert max(xs) <= width * 1.02, f"{name} clips on the right"
    assert min(ys) >= -height * 0.02, f"{name} clips at the top"
    assert max(ys) <= height * 1.02, f"{name} clips at the bottom"


def _drawn_extents(root):
    """Bounds of the solid geometry: polygon points, line endpoints and
    circle/ellipse extents. Two things are excluded on purpose — the <defs>
    subtree, whose gradient stops carry their own x1/x2 coordinate space, and
    anything marked class="glow", which fades to zero opacity and is meant to
    bleed past the frame."""
    xs, ys = [], []

    def local(node):
        return node.tag.rsplit("}", 1)[-1]

    def walk(node):
        for child in node:
            if local(child) == "defs":
                continue
            tag = local(child)
            if child.get("class") == "glow":
                walk(child)
                continue
            points = child.get("points")
            if points:
                for pair in points.split():
                    x, y = pair.split(",")
                    xs.append(float(x))
                    ys.append(float(y))
            elif tag == "line":
                xs.extend([float(child.get("x1")), float(child.get("x2"))])
                ys.extend([float(child.get("y1")), float(child.get("y2"))])
            elif tag == "circle":
                cx, cy, r = (float(child.get(a)) for a in ("cx", "cy", "r"))
                xs.extend([cx - r, cx + r])
                ys.extend([cy - r, cy + r])
            elif tag == "ellipse":
                cx, cy = float(child.get("cx")), float(child.get("cy"))
                rx, ry = float(child.get("rx")), float(child.get("ry"))
                xs.extend([cx - rx, cx + rx])
                ys.extend([cy - ry, cy + ry])
            walk(child)

    walk(root)
    assert xs and ys, "graphic drew nothing"
    return xs, ys


def test_hero_sieve_uses_the_palette_accent_and_not_another_palettes(pal):
    other = theme.palette("reactor")

    svg = iso.hero_sieve(pal)

    assert pal.accent in svg
    assert other.accent not in svg


def test_hero_sieve_labels_every_pipeline_stage(pal):
    svg = iso.hero_sieve(pal)

    for stage in ("FETCH", "FILTER", "DEDUP", "RANK"):
        assert f">{stage}<" in svg


def test_hero_sieve_marks_the_one_paid_call(pal):
    svg = iso.hero_sieve(pal)

    assert "ONE CLAUDE CALL" in svg


def test_category_glyphs_use_their_own_category_color(pal):
    for category, color in pal.categories.items():
        svg = iso.category_glyph(category, pal)

        assert color in svg or _lightened(color) in svg


def _lightened(color: str) -> str:
    return iso.mix(color, "#fff4e6", theme.FACE_LIGHTEN_TOP)


def test_category_glyphs_differ_per_category(pal):
    shapes = {iso.category_glyph(c, pal) for c in pal.categories}

    assert len(shapes) == len(pal.categories)


def test_unknown_stage_kind_fails_loudly(pal):
    with pytest.raises(ValueError, match="unknown stage"):
        iso.stage_block("teleport", pal)


def test_unknown_category_glyph_falls_back_to_a_cube(pal):
    svg = iso.category_glyph("nonsense", pal)

    assert ET.fromstring(svg).get("role") == "img"
    assert pal.accent in svg or _lightened(pal.accent) in svg


def test_mix_blends_towards_the_target():
    assert iso.mix("#000000", "#ffffff", 0.0) == "#000000"
    assert iso.mix("#000000", "#ffffff", 1.0) == "#ffffff"
    assert iso.mix("#000000", "#ffffff", 0.5) == "#808080"


def test_svgs_have_no_external_references(pal):
    """The digest is self-contained and email-safe; nothing may phone home."""
    for build in SVG_BUILDERS.values():
        svg = build(pal)

        assert "http://" not in svg.replace("http://www.w3.org/2000/svg", "")
        assert "https://" not in svg
        assert not re.search(r"url\(\s*['\"]?(?!#)", svg)
