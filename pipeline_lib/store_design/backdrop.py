"""Shadow-character backdrop shared by the storefront and the comic landing pages.

Characters are cut out of the comics themselves (characters.py) and stored one per file in
chars/<key>.json as {"uri": data:image/webp..., "w", "h"}. They are embedded as data: URIs
because Gumroad's landing iframe only loads images from Gumroad's own hosts.

⚠ Every embedded image counts toward Gumroad's 25-images-per-page cap.

Keys: "cNN" = cut from issue NN's cover, "NN_slide_panel" = cut from issue NN's pages.
"""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CHARS_DIR = os.path.join(HERE, "chars")

# The strongest figures, used where an issue has none of its own.
POOL = ["c27", "51_3_3", "c45", "33_2_0", "c36", "32_2_1", "c01", "12_4_1", "47_3_1", "c35",
        "13_2_1", "29_2_2", "50_3_5", "c24", "45_2_3", "35_3_0", "c16", "c12", "53_3_4", "48_4_1"]
# (side, top as % of page height)
STORE_SLOTS = [("right", 2), ("left", 26), ("right", 50), ("left", 74)]
# Comic pages: the hero cover already fills the top right.
LANDING_SLOTS = [("left", 16), ("right", 44), ("left", 70)]


def chars():
    out = {}
    for path in glob.glob(os.path.join(CHARS_DIR, "*.json")):
        with open(path, encoding="utf-8") as f:
            out[os.path.basename(path)[:-5]] = json.load(f)
    return out


def pick(issue_no, count=3, available=None):
    """Deterministic per issue: the issue's own characters first, then the shared pool."""
    available = available if available is not None else chars()
    issue_no = int(issue_no)
    own = sorted(k for k in available if k.startswith(f"{issue_no:02d}_"))
    if f"c{issue_no:02d}" in available:
        own.append(f"c{issue_no:02d}")
    pool = [k for k in POOL if k in available]
    start = issue_no % max(len(pool), 1)
    rest = [pool[(start + i) % len(pool)] for i in range(len(pool))]
    return (own + [c for c in rest if c not in own])[:count]


def backdrop(names, scope="", slots=STORE_SLOTS, available=None):
    """(css, html). Put html first inside the page root and wrap the content in class="fg"."""
    available = available if available is not None else chars()
    names = [n for n in names if n in available]
    s = f"{scope} " if scope else ""
    css = [
        f"{scope or 'body'}{{position:relative}}",
        f"{s}.bd{{position:absolute;inset:0;overflow:hidden;pointer-events:none;z-index:0}}",
        f"{s}.bd i{{position:absolute;display:block;height:min(78vh,720px);background:no-repeat center bottom/contain;"
        "opacity:.68;-webkit-mask-image:linear-gradient(to bottom,#000 55%,transparent 98%);"
        "mask-image:linear-gradient(to bottom,#000 55%,transparent 98%)}",
        f"{s}.bd i.left{{left:-4vw}}{s}.bd i.right{{right:-4vw}}",
        f"{s}.bd::after{{content:\"\";position:absolute;inset:0;"
        "background-image:radial-gradient(rgba(255,255,255,.05) 1px,transparent 1.3px);background-size:4px 4px}",
        f"{s}.fg{{position:relative;z-index:1}}",
        f"@media (max-width:760px){{{s}.bd i{{opacity:.3;height:62vh}}}}",
    ]
    tags = []
    for i, name in enumerate(names):
        c = available[name]
        side, top = slots[i % len(slots)]
        css.append(f"{s}.bd .c{i}{{top:{top}%;aspect-ratio:{c['w']}/{c['h']};background-image:url({c['uri']})}}")
        tags.append(f'<i class="{side} c{i}"></i>')
    return "\n".join(css), '<div class="bd" aria-hidden="true">' + "".join(tags) + "</div>"
