"""Isometric SVG graphics, generated rather than committed.

Every 3D object on the site is built here from one projection and one light, so
the whole graphic language stays consistent and follows the palette
(:mod:`sift.theme`) automatically. Output is plain inline SVG: no WebGL, no
runtime library, no external asset — which is what lets the same objects ride
along inside the self-contained weekly digest.

Projection: true isometric at 30°. World ``x`` runs down-right, ``y`` down-left,
``z`` up. Light comes from the upper-left, so a solid's top face is lightened and
its two visible side faces are darkened by fixed factors.
"""

from __future__ import annotations

import math
import random

from sift.theme import (
    FACE_DARKEN_LEFT,
    FACE_DARKEN_RIGHT,
    FACE_LIGHTEN_TOP,
    Palette,
)

COS30, SIN30 = 0.8660254, 0.5

# Which primitive stands for which ranked category. One shape per category, so
# the glyphs stay distinguishable without relying on color alone.
CATEGORY_SHAPES: dict[str, str] = {
    "models_research": "cube",
    "tooling": "cylinder",
    "infra": "pyramid",
    "policy": "hexprism",
    "business": "sphere",
}

STAGE_KINDS = ("fetch", "filter", "dedup", "rank", "weight", "deliver", "render")

_HIGHLIGHT = "#fff4e6"
_SHADOW = "#000000"


# --------------------------------------------------------------------- color


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        *(max(0, min(255, round(channel))) for channel in (r, g, b))
    )


def mix(color: str, target: str, amount: float) -> str:
    """Blend ``color`` towards ``target`` by ``amount`` in [0, 1]."""
    r1, g1, b1 = _hex_to_rgb(color)
    r2, g2, b2 = _hex_to_rgb(target)
    return _rgb_to_hex(
        r1 + (r2 - r1) * amount,
        g1 + (g2 - g1) * amount,
        b1 + (b2 - b1) * amount,
    )


def shade(base: str) -> tuple[str, str, str]:
    """``(top, left, right)`` face colors for one solid, lit from upper-left."""
    return (
        mix(base, _HIGHLIGHT, FACE_LIGHTEN_TOP),
        mix(base, _SHADOW, FACE_DARKEN_LEFT),
        mix(base, _SHADOW, FACE_DARKEN_RIGHT),
    )


def faces(base: str, material: str | None) -> tuple[str, str, str]:
    """Paint values for a solid's three faces.

    With a ``material`` name the faces are emitted as CSS variable references
    carrying the computed color as a fallback, so the light theme can restyle
    the same SVG by swapping variables. Without one (a per-item color the theme
    does not name) the computed values are used directly.
    """
    computed = shade(base)
    if material is None:
        return computed
    return tuple(
        f"var(--iso-{material}-{face}, {value})"
        for face, value in zip(("top", "left", "right"), computed)
    )


# ------------------------------------------------------------------ geometry


def project(x: float, y: float, z: float, ox: float, oy: float) -> tuple[float, float]:
    """World (x, y, z) to screen coordinates around origin (ox, oy)."""
    return ox + (x - y) * COS30, oy + (x + y) * SIN30 - z


def _points(pairs: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pairs)


def _box(
    x: float, y: float, z: float, sx: float, sy: float, h: float,
    base: str, ox: float, oy: float, *, opacity: float = 1.0, stroke: str | None = None,
    material: str | None = None,
) -> str:
    """One axis-aligned box: three visible faces, painted back to front."""
    top, left, right = faces(base, material)

    def p(a: float, b: float, c: float) -> tuple[float, float]:
        return project(a, b, c, ox, oy)

    top_face = [p(x, y, z + h), p(x + sx, y, z + h), p(x + sx, y + sy, z + h), p(x, y + sy, z + h)]
    left_face = [p(x, y + sy, z), p(x + sx, y + sy, z), p(x + sx, y + sy, z + h), p(x, y + sy, z + h)]
    right_face = [p(x + sx, y, z), p(x + sx, y + sy, z), p(x + sx, y + sy, z + h), p(x + sx, y, z + h)]
    outline = f' stroke="{stroke}" stroke-width="0.6" stroke-linejoin="round"' if stroke else ""
    return (
        f'<g opacity="{opacity:g}"{outline}>'
        f'<polygon points="{_points(left_face)}" fill="{left}"/>'
        f'<polygon points="{_points(right_face)}" fill="{right}"/>'
        f'<polygon points="{_points(top_face)}" fill="{top}"/></g>'
    )


def cube(x, y, z, size, base, ox, oy, *, opacity=1.0, stroke=None, material=None) -> str:
    return _box(
        x, y, z, size, size, size, base, ox, oy,
        opacity=opacity, stroke=stroke, material=material,
    )


def slab(x, y, z, sx, sy, h, base, ox, oy, *, opacity=1.0, material=None) -> str:
    return _box(x, y, z, sx, sy, h, base, ox, oy, opacity=opacity, material=material)


def _V(material: str, fallback: str) -> str:
    """A flat, unlit themeable color (labels, strokes, gradient stops)."""
    return f"var(--iso-{material}-top, {fallback})"


def _glass(pal: Palette, alpha: float) -> str:
    """The translucent overlay tint, themeable at render time."""
    return f"rgba(var(--iso-glass-rgb, {pal.glass_rgb}),{alpha:g})"


def mesh_plane(
    z: float, extent: float, pal: Palette, ox: float, oy: float, *,
    edge: str | None = None, thickness: float = 7, cells: int = 5,
    fill_alpha: float = 0.07, line_alpha: float = 0.28,
) -> str:
    """A translucent glass sieve plane: a tinted top, a thin front edge, and a
    grid mesh — the surface stories fall through."""

    def p(a: float, b: float, c: float) -> tuple[float, float]:
        return project(a, b, c, ox, oy)

    x0 = y0 = -extent
    x1 = y1 = extent
    top = [p(x0, y0, z), p(x1, y0, z), p(x1, y1, z), p(x0, y1, z)]
    left = [p(x0, y1, z - thickness), p(x1, y1, z - thickness), p(x1, y1, z), p(x0, y1, z)]
    right = [p(x1, y0, z - thickness), p(x1, y1, z - thickness), p(x1, y1, z), p(x1, y0, z)]

    parts = [
        f'<polygon points="{_points(left)}" fill="{_glass(pal, 0.10)}"/>',
        f'<polygon points="{_points(right)}" fill="{_glass(pal, 0.05)}"/>',
        f'<polygon points="{_points(top)}" fill="{_glass(pal, fill_alpha)}"/>',
    ]
    step = (2 * extent) / cells
    lines = []
    for i in range(1, cells):
        a, b = p(x0 + i * step, y0, z), p(x0 + i * step, y1, z)
        c, d = p(x0, y0 + i * step, z), p(x1, y0 + i * step, z)
        lines.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"/>')
        lines.append(f'<line x1="{c[0]:.1f}" y1="{c[1]:.1f}" x2="{d[0]:.1f}" y2="{d[1]:.1f}"/>')
    parts.append(
        f'<g stroke="{_glass(pal, line_alpha)}" stroke-width="0.7">{"".join(lines)}</g>'
    )
    parts.append(
        f'<polygon points="{_points(top)}" fill="none" '
        f'stroke="{edge or _glass(pal, 0.55)}" stroke-width="1.2" stroke-linejoin="round"/>'
    )
    return "".join(parts)


def _label(
    x: float, y: float, text: str, color: str, *, size: int = 14, anchor: str = "start"
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" fill="{color}" '
        f'font-family="DM Mono, ui-monospace, Menlo, monospace" font-size="{size}" '
        f'font-weight="500" letter-spacing="0.14em" text-anchor="{anchor}">{text}</text>'
    )


def _svg(width: int, height: int, label: str, body: str, defs: str = "") -> str:
    defs_block = f"<defs>{defs}</defs>" if defs else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{label}">'
        f"{defs_block}{body}</svg>"
    )


# ----------------------------------------------------------------- hero sieve

# (z height, half-extent, label, is the paid step)
_SIEVE_LAYERS = (
    (330, 190, "FETCH", False),
    (215, 150, "FILTER", False),
    (100, 112, "DEDUP", False),
    (-10, 78, "RANK", True),
)


def hero_sieve(pal: Palette, *, width: int = 860, height: int = 980, seed: int = 7) -> str:
    """The hero object: four glass mesh planes narrowing into a funnel, noise
    cubes piling above, category-colored signal cubes falling through, and one
    accent digest card emerging below."""
    rng = random.Random(seed)
    ox, oy = width / 2, 700
    accent_id = f"glow{pal.name}"

    def p(a: float, b: float, c: float) -> tuple[float, float]:
        return project(a, b, c, ox, oy)

    defs = (
        f'<radialGradient id="{accent_id}" cx="50%" cy="50%" r="50%">'
        f'<stop offset="0" stop-color="{pal.accent}" stop-opacity="0.55"/>'
        f'<stop offset="0.55" stop-color="{pal.accent}" stop-opacity="0.12"/>'
        f'<stop offset="1" stop-color="{pal.accent}" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="haze{pal.name}" cx="50%" cy="30%" r="60%">'
        f'<stop offset="0" stop-color="{_glass(pal, 0.10)}"/>'
        f'<stop offset="1" stop-color="{_glass(pal, 0)}"/></radialGradient>'
    )

    out = [
        f'<ellipse class="glow" cx="{ox:.0f}" cy="{oy - 430:.0f}" rx="360" ry="200" fill="url(#haze{pal.name})"/>'
    ]
    glow_x, glow_y = p(0, 0, -130)
    out.append(
        f'<ellipse class="glow" cx="{glow_x:.0f}" cy="{glow_y + 40:.0f}" rx="230" ry="95" fill="url(#{accent_id})"/>'
    )

    # The digest that falls out of the bottom.
    card_z = -150
    out.append(slab(-70, -46, card_z - 8, 140, 92, 8, pal.accent_deep, ox, oy, material="accent-deep"))
    card_top = [p(-70, -46, card_z), p(70, -46, card_z), p(70, 46, card_z), p(-70, 46, card_z)]
    out.append(f'<polygon points="{_points(card_top)}" fill="{_V("accent", pal.accent)}"/>')
    for i, width_fraction in enumerate((0.55, 0.85, 0.7, 0.6)):
        line_y = -30 + i * 16
        a, b = p(-56, line_y, card_z + 0.5), p(-56 + 112 * width_fraction, line_y, card_z + 0.5)
        out.append(
            f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" '
            f'stroke="{_V("ink", pal.accent_ink)}" stroke-opacity="{0.85 if i == 0 else 0.45}" '
            f'stroke-width="{4 if i == 0 else 2.5}" stroke-linecap="round"/>'
        )
    label_x, label_y = p(78, 50, card_z)
    out.append(_label(label_x + 14, label_y + 4, "DIGEST", _V("accent-hi", pal.accent_hi)))

    # (material name, hex) pairs so every cube stays themeable.
    signals = [
        (f"cat-{category.replace('_', '-')}", color)
        for category, color in pal.categories.items()
    ]
    noise_materials = [(f"noise-{i}", shade) for i, shade in enumerate(pal.noise)]

    def scatter(z_lo, z_hi, extent, count, palette_materials, size_range, signal_fraction):
        items = []
        for _ in range(count):
            size = rng.uniform(*size_range)
            material, color = (
                rng.choice(signals)
                if rng.random() < signal_fraction
                else rng.choice(palette_materials)
            )
            items.append((
                rng.uniform(-extent, extent - size),
                rng.uniform(-extent, extent - size),
                rng.uniform(z_lo, z_hi),
                size,
                color,
                material,
            ))
        items.sort(key=lambda item: (item[0] + item[1], item[2]))
        return "".join(
            cube(x, y, z, size, color, ox, oy, opacity=0.95, material=material)
            for x, y, z, size, color, material in items
        )

    noise = noise_materials
    # Painted bottom-up so nearer layers overlap the ones behind them.
    out.append(scatter(-120, -60, 55, 3, signals, (13, 17), 1.0))
    for index in (3, 2, 1, 0):
        z, extent, _, is_paid = _SIEVE_LAYERS[index]
        cells = (8, 6, 5, 4)[index]
        out.append(
            mesh_plane(
                z, extent, pal, ox, oy,
                edge=pal.accent if is_paid else None,
                cells=cells,
                fill_alpha=0.10 if is_paid else 0.07,
                line_alpha=0.38 if is_paid else 0.28,
            )
        )
        count, span, fraction = ((42, 175, 0.12), (16, 85, 0.20), (9, 80, 0.35), (5, 70, 0.60))[index]
        out.append(
            scatter(z + 14, z + span, extent - 12, count, noise, (10, 20), fraction)
        )

    for z, extent, name, is_paid in _SIEVE_LAYERS:
        lx, ly = p(-extent, extent, z)
        out.append(
            _label(lx - 16, ly + 5, name, _V("accent-hi", pal.accent_hi) if is_paid else _glass(pal, 0.62), anchor="end")
        )
    rank_z, rank_extent, _, _ = _SIEVE_LAYERS[3]
    tick_x, tick_y = p(rank_extent, -rank_extent, rank_z)
    out.append(f'<circle cx="{tick_x + 10:.1f}" cy="{tick_y - 2:.1f}" r="3.2" fill="{_V("accent", pal.accent)}"/>')
    out.append(_label(tick_x + 20, tick_y + 3, "ONE CLAUDE CALL", _V("accent-hi", pal.accent_hi), size=13))

    return _svg(
        width, height,
        "Many stories fall through four glass filter layers; one weekly digest emerges.",
        "".join(out), defs,
    )


# --------------------------------------------------------------- stage blocks


def stage_block(kind: str, pal: Palette, *, width: int = 180, height: int = 150) -> str:
    """One pipeline step as a glass slab with a distinctive object on top."""
    if kind not in STAGE_KINDS:
        raise ValueError(f"unknown stage kind: {kind!r}")

    ox, oy = width / 2, 96
    paid = kind == "rank"
    noise = list(pal.noise)

    def p(a: float, b: float, c: float) -> tuple[float, float]:
        return project(a, b, c, ox, oy)

    defs = ""
    out = []
    if paid:
        defs = (
            f'<radialGradient id="paid{pal.name}" cx="50%" cy="50%" r="50%">'
            f'<stop offset="0" stop-color="{pal.accent}" stop-opacity="0.5"/>'
            f'<stop offset="1" stop-color="{pal.accent}" stop-opacity="0"/></radialGradient>'
        )
        out.append(
            f'<ellipse class="glow" cx="{ox:.0f}" cy="{oy + 30:.0f}" rx="82" ry="34" fill="url(#paid{pal.name})"/>'
        )

    out.append(slab(-44, -44, 0, 88, 88, 16, pal.slab_paid if paid else pal.slab, ox, oy,
                    material="slab-paid" if paid else "slab"))
    plate = [p(-44, -44, 16), p(44, -44, 16), p(44, 44, 16), p(-44, 44, 16)]
    out.append(
        f'<polygon points="{_points(plate)}" fill="none" '
        f'stroke="{_V("accent", pal.accent) if paid else _glass(pal, 0.35)}" stroke-width="1.1"/>'
    )

    z0 = 16
    if kind == "fetch":  # many raw items arriving
        rng = random.Random(3)
        items = []
        for gx in range(3):
            for gy in range(3):
                items.append((
                    -38 + gx * 26 + rng.uniform(-3, 3),
                    -38 + gy * 26 + rng.uniform(-3, 3),
                    z0 + rng.uniform(4, 34),
                    rng.uniform(10, 14),
                ))
        items.sort(key=lambda item: (item[0] + item[1], item[2]))
        choices = [(f"noise-{i}", shade) for i, shade in enumerate(noise)] * 2 + [
            ("cat-tooling", pal.category_color("tooling")),
            ("cat-models-research", pal.category_color("models_research")),
        ]
        for x, y, z, size in items:
            material, color = rng.choice(choices)
            out.append(cube(x, y, z, size, color, ox, oy, material=material))
    elif kind == "filter":  # a mesh with items above it and one that got through
        out.append(cube(-6, 10, z0, 12, pal.category_color("models_research"), ox, oy, material="cat-models-research"))
        out.append(mesh_plane(z0 + 30, 34, pal, ox, oy, cells=4, fill_alpha=0.10))
        out.append(cube(-24, -20, z0 + 44, 12, noise[1], ox, oy, material="noise-1"))
        out.append(cube(8, -28, z0 + 52, 11, noise[2], ox, oy, material="noise-2"))
    elif kind == "dedup":  # duplicates merging into one
        out.append(cube(-30, -6, z0, 18, noise[2], ox, oy, opacity=0.55, material="noise-2"))
        out.append(cube(-16, -14, z0, 18, noise[3], ox, oy, opacity=0.75, material="noise-3"))
        out.append(cube(2, 2, z0, 24, pal.category_color("tooling"), ox, oy, material="cat-tooling"))
    elif kind == "rank":  # the scored block
        out.append(cube(-18, -18, z0, 36, pal.accent, ox, oy, stroke=_V("accent-hi", pal.accent_hi), material="accent"))
        fx, fy = p(0, 0, z0 + 36)
        out.append(
            f'<text x="{fx:.1f}" y="{fy + 4:.1f}" fill="{_V("ink", pal.accent_ink)}" '
            f'font-family="Bricolage Grotesque, Helvetica, Arial, sans-serif" '
            f'font-size="18" font-weight="700" text-anchor="middle">9</text>'
        )
    elif kind == "weight":  # a graded stack with a cut plane: keep the top, drop the rest
        stack = ((-34, -10), (-10, 6), (14, -22), (2, 20))
        for i, (x, y) in enumerate(stack):
            out.append(
                cube(x, y, z0, 16, pal.accent if i == 0 else pal.noise[i % len(pal.noise)], ox, oy,
                     opacity=1.0 if i < 2 else 0.45,
                     material="accent" if i == 0 else f"noise-{i % len(noise)}")
            )
        cut = z0 + 20
        plane = [p(-40, -40, cut), p(40, -40, cut), p(40, 40, cut), p(-40, 40, cut)]
        out.append(
            f'<polygon points="{_points(plane)}" fill="none" stroke="{_V("accent", pal.accent)}" '
            f'stroke-width="1.2" stroke-dasharray="4 3" stroke-linejoin="round"/>'
        )
    elif kind == "deliver":  # a copy leaving the slab: record, email, publish
        out.append(slab(-30, -20, z0, 60, 40, 4, pal.text, ox, oy, opacity=0.5, material="text"))
        out.append(slab(-24, -16, z0 + 22, 60, 40, 4, pal.text, ox, oy, material="text"))
        a, b = p(0, 0, z0 + 8), p(0, 0, z0 + 20)
        out.append(
            f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" '
            f'stroke="{_V("accent", pal.accent)}" stroke-width="2" stroke-linecap="round"/>'
        )
        out.append(cube(12, 10, z0 + 28, 12, pal.accent, ox, oy, material="accent"))
    else:  # render — a finished page
        out.append(slab(-34, -24, z0, 68, 48, 5, pal.text, ox, oy, material="text"))
        for i, width_fraction in enumerate((0.5, 0.85, 0.7)):
            a, b = p(-26, -14 + i * 12, z0 + 5.5), p(-26 + 52 * width_fraction, -14 + i * 12, z0 + 5.5)
            out.append(
                f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" '
                f'stroke="{_V("ink", pal.accent_ink)}" stroke-opacity="0.6" '
                f'stroke-width="{3 if i == 0 else 2}" stroke-linecap="round"/>'
            )
        out.append(cube(18, 12, z0 + 5, 12, pal.accent, ox, oy, material="accent"))

    return _svg(width, height, f"{kind} pipeline step", "".join(out), defs)


# ------------------------------------------------------------ category glyphs


def category_glyph(category: str, pal: Palette, *, size: int = 64) -> str:
    """One primitive per ranked category, lit like every other solid."""
    color = pal.category_color(category)
    shape = CATEGORY_SHAPES.get(category, "cube")
    material = (
        f"cat-{category.replace('_', '-')}" if category in pal.categories else "accent"
    )
    ox, oy = size / 2, size * 0.56
    top, left, right = faces(color, material)
    unique = f"{category}{pal.name}"
    body: list[str] = []
    defs = ""
    s = size * 0.3

    def p(a: float, b: float, c: float) -> tuple[float, float]:
        return project(a, b, c, ox, oy)

    if shape == "cube":
        body.append(cube(-s / 2, -s / 2, -s / 2, s, color, ox, oy, material=material))
    elif shape == "cylinder":
        rx, ry, h = s * 0.82, s * 0.41, s * 0.9
        defs = (
            f'<linearGradient id="cyl{unique}" x1="0" x2="1">'
            f'<stop offset="0" stop-color="{left}"/>'
            f'<stop offset="0.45" stop-color="{top}"/>'
            f'<stop offset="1" stop-color="{right}"/></linearGradient>'
        )
        body.append(
            f'<path d="M{ox - rx:.1f},{oy - h / 2:.1f} v{h:.1f} '
            f'a{rx:.1f},{ry:.1f} 0 0 0 {2 * rx:.1f},0 v-{h:.1f} z" fill="url(#cyl{unique})"/>'
        )
        body.append(
            f'<ellipse cx="{ox:.1f}" cy="{oy - h / 2:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="{top}"/>'
        )
    elif shape == "pyramid":
        # Half-width across the isometric diagonal is 2*b*cos30, so keep b under
        # size/(4*cos30) or the base corners fall outside the viewBox.
        b = s * 0.82
        base = [p(-b, -b, -b * 0.5), p(b, -b, -b * 0.5), p(b, b, -b * 0.5), p(-b, b, -b * 0.5)]
        apex = p(0, 0, b * 1.35)
        body.append(f'<polygon points="{_points([base[3], base[2], apex])}" fill="{left}"/>')
        body.append(f'<polygon points="{_points([base[2], base[1], apex])}" fill="{right}"/>')
        body.append(f'<polygon points="{_points([base[0], base[1], base[2], base[3]])}" fill="{top}" opacity="0.001"/>')
    elif shape == "hexprism":
        radius, h = s * 0.95, s * 0.9
        ring = [
            (radius * math.cos(math.radians(60 * i + 30)), radius * math.sin(math.radians(60 * i + 30)))
            for i in range(6)
        ]
        top_ring = [(ox + x, oy - h / 2 + y * 0.5) for x, y in ring]
        bottom_ring = [(ox + x, oy + h / 2 + y * 0.5) for x, y in ring]
        mid = f"var(--iso-{material}-right, {mix(color, _SHADOW, 0.30)})"
        for i, face in ((0, right), (1, mid), (5, left)):
            j = (i + 1) % 6
            body.append(
                f'<polygon points="{_points([top_ring[i], top_ring[j], bottom_ring[j], bottom_ring[i]])}" fill="{face}"/>'
            )
        body.append(f'<polygon points="{_points(top_ring)}" fill="{top}"/>')
    else:  # sphere
        radius = s * 0.95
        defs = (
            f'<radialGradient id="sph{unique}" cx="35%" cy="32%" r="70%">'
            f'<stop offset="0" stop-color="{top}"/>'
            f'<stop offset="0.5" stop-color="{_V(material, color)}"/>'
            f'<stop offset="1" stop-color="{left}"/></radialGradient>'
        )
        body.append(f'<circle cx="{ox:.1f}" cy="{oy - 4:.1f}" r="{radius:.1f}" fill="url(#sph{unique})"/>')

    return _svg(size, size, f"{category} category", "".join(body), defs)


# ------------------------------------------------------------------- the mark


def mark(pal: Palette, *, size: int = 40) -> str:
    """The brand mark: a tiny sieve — two glass planes and one accent cube."""
    ox, oy = size / 2, size * 0.5
    extent = size * 0.24
    body = [
        cube(-extent * 0.28, -extent * 0.28, -extent * 1.1, extent * 0.56, pal.accent, ox, oy, material="accent"),
        mesh_plane(-extent * 0.15, extent, pal, ox, oy, cells=3, thickness=3, fill_alpha=0.12, line_alpha=0.40),
        mesh_plane(extent * 0.75, extent * 1.2, pal, ox, oy, cells=4, thickness=3, fill_alpha=0.08, line_alpha=0.30),
    ]
    return _svg(size, size, "Sift", "".join(body))


def favicon(pal: Palette) -> str:
    """A flat, high-contrast version of the mark for tiny sizes: at 16px the
    isometric sieve turns to mush, so the favicon keeps the ``S`` lockup and only
    takes its colors from the palette."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="Sift">\n'
        f'  <rect width="32" height="32" rx="7" fill="{pal.accent}"/>\n'
        f'  <text x="16" y="23.5" font-family="Helvetica, Arial, sans-serif" font-size="21" '
        f'font-weight="bold" fill="{pal.accent_ink}" text-anchor="middle">S</text>\n'
        "</svg>\n"
    )
