"""Design tokens — the one source of truth for every rendered surface.

The site CSS, the self-contained weekly digest, the OG/cover cards and the
favicon all read their colors from here, so a palette change lands everywhere at
once instead of drifting per file.

The shipped palette is ``ultraviolet``; the others are kept because they are
proven (each one clears WCAG AA — see ``tests/test_theme.py``) and switching is a
one-word change in ``config.toml``'s ``[site] palette``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
