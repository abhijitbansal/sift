"""Design tokens — the one source of truth for every rendered surface.

The site CSS, the self-contained weekly digest, the OG/cover cards and the
favicon all read their colors from here, so a palette change lands everywhere at
once instead of drifting per file.

The shipped palette is ``ultraviolet``; the others are kept because they are
proven (each one clears WCAG AA — see ``tests/test_theme.py``) and switching is a
one-word change in ``config.toml``'s ``[site] palette``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

# Ranked categories, in the order the digest lays out its lanes.
CATEGORY_LABELS: dict[str, str] = {
    "models_research": "Models & Research",
    "tooling": "Tooling",
    "infra": "Infra",
    "policy": "Policy",
    "business": "Business",
}

# The isometric objects are drawn with one light from the upper-left; these are
# the face-shading factors every generated solid uses.
FACE_LIGHTEN_TOP = 0.22
FACE_DARKEN_LEFT = 0.18
FACE_DARKEN_RIGHT = 0.42

# Web fonts for the site. The digest deliberately uses system stacks only, so it
# stays offline- and email-safe.
FONT_DISPLAY = '"Bricolage Grotesque", "Helvetica Neue", Helvetica, Arial, sans-serif'
FONT_BODY = '"Schibsted Grotesk", "Helvetica Neue", Helvetica, Arial, sans-serif'
FONT_MONO = '"DM Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace'
GOOGLE_FONTS_HREF = (
    "https://fonts.googleapis.com/css2"
    "?family=Bricolage+Grotesque:opsz,wght@12..96,300..800"
    "&family=Schibsted+Grotesk:wght@400;500;600"
    "&family=DM+Mono:wght@400;500&display=swap"
)

# System fallbacks, used by the self-contained digest (no web fonts there).
FONT_DISPLAY_FALLBACK = 'Georgia, "Times New Roman", serif'
FONT_BODY_FALLBACK = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
FONT_MONO_FALLBACK = 'ui-monospace, "SF Mono", Menlo, Consolas, monospace'


@dataclass(frozen=True)
class Palette:
    """One complete set of surface colors.

    ``glass`` is the translucent overlay tint used for raised surfaces and the
    isometric mesh planes; it is stored as a hex color and converted to an
    ``rgba()`` base on demand so every token stays one comparable type.
    """

    name: str
    bg: str
    bg_2: str
    bg_3: str
    text: str
    text_2: str
    muted: str
    glass: str
    accent: str
    accent_hi: str
    accent_deep: str
    accent_ink: str
    slab: str
    slab_paid: str
    live: str
    badge_tint: str = "#fff4e6"
    categories: dict[str, str] = field(default_factory=dict)
    noise: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, str]:
        """Flat token name -> hex, for CSS emission and invariant checks."""
        return {
            "bg": self.bg,
            "bg-2": self.bg_2,
            "bg-3": self.bg_3,
            "text": self.text,
            "text-2": self.text_2,
            "muted": self.muted,
            "glass": self.glass,
            "accent": self.accent,
            "accent-hi": self.accent_hi,
            "accent-deep": self.accent_deep,
            "accent-ink": self.accent_ink,
            "slab": self.slab,
            "slab-paid": self.slab_paid,
            "live": self.live,
            "badge-tint": self.badge_tint,
        }

    def category_color(self, category: str) -> str:
        """Color for a ranked category, falling back to the accent so an
        unexpected category from the model still renders as something visible."""
        return self.categories.get(category, self.accent)

    @property
    def glass_rgb(self) -> str:
        """``r,g,b`` of the glass tint, for building ``rgba(...)`` values."""
        value = self.glass.lstrip("#")
        return ",".join(str(int(value[i : i + 2], 16)) for i in (0, 2, 4))

    def glass_rgba(self, alpha: float) -> str:
        return f"rgba({self.glass_rgb},{alpha:g})"

    @property
    def accent_rgb(self) -> str:
        value = self.accent.lstrip("#")
        return ",".join(str(int(value[i : i + 2], 16)) for i in (0, 2, 4))

    def accent_rgba(self, alpha: float) -> str:
        return f"rgba({self.accent_rgb},{alpha:g})"


def _palette(
    name: str,
    *,
    bg: str,
    bg_2: str,
    bg_3: str,
    text: str,
    text_2: str,
    muted: str,
    glass: str,
    accent: str,
    accent_hi: str,
    accent_deep: str,
    accent_ink: str,
    slab: str,
    slab_paid: str,
    live: str,
    categories: dict[str, str],
    noise: tuple[str, ...],
) -> Palette:
    return Palette(
        name=name, bg=bg, bg_2=bg_2, bg_3=bg_3, text=text, text_2=text_2,
        muted=muted, glass=glass, accent=accent, accent_hi=accent_hi,
        accent_deep=accent_deep, accent_ink=accent_ink, slab=slab,
        slab_paid=slab_paid, live=live, categories=categories, noise=noise,
    )


PALETTES: dict[str, Palette] = {
    # Deep aubergine ground, hot-coral light. The shipped look.
    "ultraviolet": _palette(
        "ultraviolet",
        bg="#130a1e", bg_2="#1a0f29", bg_3="#221537",
        text="#f5ecff", text_2="#d3c4e8", muted="#9b8ab8", glass="#eccdff",
        accent="#ff4f8b", accent_hi="#ff7fab", accent_deep="#d12d67",
        accent_ink="#1f0410", slab="#281a3c", slab_paid="#3a1e3a", live="#4ade80",
        categories={
            "models_research": "#8b84f0", "tooling": "#2dd4bf", "infra": "#fbbf24",
            "policy": "#c084fc", "business": "#4ade80",
        },
        noise=("#2b1d40", "#36264f", "#43315f", "#241834", "#4f3c6d"),
    ),
    # Warm obsidian + terracotta: the original v2 look, kept as a fallback.
    "ember": _palette(
        "ember",
        bg="#120e0b", bg_2="#17110d", bg_3="#1d1611",
        text="#f1e9dc", text_2="#cbbfa9", muted="#9a8c75", glass="#ffe8d2",
        accent="#e8804f", accent_hi="#f2a279", accent_deep="#b4542e",
        accent_ink="#1a0f08", slab="#2a221c", slab_paid="#3a2a20", live="#4ade80",
        categories={
            "models_research": "#8b84f0", "tooling": "#2dd4bf", "infra": "#f59e0b",
            "policy": "#fb7185", "business": "#4ade80",
        },
        noise=("#3b322a", "#4a3f36", "#57493e", "#2f2721", "#645548"),
    ),
    # Ink navy ground, keeping the brand orange as the light.
    "nightsignal": _palette(
        "nightsignal",
        bg="#0b0d1f", bg_2="#10132a", bg_3="#161a36",
        text="#eef0ff", text_2="#c3c8e6", muted="#8a90b8", glass="#c8d6ff",
        accent="#ff7a45", accent_hi="#ff9b70", accent_deep="#d9552a",
        accent_ink="#1a0b05", slab="#1c2040", slab_paid="#2c2444", live="#4ade80",
        categories={
            "models_research": "#8b84f0", "tooling": "#2dd4bf", "infra": "#fbbf24",
            "policy": "#f472b6", "business": "#4ade80",
        },
        noise=("#262b4a", "#2f3558", "#3a4068", "#1f2340", "#454b78"),
    ),
    # Deep petrol ground, acid-lime light: the most technical of the set.
    "reactor": _palette(
        "reactor",
        bg="#06131a", bg_2="#0a1a22", bg_3="#10232c",
        text="#e6fbf6", text_2="#b5d9d1", muted="#7ba39a", glass="#aaf0e1",
        accent="#c6ff3d", accent_hi="#dcff7a", accent_deep="#8fc41a",
        accent_ink="#0b1a04", slab="#123039", slab_paid="#1c3a2c", live="#22d3ee",
        categories={
            "models_research": "#a78bfa", "tooling": "#22d3ee", "infra": "#fbbf24",
            "policy": "#fb7185", "business": "#7dd3fc",
        },
        noise=("#16303a", "#1f3d48", "#284a56", "#122631", "#33586a"),
    ),
    # Neutral near-black ground, gold light: the quietest of the set.
    "signalgold": _palette(
        "signalgold",
        bg="#0a0a0c", bg_2="#101012", bg_3="#161618",
        text="#f3f1ea", text_2="#c9c6bb", muted="#8f8c82", glass="#ffffff",
        accent="#f2c23a", accent_hi="#ffd86b", accent_deep="#c99a17",
        accent_ink="#1a1200", slab="#1e1e22", slab_paid="#2c2716", live="#4ade80",
        categories={
            "models_research": "#8b84f0", "tooling": "#2dd4bf", "infra": "#fb923c",
            "policy": "#fb7185", "business": "#4ade80",
        },
        noise=("#26262a", "#303035", "#3b3b41", "#1e1e22", "#47474e"),
    ),
}

DEFAULT_PALETTE = "ultraviolet"


def palette(name: str | None = None) -> Palette:
    """Look up a palette by name. Unknown names raise, so a typo in config fails
    loudly at build time rather than silently rendering the default."""
    return PALETTES[name or DEFAULT_PALETTE]


def category_label(category: str) -> str:
    """Human label for a ranked category; an unknown one is title-cased."""
    return CATEGORY_LABELS.get(category, category.replace("_", " ").title())


def css_variables(pal: Palette, *, selector: str = ":root") -> str:
    """The palette as a CSS custom-property block, including the category ramp."""
    lines = [f"{selector} {{", "  color-scheme: dark;"]
    for token, value in pal.as_dict().items():
        lines.append(f"  --{token}: {value};")
    lines.append(f"  --glass-rgb: {pal.glass_rgb};")
    lines.append(f"  --accent-rgb: {pal.accent_rgb};")
    for category, color in pal.categories.items():
        lines.append(f"  --cat-{category.replace('_', '-')}: {color};")
    lines.append("}")
    return "\n".join(lines)


def category_selectors(pal: Palette) -> str:
    """``[data-cat=...] {--c: ...}`` rules, so one element can carry its category
    color through a single custom property."""
    return "\n".join(
        f"[data-cat={category}] {{ --c: var(--cat-{category.replace('_', '-')}); }}"
        for category in pal.categories
    )


# ---------------------------------------------------------------- color maths


def _channels(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _hex(r: float, g: float, b: float) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        *(max(0, min(255, round(channel))) for channel in (r, g, b))
    )


def mix(color: str, target: str, amount: float) -> str:
    """Blend ``color`` towards ``target`` by ``amount`` in [0, 1]."""
    r1, g1, b1 = _channels(color)
    r2, g2, b2 = _channels(target)
    return _hex(
        r1 + (r2 - r1) * amount, g1 + (g2 - g1) * amount, b1 + (b2 - b1) * amount
    )


def _luminance(hex_color: str) -> float:
    out = []
    for channel in _channels(hex_color):
        c = channel / 255
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = out
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


_WHITE, _BLACK = "#ffffff", "#000000"


def _darken_until(color: str, ground: str, target: float) -> str:
    """Walk a color towards black until it clears ``target`` against ``ground``.

    Used to carry a dark-theme hue onto a light ground: the hue is preserved,
    only the lightness moves, so the brand still reads as itself.
    """
    for step in range(21):
        candidate = mix(color, _BLACK, step * 0.05)
        if contrast_ratio(candidate, ground) >= target:
            return candidate
    return _BLACK


# ------------------------------------------------------------- light variants


# A Palette holds its category map, so it is not hashable and cannot use
# functools.lru_cache; memoise on the name, which is unique per palette.
_LIGHT_CACHE: dict[str, Palette] = {}


def light_palette(pal: Palette) -> Palette:
    """Derive the light counterpart of a dark palette.

    Deriving rather than hand-writing keeps the two in step: a change to the
    dark palette carries over automatically, and the contrast tests hold for
    every palette instead of only the one that shipped.
    """
    cached = _LIGHT_CACHE.get(pal.name)
    if cached is not None:
        return cached
    bg = mix(pal.bg, _WHITE, 0.955)
    bg_2 = mix(pal.bg, _WHITE, 0.925)
    bg_3 = mix(pal.bg, _WHITE, 0.885)
    text = mix(pal.bg, _BLACK, 0.35)
    light = replace(
        pal,
        name=f"{pal.name}-light",
        bg=bg,
        bg_2=bg_2,
        bg_3=bg_3,
        text=text,
        text_2=_darken_until(mix(pal.text_2, _BLACK, 0.55), bg, 4.5),
        muted=_darken_until(mix(pal.muted, _BLACK, 0.45), bg, 4.5),
        # On a light ground the translucent overlay has to be a dark tint, or
        # every raised surface and every glass plane disappears.
        glass=mix(pal.bg, _BLACK, 0.15),
        accent=_darken_until(pal.accent, bg, 4.5),
        accent_hi=_darken_until(pal.accent, bg, 6.5),
        accent_deep=_darken_until(pal.accent, bg, 8.0),
        accent_ink=_WHITE,
        badge_tint=mix(pal.bg, _BLACK, 0.30),
        slab=mix(pal.bg, _WHITE, 0.80),
        slab_paid=mix(pal.accent, _WHITE, 0.82),
        live=_darken_until(pal.live, bg, 4.5),
        # These are not only swatches on light: the digest score badge puts
        # white ink on them, so they need the full 4.5:1, not a swatch's 3.0:1.
        categories={
            category: _darken_until(color, bg, 4.5)
            for category, color in pal.categories.items()
        },
        # Noise is the stuff being filtered out: on a light ground it reads as
        # mid-grey blocks rather than the near-black ones used on dark.
        noise=tuple(mix(shade, _WHITE, 0.62) for shade in pal.noise),
    )
    _LIGHT_CACHE[pal.name] = light
    return light


# --------------------------------------------------- isometric solid materials


def iso_materials(pal: Palette) -> dict[str, str]:
    """Every named solid the SVG generator paints, as ``name -> hex``.

    Naming them (rather than passing raw hexes around) is what lets one
    generated SVG serve both themes: each face is emitted as a CSS variable
    reference, and the theme swaps the variables.
    """
    materials = {
        "accent": pal.accent,
        "accent-hi": pal.accent_hi,
        "accent-deep": pal.accent_deep,
        "ink": pal.accent_ink,
        "text": pal.text,
        "slab": pal.slab,
        "slab-paid": pal.slab_paid,
    }
    for index, shade in enumerate(pal.noise):
        materials[f"noise-{index}"] = shade
    for category, color in pal.categories.items():
        materials[f"cat-{category.replace('_', '-')}"] = color
    return materials


def iso_face_variables(pal: Palette, *, indent: str = "  ") -> str:
    """The three lit faces of every material, as CSS custom properties."""
    from sift.iso import shade as _shade  # local import avoids a cycle

    lines = [f"{indent}--iso-glass-rgb: {pal.glass_rgb};"]
    for material, color in iso_materials(pal).items():
        top, left, right = _shade(color)
        lines.append(f"{indent}--iso-{material}-top: {top};")
        lines.append(f"{indent}--iso-{material}-left: {left};")
        lines.append(f"{indent}--iso-{material}-right: {right};")
    return "\n".join(lines)


def theme_blocks(pal: Palette, *, extra: str = "") -> str:
    """The complete color layer for a page: the dark palette on ``:root`` and its
    derived light counterpart behind ``prefers-color-scheme: light``.

    Both blocks carry the isometric face variables, which is what lets one
    generated SVG restyle itself instead of being emitted twice per page.
    ``extra`` holds declarations that belong on ``:root`` but do not change with
    the theme, such as font stacks.
    """
    light = light_palette(pal)
    dark_body = "\n".join(
        [_palette_declarations(pal), iso_face_variables(pal), extra.rstrip()]
    ).rstrip()
    light_body = "\n".join(
        [_palette_declarations(light, scheme="light"), iso_face_variables(light, indent="    ")]
    )
    return (
        f":root {{\n{dark_body}\n}}\n"
        "/* The light palette is derived from the dark one, so the two never\n"
        "   drift apart; see sift.theme.light_palette. */\n"
        "@media (prefers-color-scheme: light) {\n"
        f"  :root {{\n{light_body}\n  }}\n"
        "}"
    )


def _palette_declarations(pal: Palette, *, scheme: str = "dark", indent: str = "  ") -> str:
    lines = [f"{indent}color-scheme: {scheme};"]
    for token, value in pal.as_dict().items():
        lines.append(f"{indent}--{token}: {value};")
    lines.append(f"{indent}--glass-rgb: {pal.glass_rgb};")
    lines.append(f"{indent}--accent-rgb: {pal.accent_rgb};")
    for category, color in pal.categories.items():
        lines.append(f"{indent}--cat-{category.replace('_', '-')}: {color};")
    return "\n".join(lines)
