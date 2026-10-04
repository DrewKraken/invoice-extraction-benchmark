"""
Photo, scan and fax degradations with graded severity (mild, moderate, severe).

Every function takes a clean RGB page image, a severity and a seeded
`random.Random`, and returns a new image; nothing reads the global random
state, so the same seed gives the same pixels. Pillow only: no numpy or
OpenCV.

    apply(img, [Degradation("motion_blur", "severe")], rng)

Photo degradations (category "photo"): perspective, rotate_small,
orientation, motion_blur, defocus_blur, low_light, shadow, jpeg, low_res,
crumple, coffee_stain, annotations, crop_edges, screen_photo, combo.
Scan degradations (category "scan"): grayscale_scan, noise, fax,
punch_holes, stamp.

The parameter tables (`PARAMS`) are the definition of each grade: change a
number there and the corpus changes (a new corpus version).
"""

from __future__ import annotations

import io
import math
import random
from typing import Callable, Dict, List, Sequence, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from .spec import SEVERITIES, Degradation

Img = Image.Image

PARAMS: Dict[str, Dict[str, object]] = {
    "perspective": {"mild": 0.03, "moderate": 0.07, "severe": 0.12},          # corner shift, share of side
    "rotate_small": {"mild": 3.0, "moderate": 8.0, "severe": 15.0},           # degrees
    "orientation": {"mild": 90, "moderate": 180, "severe": 270},              # degrees clockwise
    "motion_blur": {"mild": 5, "moderate": 11, "severe": 21},                 # streak length px @200dpi
    "defocus_blur": {"mild": 1.2, "moderate": 2.4, "severe": 4.0},            # Gaussian radius px
    "low_light": {"mild": 0.70, "moderate": 0.45, "severe": 0.28},            # brightness factor
    "shadow": {"mild": 0.25, "moderate": 0.45, "severe": 0.65},               # darkening in the shadow
    "jpeg": {"mild": 40, "moderate": 30, "severe": 20},                       # JPEG quality
    "low_res": {"mild": 120, "moderate": 100, "severe": 72},                  # final dpi
    "crumple": {"mild": 1, "moderate": 2, "severe": 3},                       # folds; crumple grows with it
    "coffee_stain": {"mild": 1, "moderate": 2, "severe": 4},                  # stains
    "annotations": {"mild": 2, "moderate": 4, "severe": 7},                   # marks
    "crop_edges": {"mild": 0.02, "moderate": 0.05, "severe": 0.09},           # share cut per edge
    "screen_photo": {"mild": 0.06, "moderate": 0.12, "severe": 0.22},         # moire amplitude
    "combo": {"mild": "mild", "moderate": "moderate", "severe": "severe"},
    "grayscale_scan": {"mild": 6, "moderate": 14, "severe": 24},              # noise amplitude
    "noise": {"mild": 18, "moderate": 36, "severe": 60},                      # noise amplitude
    "fax": {"mild": 196, "moderate": 140, "severe": 98},                      # vertical dpi
    "punch_holes": {"mild": 2, "moderate": 3, "severe": 4},                   # holes
    "stamp": {"mild": 0.35, "moderate": 0.55, "severe": 0.8},                 # opacity
}

DESK = (92, 78, 66)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _noise(size: Tuple[int, int], rng: random.Random, amplitude: float) -> Img:
    """Deterministic noise centred on 128 (L mode), +-amplitude."""
    w, h = size
    raw = Image.frombytes("L", (w, h), rng.randbytes(w * h))
    raw2 = Image.frombytes("L", (w, h), rng.randbytes(w * h))
    tri = ImageChops.add(raw, raw2, scale=2.0)          # triangular, closer to Gaussian
    a = amplitude / 128.0
    return tri.point(lambda v: max(0, min(255, int(128 + (v - 128) * a))))


def _add_noise(img: Img, rng: random.Random, amplitude: float) -> Img:
    n = _noise(img.size, rng, amplitude)
    n3 = Image.merge("RGB", (n, n, n)) if img.mode == "RGB" else n
    return ImageChops.add(img, n3, scale=1.0, offset=-128)


def _field(size: Tuple[int, int], rng: random.Random, cells: int = 8, blur: float = 0.0) -> Img:
    """A smooth random field (L mode, 0..255): coarse grid upsampled."""
    w, h = size
    gw, gh = cells, max(2, int(cells * h / max(1, w)))
    small = Image.new("L", (gw, gh))
    small.putdata([rng.randint(0, 255) for _ in range(gw * gh)])
    big = small.resize((w, h), Image.BICUBIC)
    return big.filter(ImageFilter.GaussianBlur(blur)) if blur else big


def _content_box(img: Img) -> Tuple[int, int, int, int]:
    """The bounding box of the ink on a page (a document fills only part of it)."""
    g = ImageOps.invert(ImageOps.grayscale(img)).point(lambda v: 255 if v > 60 else 0)
    # the bottom strip holds only the "Page 1 of 1" footer
    box = g.crop((0, 0, img.size[0], int(img.size[1] * 0.92))).getbbox()
    return box or (0, 0, img.size[0], img.size[1])


def _in_box(box: Tuple[int, int, int, int], rng: random.Random, fx: Tuple[float, float] = (0.0, 1.0),
            fy: Tuple[float, float] = (0.0, 1.0)) -> Tuple[float, float]:
    x0, y0, x1, y1 = box
    return (x0 + (x1 - x0) * rng.uniform(*fx), y0 + (y1 - y0) * rng.uniform(*fy))


def _solve(a: List[List[float]], b: List[float]) -> List[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[piv] = m[piv], m[col]
        for r in range(n):
            if r != col and m[col][col]:
                f = m[r][col] / m[col][col]
                m[r] = [x - f * y for x, y in zip(m[r], m[col])]
    return [m[i][n] / m[i][i] for i in range(n)]


def perspective_coeffs(src: Sequence[Tuple[float, float]], dst: Sequence[Tuple[float, float]]) -> List[float]:
    """Coefficients for Image.transform(PERSPECTIVE) mapping output `dst`
    points back to input `src` points."""
    a, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b.extend([u, v])
    return _solve(a, b)


def _on_desk(img: Img, rng: random.Random, margin: float = 0.06) -> Img:
    w, h = img.size
    mw, mh = int(w * margin), int(h * margin)
    desk = Image.new("RGB", (w + 2 * mw, h + 2 * mh), DESK)
    desk = _add_noise(desk, rng, 10)
    desk.paste(img, (mw, mh))
    return desk


# ---------------------------------------------------------------------------
# photo degradations
# ---------------------------------------------------------------------------


def perspective(img: Img, sev: str, rng: random.Random) -> Img:
    k = float(PARAMS["perspective"][sev])
    base = _on_desk(img, rng, margin=k + 0.03)
    w, h = base.size
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    dst = [(x + rng.uniform(-k, k) * w, y + rng.uniform(-k, k) * h) for x, y in src]
    coeffs = perspective_coeffs(src, dst)
    return base.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor=DESK)


def rotate_small(img: Img, sev: str, rng: random.Random) -> Img:
    deg = float(PARAMS["rotate_small"][sev]) * rng.choice([-1, 1])
    return img.rotate(deg, resample=Image.BICUBIC, expand=True, fillcolor="white")


def orientation(img: Img, sev: str, rng: random.Random) -> Img:
    deg = int(PARAMS["orientation"][sev])
    return img.rotate(-deg, expand=True)


def motion_blur(img: Img, sev: str, rng: random.Random) -> Img:
    length = int(PARAMS["motion_blur"][sev])
    angle = rng.uniform(0, math.pi)
    dx, dy = math.cos(angle), math.sin(angle)
    acc = img
    for i in range(1, length):
        t = i - length / 2
        shifted = img.transform(img.size, Image.AFFINE, (1, 0, -t * dx, 0, 1, -t * dy),
                                resample=Image.BILINEAR, fillcolor="white")
        acc = Image.blend(acc, shifted, 1.0 / (i + 1))
    return acc


def defocus_blur(img: Img, sev: str, rng: random.Random) -> Img:
    return img.filter(ImageFilter.GaussianBlur(float(PARAMS["defocus_blur"][sev])))


def low_light(img: Img, sev: str, rng: random.Random) -> Img:
    f = float(PARAMS["low_light"][sev])
    out = ImageEnhance.Brightness(img).enhance(f)
    out = ImageEnhance.Contrast(out).enhance(0.75 + f * 0.25)
    r, g, b = out.split()
    out = Image.merge("RGB", (r, g, b.point(lambda v: int(v * 0.88))))   # warm indoor cast
    return _add_noise(out, rng, 10 + (1 - f) * 30)


def shadow(img: Img, sev: str, rng: random.Random) -> Img:
    depth = float(PARAMS["shadow"][sev])
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    # a hand / phone shadow: a polygon from one side, soft edged
    side = rng.choice(["left", "right", "top", "bottom"])
    reach = rng.uniform(0.3, 0.6)
    if side == "left":
        poly = [(0, 0), (w * reach, 0), (w * reach * rng.uniform(0.4, 1.2), h), (0, h)]
    elif side == "right":
        poly = [(w, 0), (w * (1 - reach), 0), (w * (1 - reach * rng.uniform(0.4, 1.2)), h), (w, h)]
    elif side == "top":
        poly = [(0, 0), (w, 0), (w, h * reach * rng.uniform(0.4, 1.2)), (0, h * reach)]
    else:
        poly = [(0, h), (w, h), (w, h * (1 - reach)), (0, h * (1 - reach * rng.uniform(0.4, 1.2)))]
    d.polygon(poly, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(w * 0.04))
    # plus a gentle vignette
    vign = _field((w, h), rng, cells=4).point(lambda v: int(v * 0.25))
    mask = ImageChops.lighter(mask.point(lambda v: int(v * depth)), vign.point(lambda v: int(v * depth)))
    dark = ImageEnhance.Brightness(img).enhance(0.25)
    return Image.composite(dark, img, mask.point(lambda v: min(255, int(v)))) if depth else img


def jpeg(img: Img, sev: str, rng: random.Random) -> Img:
    q = int(PARAMS["jpeg"][sev])
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=q)
    buf.seek(0)
    out = Image.open(buf)
    out.load()
    out.info["eval_jpeg_quality"] = q
    return out.convert("RGB")


def low_res(img: Img, sev: str, rng: random.Random, source_dpi: int = 200) -> Img:
    dpi = int(PARAMS["low_res"][sev])
    w, h = img.size
    out = img.resize((max(1, int(w * dpi / source_dpi)), max(1, int(h * dpi / source_dpi))), Image.BILINEAR)
    out.info["eval_dpi"] = dpi
    return out


def crumple(img: Img, sev: str, rng: random.Random) -> Img:
    folds = int(PARAMS["crumple"][sev])
    w, h = img.size
    shade = Image.new("L", (w, h), 128)
    d = ImageDraw.Draw(shade)
    for i in range(folds):
        if i % 2 == 0:
            x = int(w * rng.uniform(0.3, 0.7))
            d.rectangle((x - 3, 0, x, h), fill=95)
            d.rectangle((x, 0, x + 5, h), fill=165)
        else:
            y = int(h * rng.uniform(0.3, 0.7))
            d.rectangle((0, y - 3, w, y), fill=95)
            d.rectangle((0, y, w, y + 5), fill=165)
    shade = shade.filter(ImageFilter.GaussianBlur(3.5))
    cells = 10 + 8 * folds
    crumples = _field((w, h), rng, cells=cells, blur=w / cells * 0.7).point(
        lambda v: int(128 + (v - 128) * (0.10 * folds)))
    edges = crumples.filter(ImageFilter.FIND_EDGES).point(lambda v: min(255, v * 3))
    texture = ImageChops.add(ImageChops.add(shade, crumples, 2.0), edges.point(lambda v: v // 3), 1.0, -20)
    tex_rgb = Image.merge("RGB", (texture, texture, texture))
    return ImageChops.multiply(img, ImageChops.add(tex_rgb, tex_rgb, 1.0, 0))


def coffee_stain(img: Img, sev: str, rng: random.Random) -> Img:
    n = int(PARAMS["coffee_stain"][sev])
    w, h = img.size
    box = _content_box(img)
    over = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(over)
    for i in range(n):
        r = rng.uniform(0.05, 0.11) * w * (1.0 + 0.2 * i)
        # stains land on the document; a severe one on the totals (bottom right of the ink)
        if sev == "severe" and i == 0:
            cx, cy = _in_box(box, rng, (0.65, 0.95), (0.75, 0.95))
        else:
            cx, cy = _in_box(box, rng)
        tone = (rng.randint(150, 185), rng.randint(105, 135), rng.randint(60, 85))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=tuple(int(255 - (255 - v) * (0.25 + 0.1 * SEVERITIES.index(sev))) for v in tone))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=tone, width=max(2, int(r * 0.07)))
    over = over.filter(ImageFilter.GaussianBlur(3))
    return ImageChops.multiply(img, over)


def annotations(img: Img, sev: str, rng: random.Random) -> Img:
    from .handwriting import draw_hand

    n = int(PARAMS["annotations"][sev])
    w, h = img.size
    out = img.copy()
    d = ImageDraw.Draw(out)
    px = w / 45
    box = _content_box(img)
    notes = ["PAID", "OK", "Approved JB", "chk", "pls query", "GRN 4471", "2nd copy", "recd",
             "x 2?", "acc 6020", "see email", "short 1 box"]
    for i in range(n):
        kind = rng.choice(["note", "tick", "circle", "underline", "number"]) if i else "note"
        x, y = _in_box(box, rng, (0.0, 0.8), (0.05, 1.0))
        ink = rng.choice([(20, 40, 150), (160, 20, 20), (30, 30, 30)])
        if kind == "note":
            draw_hand(out, x, y, rng.choice(notes), px, ink, "average", rng)
        elif kind == "number":
            # a handwritten amount near the totals: the trap a reader must not take
            nx, ny = _in_box(box, rng, (0.5, 0.75), (0.8, 1.0))
            draw_hand(out, nx, ny,
                      f"{rng.randint(100, 9999)}.{rng.randint(0, 99):02d}", px * 1.1, ink, "average", rng)
        elif kind == "tick":
            d.line((x, y, x + px * 0.4, y + px * 0.5, x + px * 1.2, y - px * 0.6), fill=ink, width=max(2, int(px / 8)))
        elif kind == "circle":
            r = px * rng.uniform(1.0, 2.5)
            d.ellipse((x - r * 2, y - r, x + r * 2, y + r), outline=ink, width=max(2, int(px / 9)))
        else:
            d.line((x, y, x + px * rng.uniform(4, 10), y + rng.uniform(-3, 3)), fill=ink, width=max(2, int(px / 9)))
    return out


def crop_edges(img: Img, sev: str, rng: random.Random) -> Img:
    k = float(PARAMS["crop_edges"][sev])
    w, h = img.size
    edges = {"mild": 1, "moderate": 2, "severe": 3}[sev]
    chosen = rng.sample(["left", "top", "right", "bottom"], edges)
    box = [0, 0, w, h]
    for e in chosen:
        cut = k * rng.uniform(0.8, 1.2)
        if e == "left":
            box[0] = int(w * cut)
        elif e == "top":
            box[1] = int(h * cut)
        elif e == "right":
            box[2] = int(w * (1 - cut))
        else:
            box[3] = int(h * (1 - cut))
    return img.crop(tuple(box))


def screen_photo(img: Img, sev: str, rng: random.Random) -> Img:
    amp = float(PARAMS["screen_photo"][sev])
    w, h = img.size
    # a screen is emissive: invert-ish contrast, cool tint, raised black level
    out = ImageEnhance.Contrast(img).enhance(0.8)
    r, g, b = out.split()
    out = Image.merge("RGB", (r.point(lambda v: int(v * 0.9)), g, b.point(lambda v: min(255, int(v * 1.02 + 6)))))
    # moire: the beat between the screen's pixel grid and the camera sensor,
    # slow sinusoidal bands at a slight angle
    period = rng.uniform(5.5, 9.0)
    row = Image.new("L", (w * 2, 1))
    row.putdata([int(128 + 127 * math.sin(x / period)) for x in range(w * 2)])
    stripes = row.resize((w * 2, h * 2), Image.NEAREST).rotate(rng.uniform(-20, 20), resample=Image.BILINEAR)
    stripes = stripes.crop((w // 2, h // 2, w // 2 + w, h // 2 + h))
    moire = stripes.point(lambda v: int(255 - amp * (255 - v)))
    out = ImageChops.multiply(out, Image.merge("RGB", (moire, moire, moire)))
    # the RGB subpixel grid: one 3-pixel row band, repeated
    band = Image.new("RGB", (w, 3))
    band.putdata([((255, 225, 225), (225, 255, 225), (225, 225, 255))[x % 3] for _y in range(3) for x in range(w)])
    pattern = Image.new("RGB", (w, h))
    for y0 in range(0, h, 3):
        pattern.paste(band, (0, y0))
    out = Image.blend(out, ImageChops.multiply(out, pattern), min(1.0, amp * 3))
    # glare
    glare = Image.new("L", (w, h), 0)
    gd = ImageDraw.Draw(glare)
    gx, gy, gr = rng.uniform(0.2, 0.8) * w, rng.uniform(0.2, 0.8) * h, rng.uniform(0.1, 0.25) * w
    gd.ellipse((gx - gr, gy - gr, gx + gr, gy + gr), fill=int(255 * amp * 2.2))
    glare = glare.filter(ImageFilter.GaussianBlur(gr * 0.6))
    out = Image.composite(Image.new("RGB", (w, h), (250, 250, 250)), out, glare)
    out = out.filter(ImageFilter.GaussianBlur(0.6 + amp * 4))
    return perspective(out, "mild", rng)


def combo(img: Img, sev: str, rng: random.Random) -> Img:
    """A realistic phone capture: tilt + shadow + blur + JPEG at one grade."""
    out = perspective(img, sev, rng)
    out = shadow(out, sev, rng)
    out = defocus_blur(out, "mild" if sev != "severe" else "moderate", rng)
    return jpeg(out, sev, rng)


# ---------------------------------------------------------------------------
# scan / fax degradations
# ---------------------------------------------------------------------------


def grayscale_scan(img: Img, sev: str, rng: random.Random) -> Img:
    amp = float(PARAMS["grayscale_scan"][sev])
    g = ImageOps.grayscale(img)
    g = ImageEnhance.Contrast(g).enhance(0.85).point(lambda v: min(255, int(v * 0.93 + 8)))
    g = _add_noise(g, rng, amp)
    g = g.rotate(rng.uniform(-0.8, 0.8), resample=Image.BICUBIC, fillcolor=240)
    return g.convert("RGB")


def noise(img: Img, sev: str, rng: random.Random) -> Img:
    out = _add_noise(img, rng, float(PARAMS["noise"][sev]))
    # salt and pepper specks
    w, h = img.size
    d = ImageDraw.Draw(out)
    for _ in range(int(w * h / 4000 * SEVERITIES.index(sev) + 50)):
        x, y = rng.randrange(w), rng.randrange(h)
        c = 0 if rng.random() < 0.5 else 255
        d.point((x, y), fill=(c, c, c))
    return out


def fax(img: Img, sev: str, rng: random.Random, source_dpi: int = 200) -> Img:
    vdpi = int(PARAMS["fax"][sev])
    w, h = img.size
    g = ImageOps.grayscale(img)
    small = g.resize((int(w * 204 / source_dpi), int(h * vdpi / source_dpi)), Image.BILINEAR)
    small = _add_noise(small, rng, 20 + (196 - vdpi) * 0.3)
    bw = small.point(lambda v: 255 if v > 150 else 0, mode="1").convert("L")
    d = ImageDraw.Draw(bw)
    sw, sh = bw.size
    for _ in range(int(sw * sh / 2500 * (1 + SEVERITIES.index(sev)))):
        d.point((rng.randrange(sw), rng.randrange(sh)), fill=0)
    for _ in range(SEVERITIES.index(sev) * 2):
        y = rng.randrange(sh)
        d.line((0, y, sw, y), fill=0 if rng.random() < 0.5 else 255, width=1)
    header = f"FAX  {rng.randint(10, 28):02d}/0{rng.randint(1, 9)}/2026 {rng.randint(10, 23)}:{rng.randint(10, 59)}  P.001"
    from PIL import ImageFont
    try:
        d.text((10, 4), header, fill=0, font=ImageFont.load_default(size=max(10, sh // 110)))
    except TypeError:  # Pillow < 10.1
        d.text((10, 4), header, fill=0)
    bw = bw.point(lambda v: 255 if v > 127 else 0)   # the header text is anti-aliased
    # back to the source resolution, as a fax-to-email PDF would be rendered
    return bw.resize((w, h), Image.NEAREST).convert("RGB")


def punch_holes(img: Img, sev: str, rng: random.Random) -> Img:
    n = int(PARAMS["punch_holes"][sev])
    w, h = img.size
    out = img.copy()
    d = ImageDraw.Draw(out)
    r = w * 0.018
    x = w * (0.035 if sev != "severe" else 0.07)    # severe: punched into the text
    for i in range(n):
        y = h * (0.15 + 0.7 * i / max(1, n - 1))
        d.ellipse((x - r, y - r, x + r, y + r), fill=(25, 25, 25) if rng.random() < 0.7 else (255, 255, 255),
                  outline=(90, 90, 90))
    return out


def stamp(img: Img, sev: str, rng: random.Random) -> Img:
    alpha = float(PARAMS["stamp"][sev])
    w, h = img.size
    word = rng.choice(["RECEIVED", "PAID", "APPROVED", "ENTERED", "COPY"])
    date_txt = f"{rng.randint(1, 28):02d} {rng.choice(['JAN', 'MAR', 'JUN', 'SEP'])} 2026"
    sw, sh = int(w * 0.36), int(w * 0.14)
    st = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    d = ImageDraw.Draw(st)
    ink = rng.choice([(190, 30, 30), (30, 50, 170), (40, 120, 60)])
    d.rounded_rectangle((4, 4, sw - 4, sh - 4), radius=sh // 6, outline=(*ink, 255), width=max(3, sh // 18))
    from .render import _pil_font
    f1 = _pil_font("sans-bold", int(sh * 0.38))
    f2 = _pil_font("sans-bold", int(sh * 0.2))
    d.text((sw / 2, sh * 0.45), word, font=f1, fill=(*ink, 255), anchor="mm")
    d.text((sw / 2, sh * 0.78), date_txt, font=f2, fill=(*ink, 255), anchor="mm")
    st = st.rotate(rng.uniform(-25, 25), expand=True, resample=Image.BICUBIC)
    a = st.getchannel("A").point(lambda v: int(v * alpha))
    st.putalpha(a)
    # severe stamps land on the header block (number / date) or the totals
    box = _content_box(img)
    if sev == "severe":
        x, y = _in_box(box, rng, (0.55, 0.62), rng.choice([(0.0, 0.05), (0.75, 0.8)]))
    else:
        x, y = _in_box(box, rng, (0.05, 0.6), (0.2, 0.7))
    pos = (int(x), int(y))
    out = img.convert("RGBA")
    out.alpha_composite(st, (min(pos[0], w - 1), min(pos[1], h - 1)))
    return out.convert("RGB")


REGISTRY: Dict[str, Callable[[Img, str, random.Random], Img]] = {
    "perspective": perspective, "rotate_small": rotate_small, "orientation": orientation,
    "motion_blur": motion_blur, "defocus_blur": defocus_blur, "low_light": low_light, "shadow": shadow,
    "jpeg": jpeg, "low_res": low_res, "crumple": crumple, "coffee_stain": coffee_stain,
    "annotations": annotations, "crop_edges": crop_edges, "screen_photo": screen_photo, "combo": combo,
    "grayscale_scan": grayscale_scan, "noise": noise, "fax": fax, "punch_holes": punch_holes, "stamp": stamp,
}
PHOTO_KINDS = ("perspective", "rotate_small", "orientation", "motion_blur", "defocus_blur", "low_light",
               "shadow", "jpeg", "low_res", "crumple", "coffee_stain", "annotations", "crop_edges",
               "screen_photo", "combo")
SCAN_KINDS = ("grayscale_scan", "noise", "fax", "punch_holes", "stamp")


def apply(img: Img, degradations: Sequence[Degradation], rng: random.Random) -> Img:
    out = img.convert("RGB")
    for d in degradations:
        if d.kind not in REGISTRY:
            raise KeyError(f"unknown degradation {d.kind!r}")
        if d.severity not in SEVERITIES:
            raise ValueError(f"unknown severity {d.severity!r}")
        info = dict(out.info)
        out = REGISTRY[d.kind](out, d.severity, rng)
        for k, v in info.items():
            if k.startswith("eval_") and k not in out.info:
                out.info[k] = v
    return out
