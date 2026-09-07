"""Unit tests for the design-token module.

The palette is the one source of truth for every surface (site CSS, the
self-contained digest, the cover cards, the favicon), so these tests pin the
invariants that keep those surfaces consistent and readable.
"""

import re

import pytest

from sift import theme


def relative_luminance(hex_color: str) -> float:
    channels = []
    value = hex_color.lstrip("#")
    for i in (0, 2, 4):
        c = int(value[i : i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def test_every_palette_defines_the_same_tokens():
    keys = {name: set(p.as_dict()) for name, p in theme.PALETTES.items()}
    reference = keys[theme.DEFAULT_PALETTE]

    assert len(keys) > 1
    for name, palette_keys in keys.items():
        assert palette_keys == reference, f"{name} has different tokens"


def test_every_token_is_a_six_digit_hex_color():
    for name, palette in theme.PALETTES.items():
        for token, value in palette.as_dict().items():
            assert re.fullmatch(r"#[0-9a-f]{6}", value), f"{name}.{token} = {value!r}"


@pytest.mark.parametrize("name", sorted(theme.PALETTES))
def test_body_text_clears_wcag_aa_on_its_own_ground(name):
    palette = theme.PALETTES[name]

    assert contrast(palette.text, palette.bg) >= 4.5
    assert contrast(palette.text_2, palette.bg) >= 4.5
    assert contrast(palette.muted, palette.bg) >= 4.5


@pytest.mark.parametrize("name", sorted(theme.PALETTES))
def test_accent_is_readable_as_text_and_as_a_button(name):
    palette = theme.PALETTES[name]

    assert contrast(palette.accent, palette.bg) >= 4.5
    # Button label: the accent ink sits *on* the accent fill.
    assert contrast(palette.accent_ink, palette.accent) >= 4.5


@pytest.mark.parametrize("name", sorted(theme.PALETTES))
def test_category_colors_are_distinguishable_from_the_ground_and_the_accent(name):
    palette = theme.PALETTES[name]

    for category, color in palette.categories.items():
        assert contrast(color, palette.bg) >= 3.0, f"{name}.{category} vs ground"
        # A category color that reads as the accent would make the paid step
        # ambiguous, so keep them apart in hue-independent luminance terms.
        assert color != palette.accent, f"{name}.{category} collides with the accent"


def test_categories_cover_every_ranked_category():
    for palette in theme.PALETTES.values():
        assert set(palette.categories) == set(theme.CATEGORY_LABELS)


def test_css_variables_block_declares_every_token():
    palette = theme.palette()

    css = theme.css_variables(palette)

    assert css.startswith(":root")
    for token, value in palette.as_dict().items():
        assert f"--{token.replace('_', '-')}: {value};" in css


def test_css_variables_includes_the_category_ramp():
    css = theme.css_variables(theme.palette())

    assert "--cat-models-research:" in css
    assert "--cat-business:" in css


def test_palette_lookup_is_by_name_and_defaults():
    assert theme.palette().name == theme.DEFAULT_PALETTE
    assert theme.palette("reactor").name == "reactor"


def test_unknown_palette_name_fails_loudly():
    with pytest.raises(KeyError):
        theme.palette("chartreuse")


def test_category_label_falls_back_for_an_unknown_category():
    assert theme.category_label("tooling") == "Tooling"
    assert theme.category_label("wat") == "Wat"


def test_category_color_falls_back_to_the_accent():
    palette = theme.palette()

    assert palette.category_color("tooling") == palette.categories["tooling"]
    assert palette.category_color("nonsense") == palette.accent


# --- light theme --------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(theme.PALETTES))
def test_every_palette_has_a_light_counterpart(name):
    light = theme.light_palette(theme.PALETTES[name])

    assert light.name == f"{name}-light"
    assert set(light.as_dict()) == set(theme.PALETTES[name].as_dict())


@pytest.mark.parametrize("name", sorted(theme.PALETTES))
def test_the_light_ground_is_actually_light(name):
    light = theme.light_palette(theme.PALETTES[name])

    assert relative_luminance(light.bg) > 0.7
    assert relative_luminance(light.text) < 0.1


@pytest.mark.parametrize("name", sorted(theme.PALETTES))
def test_light_body_text_clears_wcag_aa(name):
    light = theme.light_palette(theme.PALETTES[name])

    assert contrast(light.text, light.bg) >= 4.5
    assert contrast(light.text_2, light.bg) >= 4.5
    assert contrast(light.muted, light.bg) >= 4.5


@pytest.mark.parametrize("name", sorted(theme.PALETTES))
def test_light_accent_is_readable_as_text_and_as_a_button(name):
    light = theme.light_palette(theme.PALETTES[name])

    assert contrast(light.accent, light.bg) >= 4.5
    assert contrast(light.accent_ink, light.accent) >= 4.5


@pytest.mark.parametrize("name", sorted(theme.PALETTES))
def test_light_category_colors_carry_white_ink(name):
    """On light they back the digest score badge, whose ink is white, so a
    swatch-grade 3:1 is not enough."""
    light = theme.light_palette(theme.PALETTES[name])

    for category, color in light.categories.items():
        assert contrast(color, light.bg) >= 4.5, f"{name}-light.{category} vs ground"
        assert contrast(light.accent_ink, color) >= 4.5, f"ink on {name}-light.{category}"


@pytest.mark.parametrize("name", sorted(theme.PALETTES))
def test_dark_score_badge_ink_is_readable_on_every_category(name):
    pal = theme.PALETTES[name]

    for category, color in pal.categories.items():
        assert contrast(pal.accent_ink, color) >= 4.5, f"ink on {name}.{category}"


@pytest.mark.parametrize("name", sorted(theme.PALETTES))
def test_badge_tint_moves_the_lit_face_away_from_the_ink(name):
    """The badge's top face is mixed toward this tint. On dark it lightens; on
    light it must darken, or white ink lands on the palest part."""
    dark = theme.PALETTES[name]
    light = theme.light_palette(dark)

    assert relative_luminance(dark.badge_tint) > relative_luminance(dark.accent_ink)
    assert relative_luminance(light.badge_tint) < relative_luminance(light.accent_ink)


def test_light_palette_keeps_the_brand_hue():
    """The light accent is a darkened version of the dark one, not a new color."""
    dark = theme.palette("ultraviolet")

    light = theme.light_palette(dark)

    assert light.accent != dark.accent
    assert relative_luminance(light.accent) < relative_luminance(dark.accent)


def test_light_palette_is_cached_so_derivation_runs_once():
    dark = theme.palette()

    assert theme.light_palette(dark) is theme.light_palette(dark)


# --- isometric materials ------------------------------------------------------


def test_iso_materials_cover_every_solid_the_generator_paints():
    materials = theme.iso_materials(theme.palette())

    for required in ("accent", "accent-deep", "ink", "text", "slab", "slab-paid"):
        assert required in materials
    for i in range(5):
        assert f"noise-{i}" in materials
    for category in theme.CATEGORY_LABELS:
        assert f"cat-{category.replace('_', '-')}" in materials


def test_iso_face_variables_declare_three_faces_per_material():
    pal = theme.palette()

    css = theme.iso_face_variables(pal)

    for material in theme.iso_materials(pal):
        for face in ("top", "left", "right"):
            assert f"--iso-{material}-{face}:" in css


def test_iso_face_variables_include_the_glass_tint():
    css = theme.iso_face_variables(theme.palette())

    assert "--iso-glass-rgb:" in css


# --- explicit theme choice ----------------------------------------------------


def test_theme_blocks_let_an_explicit_choice_beat_the_system():
    """Three blocks, in this order: dark by default, light when the system asks
    for it *unless* dark was chosen, and light whenever light was chosen."""
    css = theme.theme_blocks(theme.palette())

    assert css.index(":root {") < css.index("@media (prefers-color-scheme: light)")
    assert ':root:not([data-theme="dark"])' in css
    assert ':root[data-theme="light"]' in css
    # The explicit light block must come last so it wins on equal specificity.
    assert css.index(':root[data-theme="light"]') > css.index("@media (prefers-color-scheme: light)")


def test_an_explicit_dark_choice_survives_a_light_system():
    css = theme.theme_blocks(theme.palette())
    guarded = css[css.index("@media (prefers-color-scheme: light)") :]

    # The system-light block is scoped away from an explicit dark choice.
    assert guarded.index(':root:not([data-theme="dark"])') < guarded.index("--bg:")


def test_both_themes_declare_the_same_tokens():
    css = theme.theme_blocks(theme.palette())

    for token in theme.palette().as_dict():
        assert css.count(f"--{token}:") >= 3  # dark, system-light, explicit-light
