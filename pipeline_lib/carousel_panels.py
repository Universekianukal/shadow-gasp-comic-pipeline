"""Panel-story carousel (v3): the comic told panel by panel, the way a comic seller cuts a carousel.

    python pipeline_lib/carousel_panels.py <comic.pdf> <out_dir> --issue 51 --title "..." --hook "..."

Why: v2 pasted whole pages onto the slides, and a full page of six to eight panels on a phone is
unreadable -- nobody follows the story, nobody swipes on (owner, 2026-09-17).

Slides (1080x1350), only real art from the first ~62% of the book (never the ending):
  1     hook         the splash art full-bleed, headline in Bebas Neue (the storefront's display face)
  2..6  story        ONE panel per slide, in reading order, its narration re-lettered large;
                     a tall splash fills the whole slide (boxed, it looked empty -- owner)
  7     cliffhanger  a later panel, darkened, stamped CASE FILE CONTINUES...
  8     CTA          the cover large over its own art + "COMMENT COMIC" (no page count)
Panels come from the PDF itself: every panel is a placed image, so its box is exact.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageStat

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import carousel_from_pdf as v2  # noqa: E402  (picker, hook art, text/art scoring, CTA slide)
import gen_carousel as g  # noqa: E402

W, H = g.W, g.H
RED, CREAM, INK = g.RED, g.CREAM, (11, 11, 13)
STORY_PANELS = 5
FONT_DIRS = [os.path.join(os.path.dirname(HERE), "fonts"), os.path.join(HERE, "fonts")]


def bebas(size):
    for d in FONT_DIRS:
        p = os.path.join(d, "BebasNeue-Regular.ttf")
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return g.font(size)


# ---------------------------------------------------------------- picking
def panels(doc, first, last, skip_pages):
    """Every sizeable panel in pages first..last (1-based) as {page, box, score}."""
    import fitz
    out = []
    for pno in range(first, last + 1):
        page = doc[pno - 1]
        if pno in skip_pages or v2.text_share(page) > 0.22:
            continue
        pw, ph = page.rect.width, page.rect.height
        for info in page.get_image_info():
            x0, y0, x1, y1 = info["bbox"]
            w, h = x1 - x0, y1 - y0
            share = (w * h) / (pw * ph)
            if share < 0.12 or not 0.5 <= w / h <= 2.6:
                continue
            pix = page.get_pixmap(clip=fitz.Rect(x0, y0, x1, y1), dpi=40)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            out.append({"page": pno, "box": (x0, y0, x1, y1), "score": v2.art_score(img) * share ** 0.5})
    return out


STORY_SHARE = 0.7   # story panels come from the first 70% of the preview window


def _narration(doc, c):
    import fitz
    blocks = [" ".join(bl[4].split()) for bl in doc[c["page"] - 1].get_text("blocks", clip=fitz.Rect(*c["box"]))]
    return _drop_sfx_runs(" ".join(t for t in blocks if len(t) > 25 and not t.isdigit() and not _is_sfx(t)))


STORY_PROMPT = """You are cutting an Instagram carousel for a true-crime documentary comic, "{title}".
The carousel opens with this hook: "{hook}"

Below are candidate panels from the FIRST PART of the comic, in reading order, with the narration
printed in each. The reader sees ONLY these slides, one panel per slide, with its narration.

Choose exactly {n} panels for the story slides and 1 panel for a cliffhanger slide so that a stranger
can follow a clear mini-story and ends up wanting the full comic:
- in reading order (ascending ids), telling setup -> incident -> the mystery deepening -> a twist;
- every slide must make sense given the hook and the slides before it: never pick a panel whose
  narration depends on a person, event or object that the chosen slides have not introduced;
- prefer panels with concrete narration (who, what, when); avoid panels with empty narration;
- the cliffhanger has a higher id than all story panels and raises a question it does not answer;
- never reveal how the case ends or who did it.

Candidates:
{items}

Return JSON: {{"story": [ids], "cliffhanger": id, "why": "one sentence"}}"""


def pick_panels_llm(doc, title, hook):
    """Story chosen by a language model from the narration, so the slides connect (owner,
    2026-09-17). Falls back to the art-only picker when no model is configured or the answer is
    unusable. Among panels on one page the model sees each; art quality breaks nothing here
    because every candidate already passed the size/art filters."""
    hook_page, story, cliff = pick_panels(doc)
    provider = os.environ.get("COMIC_LLM_PROVIDER", "")
    if not provider or provider == "mock":
        return hook_page, story, cliff, "art picker (no model configured)"
    base = v2.pick(doc)
    first, last = base["window"]
    cands = sorted(panels(doc, first, last, {base["hook"]}), key=lambda c: (c["page"], c["box"][1], c["box"][0]))
    for c in cands:
        c["text"] = _narration(doc, c)
    cands = [c for c in cands if c["text"]][:70]
    if len(cands) < STORY_PANELS + 1:
        return hook_page, story, cliff, "art picker (too few captioned panels)"
    items = chr(10).join(f'{i}. (page {c["page"]}) {c["text"][:300]}' for i, c in enumerate(cands))
    try:
        import llm
        ans = llm.LLM(provider=provider, model=os.environ.get("COMIC_LLM_MODEL") or None).json(
            STORY_PROMPT.format(title=title, hook=hook, n=STORY_PANELS, items=items), max_tokens=3000)
        ids = [int(x) for x in ans["story"]]
        cid = int(ans["cliffhanger"])
        ok = (len(ids) == STORY_PANELS and ids == sorted(set(ids)) and all(0 <= i < len(cands) for i in ids)
              and ids[-1] < cid < len(cands))
        if not ok:
            raise ValueError(f"unusable answer {ans}")
        return hook_page, [cands[i] for i in ids], cands[cid], "story model: " + str(ans.get("why", ""))[:200]
    except Exception as e:  # noqa: BLE001 - a carousel must still build
        print(f"WARNING: story model failed ({e}) -- using the art picker", flush=True)
        return hook_page, story, cliff, "art picker (model failed)"


def pick_panels(doc):
    """Hook as v2; story = the best panel from each of STORY_PANELS equal slices of the EARLY window,
    so the carousel follows the book from its opening (owner, 2026-09-17: #1 skipped straight to
    the suspects); cliffhanger = the best panel after the last story panel, still inside the window."""
    base = v2.pick(doc)
    first, last = base["window"]
    cands = panels(doc, first, last, {base["hook"]})
    if not cands:
        return base["hook"], [], None
    story_end = first + max(STORY_PANELS, int((last - first) * STORY_SHARE))
    early = [c for c in cands if c["page"] <= story_end]
    story = []
    span = (story_end - first + 1) / STORY_PANELS
    for k in range(STORY_PANELS):
        lo, hi = first + k * span, first + (k + 1) * span
        bucket = [c for c in early if lo <= c["page"] < hi and all(c["page"] != s["page"] for s in story)]
        if bucket:
            story.append(max(bucket, key=lambda c: c["score"]))
    # a bucket with no art: fill from the remaining early panels, still one per page
    for c in sorted(early, key=lambda c: -c["score"]):
        if len(story) >= STORY_PANELS:
            break
        if all(c["page"] != s["page"] for s in story):
            story.append(c)
    story.sort(key=lambda c: (c["page"], c["box"][1], c["box"][0]))
    after = [c for c in cands if story and c["page"] > story[-1]["page"]]
    rest = [c for c in cands if all(c["page"] != s["page"] for s in story)]
    pool = after or rest
    cliff = max(pool, key=lambda c: c["score"]) if pool else None
    return base["hook"], story, cliff


def _is_sfx(block):
    """Lettered sound effects ("WHOOSH WHOOSH WHOOSH") are art, not narration."""
    words = block.split()
    return len(words) >= 3 and len(set(w.strip(".,!?").upper() for w in words)) <= 2


def _drop_sfx_runs(text):
    out, words = [], text.split()
    i = 0
    while i < len(words):
        j = i
        while j + 1 < len(words) and words[j + 1].upper() == words[i].upper():
            j += 1
        if j - i < 2:                       # a word said 3+ times in a row is a sound effect
            out.extend(words[i:j + 1])
        i = j + 1
    return " ".join(out)


def render_panel(doc, c, width=1000):
    """(image, narration) -- the panel as printed, and the lettering inside it as plain text."""
    import fitz
    x0, y0, x1, y1 = c["box"]
    rect = fitz.Rect(x0, y0, x1, y1)
    dpi = int(72 * width / (x1 - x0)) + 1
    pix = doc[c["page"] - 1].get_pixmap(clip=rect, dpi=min(dpi, 600))
    # Narration boxes only: page numbers and short act labels ("ACCIDENT") are text too.
    blocks = [" ".join(bl[4].split()) for bl in doc[c["page"] - 1].get_text("blocks", clip=rect)]
    text = " ".join(t for t in blocks if len(t) > 25 and not t.isdigit() and not _is_sfx(t))
    text = _drop_sfx_runs(text)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples), text


def raw_art(doc, c):
    """The panel's own embedded picture -- clean art, no lettering or page margin -- or None."""
    import io
    page = doc[c["page"] - 1]
    try:
        for info in page.get_image_info(xrefs=True):
            if info.get("xref") and all(abs(a - b) < 2 for a, b in zip(info["bbox"], c["box"])):
                im = Image.open(io.BytesIO(doc.extract_image(info["xref"])["image"])).convert("RGB")
                if im.width >= 600:
                    return im
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- slides
def chrome(img, idx, total, swipe=True):
    d = ImageDraw.Draw(img)
    f = g.font(24, "Bold")
    tw = d.textlength("SHADOW GASP", font=f)
    d.rectangle((48, 48, 48 + tw + 32, 92), fill=RED)
    d.text((64, 57), "SHADOW GASP", font=f, fill=(255, 255, 255))
    # progress bar: one segment per slide, this one red
    gap, x0, x1, y = 8, 48, W - 48, H - 40
    seg = (x1 - x0 - gap * (total - 1)) / total
    for i in range(total):
        sx = x0 + i * (seg + gap)
        d.rectangle((sx, y, sx + seg, y + 6), fill=RED if i == idx - 1 else (70, 68, 66))
    if swipe:
        # Bebas Neue has no arrow glyph, so the arrow is drawn.
        sf = bebas(40)
        ax = W - 48 - 34
        d.polygon([(ax, H - 92), (ax + 34, H - 76), (ax, H - 60)], fill=RED)
        d.text((ax - 16 - d.textlength("SWIPE", font=sf), H - 97), "SWIPE", font=sf, fill=CREAM)


def backdrop(img, dim=0.22):
    return ImageEnhance.Brightness(g.cover_crop(img, W, H, 0.5).filter(ImageFilter.GaussianBlur(36))).enhance(dim)


def slide_hook(art, headline, subline, issue, total):
    base = g.cover_crop(art.convert("RGB"), W, H, 0.30)
    fade = Image.new("L", (1, H))
    for y in range(H):
        t = max(0.0, (y - H * 0.36) / (H * 0.64))
        fade.putpixel((0, y), int(255 * min(1.0, t * 1.3)))
    img = Image.composite(Image.new("RGB", (W, H), INK), base, fade.resize((W, H)))
    d = ImageDraw.Draw(img)
    text = headline.upper()
    size = 150
    while size > 80:
        f = bebas(size)
        lines = g.wrap(d, text, f, W - 110)
        if len(lines) <= 3:
            break
        size -= 6
    sf = g.font(38, "Bold")
    slines = g.wrap(d, subline, sf, W - 120)[:3] if subline else []
    block = len(lines) * size * 0.95 + (26 + len(slines) * 50 if slines else 0)
    y = H - 190 - block
    d.rectangle((60, y - 34, 180, y - 24), fill=RED)
    for ln in lines:
        d.text((58, y), ln, font=f, fill=(255, 255, 255))
        y += size * 0.95
    if slines:
        y += 26
        for ln in slines:
            d.text((60, y), ln, font=sf, fill=CREAM)
            y += 50
    d.text((60, H - 104), f"TRUE CRIME COMIC  ·  ISSUE #{issue}", font=bebas(40), fill=CREAM)
    chrome(img, 1, total)
    return img


def narration_block(d, text, max_w, max_h, start=50):
    """The panel's own lettering, re-set large enough to read on a phone."""
    if not text:
        return None, [], 0
    text = text.upper()
    size = start
    while size >= 30:
        f = g.font(size, "ExtraBold")
        lines = g.wrap(d, text, f, max_w)
        if len(lines) * size * 1.25 <= max_h:
            return f, lines, size
        size -= 2
    return None, [], 0


def slide_panel(panel, narration, idx, total):
    img = backdrop(panel)
    d = ImageDraw.Draw(img)
    top, bottom = 118, H - 130
    f, lines, size = narration_block(d, narration, W - 140, 330)
    text_h = int(len(lines) * size * 1.25) + (40 if lines else 0)
    fg = g.contain(panel, W - 80, bottom - top - text_h)
    x = (W - fg.width) // 2
    y = top + (bottom - top - text_h - fg.height) // 2
    d.rectangle((x - 5, y - 5, x + fg.width + 4, y + fg.height + 4), fill=CREAM)
    img.paste(fg, (x, y))
    ty = y + fg.height + 40
    if lines:
        d.rectangle((70, ty + 6, 80, ty + len(lines) * size * 1.25 - 10), fill=RED)
        for ln in lines:
            d.text((100, ty), ln, font=f, fill=(255, 255, 255))
            ty += size * 1.25
    chrome(img, idx, total)
    return img


def trim_white(img, thresh=232):
    """Cut near-white margins (some splash art carries a white bleed strip on one side)."""
    import numpy as np
    a = np.asarray(img.convert("L"), dtype=float)
    cols, rows = a.mean(axis=0), a.mean(axis=1)
    x0, x1, y0, y1 = 0, len(cols), 0, len(rows)
    while x0 < x1 - 10 and cols[x0] > thresh:
        x0 += 1
    while x1 > x0 + 10 and cols[x1 - 1] > thresh:
        x1 -= 1
    while y0 < y1 - 10 and rows[y0] > thresh:
        y0 += 1
    while y1 > y0 + 10 and rows[y1 - 1] > thresh:
        y1 -= 1
    return img.crop((x0, y0, x1, y1))


def slide_splash(panel, narration, idx, total):
    """A tall panel (a splash) fills the whole slide, like the hook: boxed, it left empty strips.
    `panel` should be the clean embedded art -- the printed lettering is re-set on the slide.
    The text goes over the QUIETER end of the picture, so the subject is never covered."""
    base = g.cover_crop(trim_white(panel.convert("RGB")), W, H, 0.35)
    d0 = ImageDraw.Draw(base)
    f, lines, size = narration_block(d0, narration, W - 160, 300, start=44)
    text_h = int(len(lines) * size * 1.25)
    band = int(H * 0.4)
    # Edge density, not tonal range: a bright empty shape (an envelope on black) is not "busy".
    def detail(im):
        return ImageStat.Stat(im.convert("L").filter(ImageFilter.FIND_EDGES)).mean[0]
    at_top = detail(base.crop((0, H - band, W, H))) > detail(base.crop((0, 0, W, band))) * 1.5
    fade = Image.new("L", (1, H))
    reach = text_h + 260
    for y in range(H):
        dist = y if at_top else H - y           # distance from the text's edge of the slide
        t = max(0.0, 1 - (dist - 110) / reach) if dist > 110 else 1.0
        fade.putpixel((0, y), int(235 * min(1.0, t * 1.4)))
    img = Image.composite(Image.new("RGB", (W, H), INK), base, fade.resize((W, H)))
    d = ImageDraw.Draw(img)
    ty = 130 if at_top else H - 150 - text_h
    if lines:
        d.rectangle((70, ty + 6, 80, ty + text_h - 10), fill=RED)
        for ln in lines:
            d.text((100, ty), ln, font=f, fill=(255, 255, 255))
            ty += size * 1.25
    chrome(img, idx, total)
    return img


def slide_story(doc, c, idx, total):
    panel, narration = render_panel(doc, c)
    if panel.width / panel.height < 0.9:
        return slide_splash(raw_art(doc, c) or panel, narration, idx, total)
    return slide_panel(panel, narration, idx, total)


def slide_cliff(panel, idx, total):
    """The next beat, withheld: the panel fills the slide, darkened, under a red stamp."""
    base = ImageEnhance.Brightness(g.cover_crop(trim_white(panel.convert("RGB")), W, H, 0.4)).enhance(0.42)
    vignette = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vignette)
    for i in range(0, 260, 4):                     # dark edges pull the eye to the stamp
        vd.rectangle((i, i, W - i, H - i), outline=int(200 * (1 - i / 260)), width=4)
    img = Image.composite(Image.new("RGB", (W, H), INK), base, vignette.filter(ImageFilter.GaussianBlur(40)))
    stamp = Image.new("RGBA", (940, 280), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stamp)
    sd.rectangle((0, 0, 939, 279), fill=(11, 11, 13, 150))
    sd.rectangle((8, 8, 931, 271), outline=RED, width=10)
    sf = bebas(124)
    label = "CASE FILE CONTINUES…"
    sd.text(((940 - sd.textlength(label, font=sf)) / 2, 62), label, font=sf, fill=RED)
    stamp = stamp.rotate(-6, expand=True, resample=Image.BICUBIC)
    img.paste(stamp, ((W - stamp.width) // 2, H // 2 - stamp.height // 2 - 20), stamp)
    d = ImageDraw.Draw(img)
    q = "WHAT HAPPENED NEXT IS IN THE FULL COMIC."
    qf = bebas(64)
    d.text(((W - d.textlength(q, font=qf)) / 2, H - 230), q, font=qf, fill=(255, 255, 255))
    chrome(img, idx, total)
    return img


def slide_cta(cover, title, issue, total, free):
    """Last slide: the cover big, the ask bigger. The cover art fills the ground (v2 blurred it
    into an empty dark card -- owner, 2026-09-17). No page count."""
    cover = cover.convert("RGB")
    # centre crop of the art only (focus below the masthead) so the printed title doesn't ghost behind
    # Bright enough to read as art (0.26 was "too dark", owner); dark only behind the text.
    art = cover.crop((0, int(cover.height * 0.2), cover.width, int(cover.height * 0.76)))  # no masthead/title
    img = ImageEnhance.Brightness(g.cover_crop(art, W, H, 0.5).filter(ImageFilter.GaussianBlur(4))).enhance(0.62)
    fade = Image.new("L", (1, H))
    for y in range(H):
        fade.putpixel((0, y), int(215 * max(0.0, min(1.0, (y - H * 0.55) / (H * 0.12)))))
    img = Image.composite(Image.new("RGB", (W, H), INK), img, fade.resize((W, H)))
    # the cover itself, tilted a touch with a drop shadow, like the storefront hero
    c = g.contain(cover, 500, 740)
    card = Image.new("RGBA", (c.width + 12, c.height + 12), CREAM + (255,))
    card.paste(c, (6, 6))
    card = card.rotate(-4, expand=True, resample=Image.BICUBIC)
    shadow = Image.new("RGBA", (card.width + 80, card.height + 80), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 200), (40, 50, 40 + card.width, 50 + card.height), card.split()[3])
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    cx = (W - card.width) // 2
    img.paste(shadow, (cx - 40, 90), shadow)
    img.paste(card, (cx, 100), card)
    d = ImageDraw.Draw(img)
    y = 100 + card.height + 20

    def center(text, fnt, fill, yy):
        d.text(((W - d.textlength(text, font=fnt)) / 2, yy), text, font=fnt, fill=fill)
    center("WANT THE FULL STORY?", bebas(58), CREAM, y)
    y += 64
    big = bebas(190)
    w1, w2 = d.textlength("COMMENT ", font=big), d.textlength("COMIC", font=big)
    x = (W - w1 - w2) / 2
    d.text((x, y), "COMMENT ", font=big, fill=(255, 255, 255))
    d.text((x + w1, y), "COMIC", font=big, fill=RED)
    y += 188
    center("Your first case is on us." if free else "and we'll DM you the link.", g.font(40, "Bold"),
           RED if free else CREAM, y)
    y += 64
    center(f"ISSUE #{issue}  ·  {title}", bebas(40), (170, 165, 155), y)
    chrome(img, total, total, swipe=False)
    return img


def build_slides(pdf_path, issue, title, hook, out_dir):
    doc = v2._open(pdf_path)
    hook_page, story, cliff, how = pick_panels_llm(doc, title, hook)
    print(f"#{issue} picks: {how}", flush=True)
    total = 1 + len(story) + (1 if cliff else 0) + 1
    head, sub = v2.headline_and_sub(hook or title)
    slides = [slide_hook(v2.hook_art(doc, hook_page), head, sub, issue, total)]
    slides += [slide_story(doc, c, k + 2, total) for k, c in enumerate(story)]
    if cliff:
        art = raw_art(doc, cliff) or render_panel(doc, cliff)[0]
        slides.append(slide_cliff(art, len(slides) + 1, total))
    slides.append(slide_cta(v2.render(doc, 0, 170), title, issue, total, int(issue) == 1))
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for k, s in enumerate(slides, 1):
        p = os.path.join(out_dir, f"{k}.jpg")
        s.save(p, quality=90)
        paths.append(p)
    picks = {"how": how, "hook": hook_page, "story": [(c["page"], [round(v) for v in c["box"]]) for c in story],
             "cliff": (cliff["page"], [round(v) for v in cliff["box"]]) if cliff else None}
    return paths, picks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("out_dir")
    ap.add_argument("--issue", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--hook", default="")
    a = ap.parse_args()
    paths, picks = build_slides(a.pdf, a.issue, a.title, a.hook, a.out_dir)
    print(len(paths), "slides", picks)


if __name__ == "__main__":
    main()
