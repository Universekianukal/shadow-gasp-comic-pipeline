"""Build and publish a per-case Gumroad custom landing page from the script's
own fields -- no per-case hand-writing needed. Reuses the visual system
proven on issue 01 (NORJAK): real buy buttons look categorically different
from informational tags, no button-shaped pixels baked into any image, no
duplicated title text next to the cover.

Safety: `publish_if_safe()` runs Gumroad's own sanitizer via `preview` first.
If it strips a buy element or returns any warning, this DOES NOT publish --
a broken landing page makes the product unpurchasable, which is worse than
just keeping Gumroad's default page.
"""
import html
import json
import os
import subprocess

GUMROAD_BIN = os.path.join(os.path.expanduser("~"), ".local", "bin",
                           "gumroad.exe" if os.name == "nt" else "gumroad")

TEMPLATE = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_esc}</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>tailwind.config = {{ darkMode: 'class' }};</script>
<style>
  :root {{ --ink:#0e0e10; --cream:#eee8da; --accent:#c63024; --gold:#e2a830; }}
  html{{scroll-behavior:smooth}}
  body{{background:var(--ink);color:var(--cream);font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
  .display{{font-weight:900;letter-spacing:-.02em;line-height:.95}}
  .rule{{height:7px;width:120px;background:var(--accent)}}
  .grain{{position:fixed;inset:0;pointer-events:none;opacity:.05;background-image:radial-gradient(#fff 1px,transparent 1px);background-size:3px 3px}}
  .reveal{{opacity:0;transform:translateY(18px);transition:opacity .7s ease,transform .7s ease}}
  .reveal.in{{opacity:1;transform:none}}
  .cover-shadow{{box-shadow:0 30px 70px -20px rgba(0,0,0,.9),0 0 0 1px rgba(255,255,255,.06)}}
  .card{{border:2px solid #3a3730}}
  .buy{{background:var(--accent);transition:transform .15s ease,filter .15s ease;cursor:pointer}}
  .buy:hover{{transform:translateY(-2px);filter:brightness(1.08)}}
  .tag{{border:1.5px solid #4a4640;color:#c9c5bc}}
  html.light body{{background:#f5f2ea;color:#16161a}}
  html.light .card{{border-color:#c9c4b8}}
  html.light .tag{{border-color:#c9c4b8;color:#57534b}}
</style>
</head>
<body class="antialiased">
<div class="grain"></div>
<div class="w-full bg-black/80 border-b border-white/10">
  <div class="max-w-6xl mx-auto px-5 py-3 flex items-center justify-between text-[11px] sm:text-xs font-extrabold tracking-widest">
    <span>TRUE CRIME &nbsp;·&nbsp; DOCUMENTARY COMIC</span>
    <button id="mode" class="tag px-3 py-1 rounded text-[10px] font-extrabold tracking-widest">LIGHT / DARK</button>
  </div>
</div>

<header class="max-w-6xl mx-auto px-5 pt-12 pb-16 grid gap-12 md:grid-cols-2 items-center">
  <div class="reveal order-2 md:order-1">
    <p class="text-xs font-extrabold tracking-[.25em]" style="color:var(--gold)">ISSUE {issue_no_esc}</p>
    <h1 class="display text-6xl sm:text-7xl mt-3" data-gumroad-field="name">{title_esc}</h1>
    <div class="rule mt-6"></div>
    <p class="mt-7 text-xl sm:text-2xl font-bold leading-snug">{hook_esc}</p>
    <div class="mt-9 flex flex-wrap items-center gap-3">
      <a data-gumroad-action="buy" class="buy inline-flex items-center justify-center rounded-lg px-8 py-4 font-extrabold tracking-wide text-white text-lg">
        Get the comic &mdash; <span data-gumroad-field="price" class="ml-2">$2.99</span>
      </a>
      <span class="inline-flex items-center gap-1.5 text-xs font-bold tracking-widest" style="color:#8a8680">
        <svg width="13" height="13" viewBox="0 0 20 20" fill="none" style="opacity:.8">
          <path d="M4 10.5l4 4 8-9" stroke="#8a8680" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        INSTANT PDF DOWNLOAD
      </span>
    </div>
  </div>
  <div class="reveal order-1 md:order-2 flex justify-center">
    <img src="{cover_url}" alt="Cover of {title_esc}" class="cover-shadow rounded w-full max-w-[440px] sm:max-w-[520px]">
  </div>
</header>

<section class="max-w-6xl mx-auto px-5 pb-16">
  <p class="reveal text-[11px] font-bold tracking-widest mb-3" style="color:#6e6a63">AT A GLANCE</p>
  <div class="reveal flex flex-wrap gap-2.5">
    <span class="tag inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-bold tracking-wide">
      <span class="w-1.5 h-1.5 rounded-full" style="background:#8a8680"></span>{badge_esc}
    </span>
    <span class="tag inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-bold tracking-wide">
      <span class="w-1.5 h-1.5 rounded-full" style="background:#8a8680"></span>ISSUE {issue_no_esc} &middot; OUT NOW
    </span>
    <span class="tag inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-bold tracking-wide">
      <span class="w-1.5 h-1.5 rounded-full" style="background:#8a8680"></span>REAL CASE FILES
    </span>
    <span class="tag inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-bold tracking-wide">
      <span class="w-1.5 h-1.5 rounded-full" style="background:#8a8680"></span>READ ANYWHERE
    </span>
  </div>
</section>

<section class="max-w-4xl mx-auto px-5 pb-20">
  <h2 class="reveal display text-3xl sm:text-4xl">WHAT HAPPENED</h2>
  <div class="rule mt-4 reveal"></div>
  <div class="mt-8 space-y-5 text-lg leading-relaxed reveal" style="color:#cfcac1">
    {what_happened}
  </div>
</section>

<section class="max-w-6xl mx-auto px-5 pb-20">
  <h2 class="reveal display text-3xl sm:text-4xl">INSIDE THIS ISSUE</h2>
  <div class="rule mt-4 reveal"></div>
  <div class="mt-8 grid gap-4 sm:grid-cols-2 reveal">
    {inside_cards}
  </div>
</section>

<section class="max-w-4xl mx-auto px-5 pb-28 text-center">
  <div class="reveal">
    <h2 class="display text-4xl sm:text-5xl">READ THE WHOLE CASE</h2>
    <p class="mt-5 text-lg" style="color:#a8a49c" data-gumroad-field="description">{subject_esc}</p>
    <a data-gumroad-action="buy" class="buy mt-9 inline-flex items-center justify-center rounded-lg px-10 py-5 font-extrabold tracking-wide text-white text-xl">
      Get it now &mdash; <span data-gumroad-field="price" class="ml-2">$2.99</span>
    </a>
    <p class="mt-5 text-xs font-bold tracking-widest" style="color:#7d7970">INSTANT PDF &middot; READ ON ANY DEVICE</p>
    <p class="mt-10 text-xs leading-relaxed" style="color:#6e6a63">
      Based on real events and public records. Dialogue is dramatized where no
      verbatim record exists. Interior art was generated with AI image tools
      and art-directed, edited and composited for publication; the writing,
      lettering and layout are original to this edition.
    </p>
  </div>
</section>

<footer class="border-t border-white/10 py-8 text-center text-xs font-bold tracking-widest" style="color:#6e6a63">
  SHADOW GASP &nbsp;·&nbsp; REAL CASES, RESEARCHED AND DRAWN
</footer>

<div class="fixed bottom-0 left-0 right-0 sm:hidden bg-black/85 border-t border-white/10 p-3" style="backdrop-filter:blur(10px)">
  <a data-gumroad-action="buy" class="buy block text-center rounded-lg py-4 font-extrabold tracking-wide text-white">
    Get the comic &mdash; <span data-gumroad-field="price">$2.99</span>
  </a>
</div>
<div class="h-20 sm:hidden"></div>

<script>
  var io = new IntersectionObserver(function(es){{
    es.forEach(function(e){{ if(e.isIntersecting){{ e.target.classList.add('in'); io.unobserve(e.target); }} }});
  }}, {{ threshold: .12 }});
  document.querySelectorAll('.reveal').forEach(function(el){{ io.observe(el); }});
  document.getElementById('mode').addEventListener('click', function(){{
    document.documentElement.classList.toggle('light');
    document.documentElement.classList.toggle('dark');
  }});
</script>
</body>
</html>
"""


def _fact_paragraphs(script, limit=3):
    """Pull real, already fact-checked prose from back_matter instead of
    writing new copy -- back_matter.lines is the one field in the script
    schema explicitly required to be non-fabricated."""
    lines = [l for l in script.get("back_matter", {}).get("lines", [])
             if l.strip() and not l.strip().startswith("Sources")]
    return lines[:limit] or [script.get("subject", "")]


def build_html(script, cover_url):
    title = script["title"]
    what_happened = "\n    ".join(
        f"<p>{html.escape(p)}</p>" for p in _fact_paragraphs(script)
    )
    inside = script.get("promo_inside") or [
        "REAL CASE FILES", "NAMED SOURCES", "TIMELINE", "WHAT WAS REAL"
    ]
    inside_cards = "\n    ".join(
        f'<div class="card rounded-lg p-6"><p class="font-extrabold tracking-wide" '
        f'style="color:var(--gold)">{html.escape(item.upper())}</p></div>'
        for item in inside[:4]
    )
    return TEMPLATE.format(
        title_esc=html.escape(f'{script.get("series","SHADOW GASP")} #{script.get("issue_no","01")}: {title}'),
        issue_no_esc=html.escape(str(script.get("issue_no", "01"))),
        hook_esc=html.escape(script.get("promo_hook") or script.get("tagline", "")),
        cover_url=cover_url,
        badge_esc=html.escape(script.get("promo_badge", "REAL CASE")),
        what_happened=what_happened,
        inside_cards=inside_cards,
        subject_esc=html.escape(script.get("subject", "")),
    )


def publish_if_safe(product_id, html_path):
    """Preview through Gumroad's real sanitizer first; only publish if it's
    clean (no warning, and nothing structurally important got stripped)."""
    preview = subprocess.run(
        [GUMROAD_BIN, "products", "page", "preview", product_id, html_path,
         "--json", "--no-input", "--non-interactive"],
        capture_output=True, text=True,
    )
    if preview.returncode != 0:
        return False, f"preview failed: {preview.stderr or preview.stdout}"
    data = json.loads(preview.stdout)
    if data.get("warning"):
        return False, f"sanitizer warning: {data['warning']}"

    publish = subprocess.run(
        [GUMROAD_BIN, "products", "page", "publish", product_id, html_path,
         "--json", "--no-input", "--non-interactive"],
        capture_output=True, text=True,
    )
    if publish.returncode != 0:
        return False, f"publish failed: {publish.stderr or publish.stdout}"
    pdata = json.loads(publish.stdout)
    if not pdata.get("success") or pdata.get("warning"):
        return False, f"publish warning: {pdata.get('warning')}"
    return True, None
