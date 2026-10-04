"""
Pages -> a digital PDF (reportlab) or raster pages (Pillow).

Both backends draw the same `layout.Page` operations. The PDF uses the
standard Helvetica / Times / Courier fonts, so it carries a real text layer
like an accounting package's export; the raster uses the URW Type 1 clones of
those fonts that ship inside reportlab (same metrics), so text lands in the
same place.
"""

from __future__ import annotations

import io
import os
import random
from functools import lru_cache
from typing import List, Sequence

from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen.canvas import Canvas

from .handwriting import draw_hand
from .layout import PDF_FONTS, Box, Page, Rule, Text, text_width

_RL_FONT_DIR = None


def _rl_font_dir() -> str:
    global _RL_FONT_DIR
    if _RL_FONT_DIR is None:
        import reportlab

        _RL_FONT_DIR = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    return _RL_FONT_DIR


_PIL_FONT_FILES = {
    "sans": "_a______.pfb", "sans-bold": "_ab_____.pfb",
    "serif": "_er_____.pfb", "serif-bold": "_eb_____.pfb",
    "mono": "com_____.pfb", "mono-bold": "cob_____.pfb",
    "hand": "_ai_____.pfb",
}


@lru_cache(maxsize=256)
def _pil_font(name: str, px: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(_rl_font_dir(), _PIL_FONT_FILES.get(name, "_a______.pfb"))
    try:
        return ImageFont.truetype(path, max(4, px))
    except OSError:  # pragma: no cover - a reportlab build without the Type 1 files
        return ImageFont.truetype(os.path.join(_rl_font_dir(), "Vera.ttf"), max(4, px))


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


def render_pdf(pages: Sequence[Page], title: str = "", author: str = "") -> bytes:
    """A deterministic PDF (invariant=1: no timestamp, fixed document id).
    The creator string is part of the bytes: keep it, or the published
    sha256 sums stop matching."""
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=(pages[0].width, pages[0].height), invariant=1)
    c.setCreator("IPP accuracy benchmark generator")
    if title:
        c.setTitle(title)
    if author:
        c.setAuthor(author)
    for page in pages:
        c.setPageSize((page.width, page.height))
        H = page.height
        for op in page.ops:
            if isinstance(op, Box):
                if op.fill is not None:
                    c.setFillColorRGB(*(v / 255 for v in op.fill))
                if op.stroke is not None:
                    c.setStrokeColorRGB(*(v / 255 for v in op.stroke))
                    c.setLineWidth(op.width)
                c.rect(op.x, H - op.y - op.h, op.w, op.h, fill=1 if op.fill else 0, stroke=1 if op.stroke else 0)
            elif isinstance(op, Rule):
                c.setStrokeColorRGB(*(v / 255 for v in op.color))
                c.setLineWidth(op.width)
                c.line(op.x1, H - op.y1, op.x2, H - op.y2)
            elif isinstance(op, Text):
                c.setFillColorRGB(*(v / 255 for v in op.color))
                c.setFont(PDF_FONTS.get(op.font, "Helvetica"), op.size)
                c.drawString(op.left, H - op.y, op.text)
        c.showPage()
    c.save()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Raster
# ---------------------------------------------------------------------------


def render_page_image(page: Page, dpi: int = 200, seed: str = "") -> Image.Image:
    k = dpi / 72.0
    img = Image.new("RGB", (int(round(page.width * k)), int(round(page.height * k))), "white")
    draw = ImageDraw.Draw(img)
    for i, op in enumerate(page.ops):
        if isinstance(op, Box):
            x0, y0 = op.x * k, op.y * k
            x1, y1 = (op.x + op.w) * k, (op.y + op.h) * k
            draw.rectangle((x0, y0, x1, y1), fill=op.fill, outline=op.stroke,
                           width=max(1, int(round(op.width * k))) if op.stroke else 0)
        elif isinstance(op, Rule):
            draw.line((op.x1 * k, op.y1 * k, op.x2 * k, op.y2 * k), fill=op.color,
                      width=max(1, int(round(op.width * k))))
        elif isinstance(op, Text):
            if op.hand:
                rng = random.Random(f"{seed}:{i}:{op.text}")
                draw_hand(img, op.left * k if op.align == "left" else op.x * k, op.y * k, op.text,
                          op.size * k, op.color, op.hand, rng, align=op.align,
                          target_width=text_width(op.text, op.font, op.size) * k)
                draw = ImageDraw.Draw(img)
            else:
                font = _pil_font(op.font, int(round(op.size * k)))
                draw.text((op.left * k, op.y * k), op.text, font=font, fill=op.color, anchor="ls")
    return img


def render_images(pages: Sequence[Page], dpi: int = 200, seed: str = "") -> List[Image.Image]:
    return [render_page_image(p, dpi, f"{seed}:{n}") for n, p in enumerate(pages)]
