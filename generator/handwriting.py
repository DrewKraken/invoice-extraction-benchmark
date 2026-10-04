"""
Handwriting-style text for the raster renderer, with graded legibility.

No handwriting font ships with the repo, so the look comes from two parts:

  * a script-like font: the first found of INVOICE_BENCH_HAND_FONT (a path), a
    handwriting font installed on the machine (Windows: Ink Free, Segoe
    Print, Bradley Hand, Lucida Handwriting, Comic Sans; Linux: Caveat,
    Kalam, Comic Neue...), else reportlab's bundled Vera Sans Oblique;
  * per-glyph jitter drawn with Pillow: rotation, size, baseline drift,
    spacing and stroke weight, all from a seeded RNG, increasing with the
    legibility grade (neat < average < poor). "poor" also overstrikes some
    glyphs and drops a few ink blots.

The font file found is recorded in the corpus manifest; two machines with
different fonts produce different pixels from the same seed (the text is the
same). Set INVOICE_BENCH_HAND_FONT to pin it. The published corpus was drawn
with Windows' Ink Free (Inkfree.ttf); the font itself is not distributed.
"""

from __future__ import annotations

import glob
import hashlib
import os
import random
from functools import lru_cache
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

LEGIBILITY = ("neat", "average", "poor")

# (rotation degrees, size jitter, baseline drift px-per-em, spacing jitter, overstrike prob)
_JITTER = {
    "neat": (3.0, 0.04, 0.03, 0.04, 0.0),
    "average": (7.0, 0.09, 0.07, 0.10, 0.02),
    "poor": (13.0, 0.17, 0.14, 0.20, 0.08),
}

_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\Inkfree.ttf", r"C:\Windows\Fonts\segoepr.ttf", r"C:\Windows\Fonts\BRADHITC.TTF",
    r"C:\Windows\Fonts\LHANDW.TTF", r"C:\Windows\Fonts\comic.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf", "/Library/Fonts/Comic Sans MS.ttf",
]
_LINUX_GLOBS = ["/usr/share/fonts/**/Caveat*.ttf", "/usr/share/fonts/**/Kalam*.ttf",
                "/usr/share/fonts/**/ComicNeue*.ttf", "/usr/share/fonts/**/*Handlee*.ttf",
                "/usr/share/fonts/**/*comic*.ttf"]


def _fallback_font() -> str:
    import reportlab

    return os.path.join(os.path.dirname(reportlab.__file__), "fonts", "VeraIt.ttf")


@lru_cache(maxsize=1)
def hand_font_path() -> str:
    pinned = os.getenv("INVOICE_BENCH_HAND_FONT")
    if pinned and os.path.isfile(pinned):
        return pinned
    for path in _CANDIDATES:
        if os.path.isfile(path):
            return path
    for pattern in _LINUX_GLOBS:
        found = sorted(glob.glob(pattern, recursive=True))
        if found:
            return found[0]
    return _fallback_font()


def hand_font_fingerprint() -> Tuple[str, str]:
    path = hand_font_path()
    with open(path, "rb") as fh:
        return os.path.basename(path), hashlib.sha256(fh.read()).hexdigest()[:16]


@lru_cache(maxsize=64)
def _font(px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(hand_font_path(), max(6, px))


def draw_hand(
    img: Image.Image,
    x: float,
    baseline: float,
    text: str,
    px: float,
    color: Tuple[int, int, int],
    legibility: str,
    rng: random.Random,
    align: str = "left",
    target_width: Optional[float] = None,
) -> None:
    """Draw `text` on `img` starting at (x, baseline), glyph by glyph."""
    rot, size_j, drift_j, space_j, over_p = _JITTER.get(legibility, _JITTER["average"])
    base_font = _font(int(px))
    # Scale so the written word spans roughly the width the layout measured.
    natural = base_font.getlength(text)
    scale = 1.0
    if target_width and natural > 0:
        scale = max(0.75, min(1.25, target_width / natural))
    width_est = natural * scale
    if align == "right":
        x -= width_est
    elif align == "center":
        x -= width_est / 2
    drift = 0.0
    # Draw into a strip around the text, not a page-sized layer.
    ox, oy = int(x - px), int(baseline - 2.2 * px)
    layer = Image.new("RGBA", (int(width_est * 1.35 + 3 * px), int(3.4 * px)), (0, 0, 0, 0))
    x, baseline = x - ox, baseline - oy
    cx = x
    for ch in text:
        size = max(6, int(px * scale * (1 + rng.uniform(-size_j, size_j))))
        font = _font(size)
        adv = font.getlength(ch)
        if ch.strip():
            pad = int(size * 0.6)
            tile = Image.new("RGBA", (int(adv) + 2 * pad, int(size * 1.6) + 2 * pad), (0, 0, 0, 0))
            td = ImageDraw.Draw(tile)
            alpha = rng.randint(200, 255)
            ink = (*color, alpha)
            td.text((pad, pad + size), ch, font=font, fill=ink, anchor="ls")
            if rng.random() < over_p:
                td.text((pad + 1, pad + size - 1), ch, font=font, fill=ink, anchor="ls")
            tile = tile.rotate(rng.uniform(-rot, rot), resample=Image.BICUBIC, expand=False)
            layer.paste(tile, (int(cx - pad), int(baseline + drift - size - pad)), tile)
        drift += rng.uniform(-drift_j, drift_j) * px
        drift = max(-0.35 * px, min(0.35 * px, drift))
        cx += adv * (1 + rng.uniform(-space_j, space_j))
    if legibility == "poor" and text.strip() and rng.random() < 0.25:
        d = ImageDraw.Draw(layer)
        bx = rng.uniform(x, max(x + 1, cx))
        r = rng.uniform(0.08, 0.18) * px
        d.ellipse((bx - r, baseline - r, bx + r, baseline + r), fill=(*color, 120))
    img.paste(layer, (ox, oy), layer)
