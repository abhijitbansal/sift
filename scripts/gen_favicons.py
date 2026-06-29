"""Generate the raster favicon set from the Sift lettermark (dev tool).

The SVG favicon (docs/assets/favicon.svg) is the source of truth and works in
modern browsers; this produces the raster fallbacks for older browsers, iOS
home screens, and link previews. Run after changing the mark:

    uv run python scripts/gen_favicons.py

Requires Pillow (a dev dependency). Outputs are committed under docs/assets/.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ACCENT = (180, 84, 46)  # #b4542e
CREAM = (253, 253, 251)  # #fdfdfb
ASSETS = Path(__file__).resolve().parents[1] / "docs" / "assets"

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/Library/Fonts/Georgia.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_mark(size: int, *, rounded: bool) -> Image.Image:
    """Terracotta tile with a centered cream serif 'S'."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if rounded:
        draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=ACCENT)
    else:
        draw.rectangle([0, 0, size, size], fill=ACCENT)  # full bleed for apple-touch
    font = _font(int(size * 0.7))
    bbox = draw.textbbox((0, 0), "S", font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), "S", font=font, fill=CREAM)
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
