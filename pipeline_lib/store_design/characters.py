"""Cut a new comic's people out of its carousel pages for the page backdrop (build time, CPU).

    python -m store_design.characters --issue 57 --slides carousel/<dir>/2.jpg carousel/<dir>/3.jpg ...

Slides 2-4 of a carousel are real comic pages centred on a 1080x1350 card. Each page is split
into panels on its gutters, every panel goes through rembg's human-segmentation model, and a
cut-out is kept only when it is one solid figure with no lettering in it. The best few are tinted
blood-red and written to candidates/<NN>_<slide>_<panel>.json, with a preview sheet
candidates/<NN>_sheet.png.

⭐⭐ CANDIDATES ONLY. The human-segmentation model happily cuts out life rings, palm trees and
headless torsos (first cloud run, 2026-09-16: 5 of 6 picks were junk), and a face detector did not
separate them either (YuNet at 0.7 kept 5 junk and lost two thirds of the good figures). Nothing
reaches a live page until someone approves it: store_sync.yml approve_chars=<keys> moves the
chosen files into chars/. Needs: rembg, onnxruntime, scipy, numpy, Pillow
(rapidocr-onnxruntime optional, for the lettering check).
"""
import argparse
import base64
import io
import json
import os

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES_DIR = os.path.join(HERE, "candidates")
PAGE_BOX = (150, 115, 930, 1318)  # the comic page inside a carousel slide
BODY = np.array([36, 22, 26], float)    # silhouette fill, a touch lighter than the #0b0b0d ground
LIGHT = np.array([150, 44, 38], float)  # highlights glow blood-red


def _runs(mask, min_len):
    out, start = [], None
    for i, m in enumerate(list(mask) + [True]):
        if not m and start is None:
            start = i
        elif m and start is not None:
            if i - start >= min_len:
                out.append((start, i))
            start = None
    return out


def panels(path, min_side=150):
    """Panels of a comic page, split where a whole row/column is flat (a gutter)."""
    page = Image.open(path).convert("RGB").crop(PAGE_BOX)
    g = np.asarray(page.convert("L"), float)
    out = []
    for y0, y1 in _runs(g.std(axis=1) < 12, min_side):
        band = g[y0:y1]
        for x0, x1 in _runs(band.std(axis=0) < 12, min_side):
            out.append(page.crop((x0, y0, x1, y1)))
    return out


def shade(cut, height=520):
    im = cut.convert("RGBA")
    im = im.crop(im.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox())
    im = im.resize((max(1, int(im.width * height / im.height)), height), Image.LANCZOS)
    a = np.asarray(im, float)
    alpha = np.clip((a[..., 3:] / 255.0 - 0.25) / 0.5, 0, 1)
    lum = (a[..., :3] @ [0.299, 0.587, 0.114])[..., None] / 255.0
    rgb = BODY + (LIGHT - BODY) * np.clip(lum * 1.6, 0, 1)
    out = Image.fromarray(np.dstack([rgb, alpha * 255]).astype("uint8"), "RGBA")
    return out.filter(ImageFilter.GaussianBlur(0.4))


def _has_lettering(img, ocr):
    if ocr is None:
        return False
    rgb = Image.new("RGB", img.size, "white")
    rgb.paste(img, mask=img.getchannel("A"))
    result, _ = ocr(np.asarray(rgb))
    return any(len(t.strip()) >= 3 and float(conf) > 0.6 for _, t, conf in (result or []))


def candidates(slides):
    from rembg import new_session, remove
    from scipy import ndimage

    session = new_session("u2net_human_seg")
    for path in slides:
        slide = os.path.splitext(os.path.basename(path))[0]
        for k, panel in enumerate(panels(path)):
            cut = remove(panel, session=session)
            solid = np.asarray(cut)[..., 3] > 128
            cover = float(solid.mean())
            if not 0.06 <= cover <= 0.7:
                continue
            labels, n = ndimage.label(solid)
            main = float(ndimage.sum(solid, labels, range(1, n + 1)).max() / solid.sum())
            if main < 0.85:
                continue
            box = cut.getchannel("A").point(lambda v: 255 if v > 128 else 0).getbbox()
            fig = cut.crop(box)
            # A sliver or a strip is a prop or a fragment, not a character.
            if fig.height < 0.35 * panel.height or not 0.25 <= fig.width / fig.height <= 1.6:
                continue
            yield f"{slide}_{k}", fig, cover * main


def cut_issue(issue, slides, keep=6):
    try:
        from rapidocr_onnxruntime import RapidOCR
        ocr = RapidOCR()
    except Exception:
        ocr = None
    picked = []
    for name, fig, score in sorted(candidates(slides), key=lambda c: -c[2]):
        if _has_lettering(fig, ocr):
            continue
        picked.append((name, fig))
        if len(picked) == keep:
            break
    os.makedirs(CANDIDATES_DIR, exist_ok=True)
    written, shaded = [], []
    for name, fig in picked:
        img = shade(fig)
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=60, method=6)
        key = f"{int(issue):02d}_{name}"
        with open(os.path.join(CANDIDATES_DIR, f"{key}.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump({"uri": "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode(),
                       "w": img.width, "h": img.height}, f, separators=(",", ":"))
        written.append(key)
        shaded.append(img)
    if shaded:
        _sheet(issue, written, shaded)
    return written


def _sheet(issue, keys, images):
    """One PNG to review an issue's candidates by eye (on GitHub or anywhere)."""
    from PIL import ImageDraw

    cell = 260
    sheet = Image.new("RGBA", (cell * len(images), cell + 30), (11, 11, 13, 255))
    draw = ImageDraw.Draw(sheet)
    for i, (key, img) in enumerate(zip(keys, images)):
        thumb = img.copy()
        thumb.thumbnail((cell - 20, cell - 10))
        sheet.alpha_composite(thumb, (i * cell + 10, 28))
        draw.text((i * cell + 10, 8), key, fill=(255, 220, 0))
    sheet.convert("RGB").save(os.path.join(CANDIDATES_DIR, f"{int(issue):02d}_sheet.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", required=True, type=int)
    ap.add_argument("--slides", nargs="+", required=True)
    a = ap.parse_args()
    print("characters:", cut_issue(a.issue, a.slides) or "none usable")


if __name__ == "__main__":
    main()
