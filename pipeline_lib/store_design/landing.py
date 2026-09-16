"""Shadow Gasp comic landing page in the storefront's noir design (live since 2026-09-16).

build_html(case, related) -> str
  case    = {issue_no, title, hook, badge, what: [str], inside: [str],
             subject, thumbnail_url, price}
  related = [{issue_no, title, price, url, thumbnail_url}]  (up to 4)

Gumroad fills data-gumroad-field="price"/"description" with live values and
turns data-gumroad-action="buy" into checkout, so those hooks must stay.
The page renders inside a sandboxed iframe whose CSP only allows images from
public-files.gumroad.com / static-2.gumroad.com.
"""
import html

from . import backdrop

STORE_URL = "https://shadowgasp.gumroad.com/"
LOGO = "https://public-files.gumroad.com/cl21bznqqeyqx5d90dwf3rix9uva"
DISCLOSURE = (
    "Based on real events and public records. Dialogue is dramatized where no verbatim "
    "record exists. Interior art was generated with AI image tools and art-directed, edited "
    "and composited for publication; the writing, lettering and layout are original to this edition."
)

CSS = """
@import url("https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Montserrat:wght@400;600;800&display=swap");
:root{--ink:#0b0b0d;--panel:#131317;--line:#2a2a31;--paper:#f1ece4;--muted:#a19c95;--red:#d0342c;--red-deep:#8e1d18}
*{box-sizing:border-box}
html,body{margin:0;background:var(--ink)}
body{color:var(--paper);font-family:Montserrat,"Segoe UI",Helvetica,Arial,sans-serif;line-height:1.6;
  background:radial-gradient(1100px 620px at 80% -8%,#2c0f0e 0%,rgba(11,11,13,0) 62%),var(--ink)}
a{color:inherit;text-decoration:none}
.wrap{max-width:1180px;margin:0 auto;padding:0 clamp(16px,4vw,48px)}
.display{font-family:"Bebas Neue",Impact,"Arial Narrow",sans-serif;font-weight:400;letter-spacing:.02em;line-height:.92;margin:0}
.eyebrow{color:var(--red);font-weight:800;font-size:12px;letter-spacing:.28em;text-transform:uppercase;margin:0}
.muted{color:var(--muted)}
.top{display:flex;align-items:center;gap:12px;padding:22px 0;border-bottom:1px solid var(--line)}
.top img{width:42px;height:42px;border-radius:50%;border:2px solid var(--red)}
.top .display{font-size:28px}
.top .all{margin-left:auto;font-size:12px;font-weight:800;letter-spacing:.2em;text-transform:uppercase;
  border:1px solid var(--line);padding:9px 14px;transition:border-color .2s,background .2s}
.top .all:hover{border-color:var(--paper);background:rgba(255,255,255,.04)}
.hero{display:grid;grid-template-columns:1.1fr minmax(0,420px);gap:clamp(28px,6vw,80px);align-items:center;
  padding:clamp(36px,7vw,90px) 0 clamp(40px,6vw,70px)}
.hero .no{display:block;color:var(--muted);font-size:clamp(22px,2.6vw,30px);margin:14px 0 4px}
.hero h1{font-size:clamp(64px,10vw,138px)}
.hero .hook{font-size:clamp(17px,1.8vw,21px);font-weight:600;color:#e4ded5;max-width:30em;margin:22px 0 32px}
.buyrow{display:flex;flex-wrap:wrap;align-items:center;gap:14px 22px}
.buy{display:inline-flex;align-items:center;gap:10px;background:var(--red);color:#fff;font-weight:800;cursor:pointer;
  letter-spacing:.12em;text-transform:uppercase;font-size:15px;padding:17px 30px;border-radius:2px;
  box-shadow:6px 6px 0 var(--red-deep);transition:transform .15s ease,box-shadow .15s ease}
.buy:hover{transform:translate(-2px,-2px);box-shadow:8px 8px 0 var(--red-deep)}
.note{font-size:12px;font-weight:800;letter-spacing:.2em;text-transform:uppercase;color:var(--muted)}
.cover{position:relative;justify-self:center;width:100%;max-width:420px}
.frame{aspect-ratio:368/564;overflow:hidden;border-radius:4px;background:#000}
.cover .frame{transform:rotate(2.5deg);box-shadow:0 40px 90px rgba(0,0,0,.75),0 0 0 1px var(--line);transition:transform .5s ease}
.cover:hover .frame{transform:rotate(0) scale(1.02)}
.frame img{display:block;width:163.05%;max-width:none;margin:-4.9% 0 0 -31.52%}
.stamp{position:absolute;left:-22px;bottom:-26px;transform:rotate(-8deg);border:3px solid var(--red);color:var(--red);
  background:rgba(11,11,13,.82);font-family:"Bebas Neue",Impact,sans-serif;font-size:30px;letter-spacing:.08em;
  line-height:1;padding:8px 14px 5px;white-space:nowrap;box-shadow:0 0 0 3px rgba(11,11,13,.82)}
.band{border-top:1px solid var(--line);border-bottom:1px solid var(--line);background:rgba(255,255,255,.015)}
.facts{display:flex;flex-wrap:wrap;gap:10px 34px;padding:18px 0;font-size:12px;font-weight:800;letter-spacing:.2em;text-transform:uppercase}
.facts span::before{content:"";display:inline-block;width:7px;height:7px;background:var(--red);margin-right:10px;transform:translateY(-1px)}
section.block{padding:clamp(56px,8vw,96px) 0 0}
.head{display:flex;align-items:end;gap:18px;margin-bottom:30px}
.head .display{font-size:clamp(46px,6vw,76px)}
.head .rule{flex:1;height:1px;background:var(--line);margin-bottom:14px}
.exhibits{display:grid;gap:18px;max-width:880px}
.exhibit{display:grid;grid-template-columns:120px 1fr;gap:22px;padding:22px 26px;background:var(--panel);
  border:1px solid var(--line);border-left:4px solid var(--red)}
.exhibit b{font-family:"Bebas Neue",Impact,sans-serif;font-weight:400;font-size:26px;line-height:1;color:var(--muted);letter-spacing:.04em}
.exhibit p{margin:0;font-size:17px;color:#dcd6cd}
.files{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}
.file{position:relative;padding:40px 22px 24px;background:var(--panel);border:1px solid var(--line);
  clip-path:polygon(0 14px,38% 14px,44% 0,100% 0,100% 100%,0 100%);transition:transform .2s ease,border-color .2s}
.file:hover{transform:translateY(-4px);border-color:var(--red)}
.file i{position:absolute;top:22px;left:22px;font-style:normal;text-transform:uppercase;color:var(--red);font-weight:800;font-size:12px;letter-spacing:.2em}
.file h3{font-family:"Bebas Neue",Impact,sans-serif;font-weight:400;font-size:30px;line-height:1;margin:12px 0 0;letter-spacing:.02em}
.close{margin-top:clamp(56px,8vw,96px);padding:clamp(40px,6vw,72px) clamp(20px,5vw,64px);text-align:center;
  border:1px dashed var(--red);background:linear-gradient(180deg,rgba(208,52,44,.10),rgba(208,52,44,.02))}
.close .display{font-size:clamp(48px,7vw,92px)}
.close .desc{max-width:760px;margin:22px auto 34px;color:#d3cdc4;font-size:16px;white-space:pre-line}
.more{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:22px}
.mini{display:block}
.mini .frame{box-shadow:0 14px 30px rgba(0,0,0,.6),0 0 0 1px var(--line);transition:transform .25s ease,box-shadow .25s}
.mini:hover .frame{transform:translateY(-6px) rotate(-1deg);box-shadow:0 22px 40px rgba(0,0,0,.7),0 0 0 2px var(--red)}
.mini .case{display:block;margin:14px 0 4px;color:var(--red);font-size:11px;font-weight:800;letter-spacing:.24em;text-transform:uppercase}
.mini h3{font-family:"Bebas Neue",Impact,sans-serif;font-weight:400;font-size:24px;line-height:1;margin:0 0 6px}
.mini .price{font-size:13px;font-weight:600;color:var(--muted)}
.backlink{display:inline-block;margin-top:30px;font-size:12px;font-weight:800;letter-spacing:.2em;text-transform:uppercase;
  border-bottom:2px solid var(--red);padding-bottom:4px}
footer{margin-top:clamp(64px,9vw,110px);border-top:1px solid var(--line);padding:34px 0 48px;text-align:center}
footer .display{font-size:clamp(34px,5vw,56px)}
footer p.small{max-width:720px;margin:16px auto 0;font-size:12px;color:#77726b}
.rise{opacity:0;animation:rise .8s cubic-bezier(.2,.7,.2,1) forwards}
.d1{animation-delay:.08s}.d2{animation-delay:.18s}.d3{animation-delay:.28s}.d4{animation-delay:.38s}
@keyframes rise{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}
.sticky{display:none}
@media (max-width:760px){
  .hero{grid-template-columns:1fr;text-align:center}
  .hero .cover{order:-1;max-width:250px;margin-bottom:28px}
  .hero .hook{margin-left:auto;margin-right:auto}
  .buyrow{justify-content:center}
  .stamp{font-size:22px;left:-14px;bottom:-30px}
  .top .all{padding:8px 10px;letter-spacing:.12em}
  .exhibit{grid-template-columns:1fr;gap:8px}
  .more{grid-template-columns:repeat(2,minmax(0,1fr))}
  .sticky{display:block;z-index:5;position:fixed;left:0;right:0;bottom:0;padding:10px 14px;background:rgba(11,11,13,.92);
    border-top:1px solid var(--line);backdrop-filter:blur(10px)}
  .sticky .buy{display:flex;justify-content:center;box-shadow:none}
  footer{padding-bottom:110px}
}
@media (prefers-reduced-motion:reduce){.rise{animation:none;opacity:1}*{transition:none!important}}
"""

LETTERS = "ABCDEFGH"


def _cover(url, cls="frame"):
    return f'<div class="{cls}"><img src="{html.escape(url)}" alt=""></div>'


def build_html(case, related):
    e = html.escape
    n = case["issue_no"]
    title = case["title"]
    exhibits = "".join(
        f'<div class="exhibit"><b>Exhibit {LETTERS[i]}</b><p>{e(t)}</p></div>'
        for i, t in enumerate(case["what"][:len(LETTERS)])
    )
    files = "".join(
        f'<div class="file"><i>File {i + 1:02d}</i><h3>{e(t)}</h3></div>'
        for i, t in enumerate(case["inside"][:4])
    )
    more = "".join(
        f'<a class="mini" href="{e(r["url"])}">{_cover(r["thumbnail_url"])}'
        f'<span class="case">Case No. {r["issue_no"]}</span><h3>{e(r["title"])}</h3>'
        f'<span class="price">{e(r["price"])}</span></a>'
        for r in related[:4]
    )
    buy = ('<a data-gumroad-action="buy" class="buy">{label} &mdash; '
           '<span data-gumroad-field="price">{price}</span></a>')
    price = e(case.get("price", ""))
    bd_css, bd_html = backdrop.backdrop(backdrop.pick(n, 3), slots=backdrop.LANDING_SLOTS)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(f"SHADOW GASP #{n}: {title}")}</title>
<style>{CSS}
{bd_css}</style>
</head>
<body>
{bd_html}
<div class="fg">
<div class="wrap">
  <header class="top">
    <a href="{STORE_URL}"><img src="{LOGO}" alt="Shadow Gasp"></a>
    <a href="{STORE_URL}" class="display">Shadow Gasp</a>
    <a class="all" href="{STORE_URL}">All case files</a>
  </header>

  <section class="hero">
    <div>
      <p class="eyebrow rise">True crime · Documentary comic</p>
      <h1 class="display rise d1"><span class="no">Case file No. {n}</span>{e(title)}</h1>
      <p class="hook rise d2">{e(case["hook"])}</p>
      <div class="buyrow rise d3">
        {buy.format(label="Get the comic", price=price)}
        <span class="note">Instant PDF download</span>
      </div>
    </div>
    <div class="cover rise d2">
      {_cover(case["thumbnail_url"])}
      <span class="stamp">{e(case["badge"])}</span>
    </div>
  </section>
</div>

<div class="band"><div class="wrap facts">
  <span>Issue No. {n} · out now</span><span>{e(case["badge"])}</span><span>Real case files</span><span>Read on any device</span>
</div></div>

<div class="wrap">
  <section class="block">
    <div class="head"><h2 class="display">What happened</h2><div class="rule"></div></div>
    <div class="exhibits">{exhibits}</div>
  </section>

  <section class="block">
    <div class="head"><h2 class="display">Inside this issue</h2><div class="rule"></div></div>
    <div class="files">{files}</div>
  </section>

  <section class="close">
    <p class="eyebrow">Case file No. {n}</p>
    <h2 class="display" style="margin-top:12px">Read the whole case</h2>
    <p class="desc" data-gumroad-field="description">{e(case["subject"])}</p>
    {buy.format(label="Get it now", price=price)}
    <p class="note" style="margin-top:22px">Instant PDF · read on any device</p>
  </section>

  <section class="block">
    <div class="head"><h2 class="display">More case files</h2><div class="rule"></div></div>
    <div class="more">{more}</div>
    <a class="backlink" href="{STORE_URL}">See every case file →</a>
  </section>

  <footer>
    <p class="display">Pick a case. Turn off the lights.</p>
    <p class="small">{e(DISCLOSURE)}</p>
  </footer>
</div>

</div>
<div class="sticky">{buy.format(label="Get the comic", price=price)}</div>
</body>
</html>
"""
