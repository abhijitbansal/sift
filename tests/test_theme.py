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
