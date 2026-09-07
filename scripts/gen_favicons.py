"""Generate the raster favicon set from the Sift lettermark (dev tool).

``docs/assets/favicon.svg`` is generated on every ``sift site`` run and works in
modern browsers; this produces the raster fallbacks for older browsers, iOS home
screens and link previews. Those rasters are committed binaries, so they do NOT
follow a palette change on their own — run this after changing the palette or
the mark, or the tab icon and the home-screen icon will disagree:

    uv run python scripts/gen_favicons.py

Colors come from ``sift.theme``, so this stays in step with everything else.
Requires Pillow. Outputs are committed under docs/assets/.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sift import theme  # noqa: E402  (needs the path above)


def _rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


_PALETTE = theme.palette()
ACCENT = _rgb(_PALETTE.accent)
INK = _rgb(_PALETTE.accent_ink)
ASSETS = Path(__file__).resolve().parents[1] / "docs" / "assets"

# The SVG mark uses a grotesque, so the raster set matches rather than falling
# back to the old serif lettermark.
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_mark(size: int, *, rounded: bool) -> Image.Image:
    """Accent tile with a centered dark-ink 'S', matching favicon.svg."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if rounded:
        draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=ACCENT)
    else:
        draw.rectangle([0, 0, size, size], fill=ACCENT)  # full bleed for apple-touch
    font = _font(int(size * 0.7))
    bbox = draw.textbbox((0, 0), "S", font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), "S", font=font, fill=INK)
    return img


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    master = _draw_mark(512, rounded=True)

    for size in (16, 32):
        master.resize((size, size), Image.LANCZOS).save(ASSETS / f"favicon-{size}.png")
    master.resize((32, 32), Image.LANCZOS).save(
        ASSETS / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)]
    )
    # Apple touch icon: full-bleed (iOS applies its own rounded mask), opaque.
    _draw_mark(180, rounded=False).convert("RGB").save(ASSETS / "apple-touch-icon.png")
    print(f"Wrote favicon set to {ASSETS}")


if __name__ == "__main__":
    main()
