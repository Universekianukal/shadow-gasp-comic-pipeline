"""Build the Shadow Gasp storefront: every issue in issue-number order.

Gumroad allows at most 25 distinct image URLs on a custom page (the logo is
one, and so is each embedded data: image) and only serves images from its own hosts, so the issues are split into
pages of PER_PAGE covers: the profile home page, then /case-files-2, -3, ...

build_pages(products) -> {slug: html}; slug "profile" is the store home page.
"""
import html
import re

from . import backdrop

ISSUE_RE = re.compile(r"#\s*0*(\d+)")
# 12 = rows of 4 on desktop, 3 on tablet, 2 on phone (20 read as crowded, 2026-09-17). Well inside
# the 25-image cap: logo + 4 backdrop characters + 12 covers.
PER_PAGE = 12
STORE_URL = "https://shadowgasp.gumroad.com/"
# Gumroad's own follow form. Custom pages cannot embed it (no data-gumroad hook for following),
# and their links may only leave for the store host, so every subscribe CTA links here.
SUBSCRIBE_URL = STORE_URL + "subscribe"
PAGE_CHARS = [["c27", "51_3_3", "c45", "33_2_0"], ["c36", "32_2_1", "c01", "12_4_1"],
              ["47_3_1", "c24", "53_3_4", "35_3_0"], ["c35", "13_2_1", "29_2_2", "50_3_5"],
              ["45_2_3", "46_4_4", "c12", "48_4_1"]]
LOGO = "https://public-files.gumroad.com/cl21bznqqeyqx5d90dwf3rix9uva"
# Fallback only: the live text comes from the Gumroad profile bio (profile_text), so an edit there
# reaches the store at the next sync. The hard-coded copy once said 25–50 pages while the profile
# said 40–100.
DEFAULT_BIO = "\n".join([
    "Some cases were never solved. Some were never fully told.",
    "Shadow Gasp brings history's darkest true crimes and unexplained mysteries back to life as noir "
    "comics: heists, disappearances, ghost ships and cold cases.",
    "🔎 Real cases, researched from the record",
    "📖 40–100 illustrated pages per issue",
    "⚡ Read tonight, on any device",
    "Pick a case. Turn off the lights.",
])


def profile_text(bio):
    """Profile bio -> {"paras": [...], "promises": [(icon, text)], "closer": str}.

    Lines that start with an emoji are the promises; the last plain line after them is the
    sign-off; plain lines before them are the intro paragraphs.
    """
    paras, promises, closer = [], [], ""
    for line in (bio or DEFAULT_BIO).splitlines():
        line = re.sub(r"\s+\.$", ".", line.strip())
        if not line:
            continue
        if not line[0].isalnum() and " " in line:
            icon, text = line.split(" ", 1)
            promises.append((icon, text.strip().rstrip(".")))
        elif promises:
            closer = line
        else:
            paras.append(line)
    return {"paras": paras, "promises": promises, "closer": closer or "Pick a case. Turn off the lights."}


CSS = """
@import url("https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Montserrat:wght@400;600;800&display=swap");
.sg{--ink:#0b0b0d;--panel:#141418;--line:#2a2a31;--paper:#f1ece4;--muted:#a19c95;--red:#d0342c;--red-deep:#8e1d18;
  background:radial-gradient(1200px 600px at 70% -10%,#2a0f0e 0%,rgba(11,11,13,0) 60%),var(--ink);
  color:var(--paper);font-family:Montserrat,"Segoe UI",Helvetica,Arial,sans-serif;line-height:1.55;
  margin:0;padding:0 clamp(16px,4vw,48px) 64px;min-height:100vh}
.sg *{box-sizing:border-box}
.sg a{color:inherit;text-decoration:none}
.sg .wrap{max-width:1180px;margin:0 auto}
.sg .display{font-family:"Bebas Neue",Impact,"Arial Narrow",sans-serif;font-weight:400;letter-spacing:.02em;line-height:.95;margin:0}
.sg .top{display:flex;align-items:center;gap:14px;padding:28px 0 18px;border-bottom:1px solid var(--line)}
.sg .top img{width:52px;height:52px;border-radius:50%;border:2px solid var(--red)}
.sg .top .display{font-size:34px}
.sg .top small{display:block;color:var(--muted);font-size:11px;letter-spacing:.24em;text-transform:uppercase}
.sg .top .sub{margin-left:auto;order:3;background:var(--red);color:#fff;font-size:12px;font-weight:800;letter-spacing:.18em;
  text-transform:uppercase;padding:10px 16px;border-radius:2px;box-shadow:4px 4px 0 var(--red-deep)}
.sg .top .sub:hover{transform:translate(-1px,-1px);box-shadow:5px 5px 0 var(--red-deep)}
.sg .subscribe{display:flex;flex-wrap:wrap;gap:18px 32px;align-items:center;justify-content:space-between;margin:28px 0 0;
  padding:26px 28px;border:1px solid var(--line);background:linear-gradient(90deg,rgba(208,52,44,.18),rgba(20,20,24,.6))}
.sg .subscribe .display{font-size:clamp(30px,4vw,42px)}
.sg .subscribe p{margin:6px 0 0;color:#d9d3ca}
.sg .foot .btn{margin-top:22px}
.sg .tape{order:2;margin-left:18px;background:var(--red);color:#fff;font-size:11px;font-weight:800;letter-spacing:.2em;
  text-transform:uppercase;padding:6px 12px;transform:rotate(-2deg)}
.sg .hero{display:grid;grid-template-columns:minmax(0,340px) 1fr;gap:clamp(24px,5vw,64px);align-items:center;padding:clamp(32px,6vw,72px) 0}
.sg .hero-cover{position:relative;aspect-ratio:368/564;overflow:hidden;border-radius:4px;
  box-shadow:0 30px 80px rgba(0,0,0,.7),0 0 0 1px var(--line);transform:rotate(-2deg);transition:transform .4s ease}
.sg .hero-cover:hover{transform:rotate(0) scale(1.02)}
.sg .kicker{color:var(--red);font-weight:800;font-size:12px;letter-spacing:.28em;text-transform:uppercase;margin:0 0 14px}
.sg .hero h1{font-size:clamp(56px,9vw,120px)}
.sg .hero .no{color:var(--muted);font-size:clamp(20px,2.4vw,28px);display:block;margin-bottom:6px}
.sg .hero p.tag{font-size:clamp(15px,1.6vw,18px);color:#d9d3ca;max-width:34em;margin:20px 0 28px}
.sg .btn{display:inline-flex;align-items:center;gap:12px;background:var(--red);color:#fff;font-weight:800;
  letter-spacing:.12em;text-transform:uppercase;font-size:14px;padding:15px 26px;border-radius:2px;
  box-shadow:6px 6px 0 var(--red-deep);transition:transform .15s ease,box-shadow .15s ease}
.sg .btn:hover{transform:translate(-2px,-2px);box-shadow:8px 8px 0 var(--red-deep)}
.sg .btn.ghost{background:transparent;border:1px solid var(--paper);box-shadow:none}
.sg .btn.ghost:hover{background:var(--paper);color:var(--ink)}
.sg .brief{display:grid;grid-template-columns:1.3fr 1fr;gap:clamp(20px,4vw,48px);padding:32px 0;
  border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.sg .brief p{margin:0 0 10px;color:#d9d3ca}
.sg .brief p:first-child{font-size:20px;color:var(--paper);font-weight:600}
.sg .brief ul{list-style:none;margin:0;padding:0;display:grid;gap:10px;align-content:center}
.sg .brief li{display:flex;gap:12px;align-items:center;font-weight:600}
.sg .brief li span{width:34px;height:34px;display:grid;place-items:center;border:1px solid var(--line);border-radius:50%}
.sg .free{display:flex;flex-wrap:wrap;gap:16px 28px;align-items:center;justify-content:space-between;margin:40px 0 0;
  padding:22px 26px;border:1px dashed var(--red);background:rgba(208,52,44,.07)}
.sg .free .display{font-size:32px}
.sg .free p{margin:4px 0 0;color:var(--muted)}
.sg .files-head{display:flex;align-items:baseline;justify-content:space-between;gap:16px;margin:64px 0 22px;flex-wrap:wrap}
.sg .files-head .display{font-size:clamp(44px,6vw,72px)}
.sg .files-head span{color:var(--muted);font-size:13px;letter-spacing:.2em;text-transform:uppercase}
.sg .grid{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;justify-content:center;gap:36px 24px}
.sg .grid>li{flex:0 0 calc((100% - 72px) / 4);min-width:0}
@media (max-width:980px){.sg .grid>li{flex-basis:calc((100% - 48px) / 3)}}
.sg .card{display:block;opacity:0;animation:sg-in .6s ease forwards}
.sg .card .cv{position:relative;aspect-ratio:368/564;overflow:hidden;border-radius:3px;background-color:#000;
  box-shadow:0 12px 30px rgba(0,0,0,.55),0 0 0 1px var(--line);transition:transform .25s ease,box-shadow .25s ease}
.sg .card .cv img,.sg .hero-cover img{display:block;width:163.05%;max-width:none;margin:-4.9% 0 0 -31.52%}
.sg .card:hover .cv{transform:translateY(-6px) rotate(-1deg);box-shadow:0 22px 40px rgba(0,0,0,.7),0 0 0 2px var(--red)}
.sg .card .case{display:block;margin:14px 0 4px;color:var(--red);font-size:11px;font-weight:800;letter-spacing:.24em;text-transform:uppercase}
.sg .card h3{font-family:"Bebas Neue",Impact,sans-serif;font-weight:400;font-size:24px;line-height:1;letter-spacing:.02em;margin:0 0 6px}
.sg .card .price{font-size:13px;font-weight:600;color:var(--muted);letter-spacing:.08em}
.sg .card:hover h3{color:#fff;text-decoration:underline;text-decoration-color:var(--red);text-underline-offset:4px}
.sg .pager{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin-top:48px}
.sg .pager a,.sg .pager b{min-width:46px;text-align:center;padding:10px 14px;border:1px solid var(--line);font-weight:800;font-size:13px;letter-spacing:.14em;text-transform:uppercase}
.sg .pager b{background:var(--red);border-color:var(--red);color:#fff}
.sg .pager a:hover{border-color:var(--paper)}
.sg .foot{text-align:center;margin-top:80px;padding-top:40px;border-top:1px solid var(--line)}
.sg .foot .display{font-size:clamp(40px,7vw,80px)}
.sg .foot p{color:var(--muted);margin:10px 0 0}
.sg .foot p.display{color:var(--paper)}
@keyframes sg-in{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@media (max-width:720px){
  .sg .hero{grid-template-columns:1fr;text-align:center}
  .sg .hero-cover{max-width:240px;margin:0 auto}
  .sg .hero p.tag{margin-left:auto;margin-right:auto}
  .sg .brief{grid-template-columns:1fr}
  .sg .tape{display:none}
  .sg .grid{gap:24px 14px}
  .sg .grid>li{flex-basis:calc((100% - 14px) / 2)}
  .sg .card h3{font-size:20px}
}
@media (prefers-reduced-motion:reduce){.sg .card{animation:none;opacity:1}.sg *{transition:none!important}}
"""


def issue_no(name):
    m = ISSUE_RE.search(name or "")
    return int(m.group(1)) if m else -1


def title_of(name):
    return name.split(":", 1)[1].strip() if ":" in name else name


def tagline(desc, limit=200):
    text = re.sub(r"<[^>]+>", " ", desc or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    out = ""
    for sentence in re.findall(r".+?(?:[.!?](?=\s|$)|$)", text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if out and len(out) + 1 + len(sentence) > limit:
            break
        out = f"{out} {sentence}".strip()
    return out if len(out) <= limit else out[: limit - 1].rsplit(" ", 1)[0] + "…"


def page_slug(k):
    return "profile" if k == 1 else f"case-files-{k}"


def page_url(k):
    return STORE_URL if k == 1 else STORE_URL + page_slug(k)


def card(p, i):
    e = html.escape
    return (
        f'<li><a class="card" href="{e(p["short_url"])}" style="animation-delay:{min(i, 30) * 40}ms">'
        f'<div class="cv"><img src="{e(p["thumbnail_url"])}" alt=""></div>'
        f'<span class="case">Case No. {issue_no(p["name"])}</span><h3>{e(title_of(p["name"]))}</h3>'
        f'<span class="price">{e(p["formatted_price"])}</span></a></li>'
    )


def pager(k, pages):
    if pages == 1:
        return ""
    links = []
    if k > 1:
        links.append(f'<a href="{page_url(k - 1)}">← Newer</a>')
    for j in range(1, pages + 1):
        links.append(f"<b>{j}</b>" if j == k else f'<a href="{page_url(j)}">{j}</a>')
    if k < pages:
        links.append(f'<a href="{page_url(k + 1)}">Older →</a>')
    return '<nav class="pager">' + "".join(links) + "</nav>"


def header(total, k):
    home = "" if k == 1 else f' href="{STORE_URL}"'
    return (
        f'<header class="top"><a{home}><img src="{LOGO}" alt="Shadow Gasp"></a>'
        f'<a{home}><h2 class="display">Shadow Gasp</h2><small>True crime · Documentary comics</small></a>'
        f'<span class="tape">{total} case files open</span>'
        f'<a class="sub" href="{SUBSCRIBE_URL}">Subscribe</a></header>'
    )


def intro(live, profile):
    e = html.escape
    new = live[0]
    first = next((p for p in live if issue_no(p["name"]) == 1), None)
    parts = [
        '<section class="hero">'
        f'<a class="hero-cover" href="{e(new["short_url"])}"><img src="{e(new["thumbnail_url"])}" alt=""></a>'
        '<div><p class="kicker">New case file</p>'
        f'<h1 class="display"><span class="no">Issue No. {issue_no(new["name"])}</span>{e(title_of(new["name"]))}</h1>'
        f'<p class="tag">{e(tagline(new.get("description")))}</p>'
        # Straight to checkout: /l/<permalink>?wanted=true is Gumroad's own redirect to the
        # payment page (pay-what-you-want products don't redirect, so #1 keeps its product link).
        f'<a class="btn" href="{e(new["short_url"])}?wanted=true">Get the comic — {e(new["formatted_price"])}</a></div></section>',
        '<section class="brief"><div>'
        + "".join(f"<p>{e(t)}</p>" for t in profile["paras"])
        + "</div><ul>"
        + "".join(f"<li><span>{e(i)}</span>{e(t)}</li>" for i, t in profile["promises"])
        + "</ul></section>",
    ]
    if first:
        parts.append(
            '<section class="free"><div>'
            f'<h2 class="display">Start with case No. 1 — {e(title_of(first["name"]))}</h2>'
            f"<p>{e(tagline(first.get('description'), 170))}</p></div>"
            f'<a class="btn ghost" href="{e(first["short_url"])}">Pay what you want</a></section>'
        )
    parts.append(
        '<section class="subscribe"><div>'
        '<h2 class="display">Never miss a case file</h2>'
        "<p>Subscribe and every new case lands in your inbox the day it opens.</p></div>"
        f'<a class="btn" href="{SUBSCRIBE_URL}">Subscribe free</a></section>'
    )
    return parts


def page(live, k, pages, profile):
    chunk = live[(k - 1) * PER_PAGE : k * PER_PAGE]
    title = "The Case Files" if k == 1 else f"Case Files · Page {k}"
    bd_css, bd_html = backdrop.backdrop(PAGE_CHARS[(k - 1) % len(PAGE_CHARS)], ".sg")
    parts = [f"<style>{CSS}\n{bd_css}</style>",'<div class="sg">', bd_html, '<div class="wrap fg">', header(len(live), k)]
    if k == 1:
        parts += intro(live, profile)
    parts += [
        f'<div class="files-head"><h2 class="display">{title}</h2>'
        f"<span>No. {issue_no(chunk[0]['name'])} → No. {issue_no(chunk[-1]['name'])}</span></div>",
        '<ul class="grid">' + "".join(card(p, i) for i, p in enumerate(chunk)) + "</ul>",
        pager(k, pages),
        f'<footer class="foot"><p class="display">{html.escape(profile["closer"])}</p>'
        "<p>New case files are added as they are researched.</p>"
        f'<a class="btn" href="{SUBSCRIBE_URL}">Subscribe for new cases</a></footer>',
        "</div></div>",
    ]
    return "\n".join(parts)


def live_issues(products):
    live = [p for p in products if p.get("published") and not p.get("deleted") and issue_no(p.get("name")) > 0]
    return sorted(live, key=lambda p: issue_no(p["name"]), reverse=True)


def build_pages(products, bio=None):
    live = live_issues(products)
    pages = -(-len(live) // PER_PAGE)
    profile = profile_text(bio)
    return {page_slug(k): page(live, k, pages, profile) for k in range(1, pages + 1)}
