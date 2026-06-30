"""Generate the static-raster OG / cover cards (1200×630 PNG).

Best-effort by design: any failure (Pillow not installed, no usable font, disk
error) is logged and returns False, so the weekly run never breaks — callers fall
back to the committed static ``docs/assets/og.png``. Pillow is imported lazily
inside the functions so a missing dependency surfaces as a caught ImportError."""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger("sift.card")

W, H = 1200, 630
BG = (27, 20, 16)  # #1b1410 warm umber
ACCENT = (224, 122, 79)  # #e07a4f terracotta
INK = (239, 231, 217)  # #efe7d9 cream
MUTED = (173, 159, 133)  # #ad9f85
CAT_COLORS = {
    "models_research": (139, 132, 240),
    "tooling": (45, 212, 191),
    "infra": (245, 158, 11),
    "policy": (251, 113, 133),
    "business": (74, 222, 128),
}

# Serif (wordmark / headline) and mono (data) font candidates, mirroring
# scripts/gen_favicons.py. load_default() is the last resort so a card always
# renders, even on a minimal box.
SERIF_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/Library/Fonts/Georgia.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
]
MONO_CANDIDATES = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]


def _font(candidates: list[str], size: int):
    from PIL import ImageFont

    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _base():
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 12], fill=ACCENT)  # top accent rule
    draw.text((72, 60), "SIFT", font=_font(SERIF_CANDIDATES, 132), fill=INK)
    return img, draw


def render_static_card(path: Path) -> bool:
    """Brand card for the prose pages and the universal fallback. Returns True
    on success, False (logged) on any failure."""
    try:
        img, draw = _base()
        draw.text(
            (76, 232),
            "Weekly AI signal — curated for one reader",
            font=_font(SERIF_CANDIDATES, 44),
            fill=MUTED,
        )
        draw.text(
            (76, 520),
            "one Claude call  ·  everything else local & free",
            font=_font(MONO_CANDIDATES, 30),
            fill=ACCENT,
        )
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        img.save(path, "PNG")
        return True
    except Exception:  # noqa: BLE001 - best-effort; caller falls back to committed og.png
        log.exception("Static OG card generation failed")
        return False


def render_issue_card(
    path: Path,
    *,
    week: str,
    range_label: str,
    headline: str,
    category_counts: dict[str, int],
    story_count: int,
    feed_count: int,
) -> bool:
    """Per-issue cover card (also the digest's og:image). Returns True on
    success, False (logged) on any failure."""
    try:
        img, draw = _base()
        draw.text(
            (76, 224),
            f"WEEK {week}  ·  {range_label}",
            font=_font(MONO_CANDIDATES, 34),
            fill=ACCENT,
        )
        head_font = _font(SERIF_CANDIDATES, 54)
        y = 300
        for line in _wrap(draw, headline, head_font, W - 150)[:3]:
            draw.text((76, y), line, font=head_font, fill=INK)
            y += 64
        # category-mix bar
        total = sum(category_counts.values()) or 1
        x, bar_y, bar_w = 76, 522, W - 152
        for cat, count in category_counts.items():
            seg = int(bar_w * count / total)
            if seg <= 0:
                continue
            draw.rectangle([x, bar_y, x + seg, bar_y + 26], fill=CAT_COLORS.get(cat, MUTED))
            x += seg
        draw.text(
            (76, 568),
            f"{story_count} stories  ·  {feed_count} feeds  ·  one Claude call",
            font=_font(MONO_CANDIDATES, 28),
            fill=MUTED,
        )
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        img.save(path, "PNG")
        return True
    except Exception:  # noqa: BLE001 - best-effort
        log.exception("Issue OG card generation failed for %s", week)
        return False
