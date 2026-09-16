"""The data a landing page needs, from a fresh script (build time) or from the live page (sync).

A "case" is {issue_no, title, hook, badge, what, inside, subject, thumbnail_url, price}.
"""
import html
import json
import os
import re
import urllib.request

from .store_pages import STORE_URL, issue_no, title_of

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INSIDE = ["REAL CASE FILES", "NAMED SOURCES", "TIMELINE", "WHAT WAS REAL"]
# Marker of a page already in this design.
V2_MARKER = 'class="exhibits"'


def status_labels():
    """Hand-checked case-status stamps (see STATUS_NOTES.md); these beat the script's promo_badge."""
    with open(os.path.join(HERE, "status_labels.json"), encoding="utf-8") as f:
        return {int(k): v for k, v in json.load(f).items()}


def _plain(desc):
    text = re.sub(r"<br\s*/?>|</p>", "\n", desc or "")
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return [re.sub(r"\s+", " ", t).strip() for t in text.split("\n") if t.strip()]


def _sentences(text):
    return [s.strip() for s in re.findall(r".+?(?:[.!?](?=\s|$)|$)", text) if s.strip()]


def _clean(what):
    return [re.sub(r"^FACT:\s*", "", w) for w in what if w.strip()]


def related(products, n, count=4):
    """Older issues first (they never change), newer ones only to fill."""
    live = {issue_no(p.get("name")): p for p in products if p.get("published") and not p.get("deleted")}
    older = [k for k in sorted(live, reverse=True) if 0 < k < n]
    newer = [k for k in sorted(live) if k > n]
    return [{"issue_no": k, "title": title_of(live[k]["name"]), "price": live[k]["formatted_price"],
             "url": live[k]["short_url"], "thumbnail_url": live[k]["thumbnail_url"]}
            for k in (older + newer)[:count]]


def from_script(script, product, fact_lines):
    """New comic at build time. fact_lines = the fact-checked back-matter paragraphs."""
    n = int(str(script.get("issue_no", "0")).lstrip("0") or 0)
    return {
        "issue_no": n,
        "title": script["title"],
        "hook": script.get("promo_hook") or script.get("tagline", ""),
        "badge": status_labels().get(n) or (script.get("promo_badge") or "REAL CASE").upper(),
        "what": _clean(fact_lines) or [script.get("subject", "")],
        "inside": [x.upper() for x in (script.get("promo_inside") or DEFAULT_INSIDE)][:4],
        "subject": "\n\n".join(_plain(product.get("description"))) or script.get("subject", ""),
        "thumbnail_url": product["thumbnail_url"],
        "price": product.get("formatted_price", ""),
    }


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (shadow-gasp store sync)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def live_landing(product):
    """The custom HTML currently served for a product, or None when it has none."""
    page = fetch(product["short_url"])
    m = re.search(r'id="gumroad-landing-frame"\s+src="([^"]+)"', page)
    return fetch(STORE_URL.rstrip("/") + m.group(1)) if m else None


def from_live_page(product, embed_html):
    """Existing comic: reuse the text of its old-design page, or the description when it has none."""
    n = issue_no(product["name"])
    rec = {}
    def txt(x):
        return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", x))).strip()
    if embed_html and V2_MARKER in embed_html:
        # Already this design (a re-render, e.g. after new characters were cut). Gumroad's
        # sanitizer re-serialises the page with newlines between tags, hence the \s*.
        hook = re.search(r'<p class="hook[^"]*">(.*?)</p>', embed_html, re.S)
        stamp = re.search(r'<span class="stamp">(.*?)</span>', embed_html, re.S)
        rec = {
            "hook": txt(hook.group(1)) if hook else "",
            "badge": txt(stamp.group(1)) if stamp else "",
            "what": [txt(x) for x in re.findall(r'<div class="exhibit">\s*<b>.*?</b>\s*<p>(.*?)</p>\s*</div>', embed_html, re.S)],
            "inside": [txt(x) for x in re.findall(r'<div class="file">\s*<i>.*?</i>\s*<h3>(.*?)</h3>\s*</div>', embed_html, re.S)],
        }
    elif embed_html and "WHAT HAPPENED" in embed_html:
        def g(pattern):
            m = re.search(pattern, embed_html, re.S)
            return html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""
        block = re.search(r'WHAT HAPPENED.*?<div class="mt-8[^"]*"[^>]*>(.*?)</div>', embed_html, re.S)
        rec = {
            "hook": g(r'<div class="rule mt-6"></div>\s*<p[^>]*>(.*?)</p>'),
            "badge": g(r"AT A GLANCE.*?</span>(.*?)</span>"),
            "what": [html.unescape(re.sub(r"\s+", " ", x)).strip()
                     for x in re.findall(r"<p>(.*?)</p>", block.group(1) if block else "", re.S)],
            "inside": [html.unescape(x).strip()
                       for x in re.findall(r'<div class="card[^"]*"><p[^>]*>(.*?)</p></div>', embed_html, re.S)],
        }
    paras = _plain(product.get("description"))
    first = _sentences(paras[0]) if paras else [""]
    return {
        "issue_no": n,
        "title": title_of(product["name"]),
        "hook": rec.get("hook") or " ".join(first[:2]),
        "badge": status_labels().get(n) or rec.get("badge") or "REAL CASE",
        "what": _clean(rec.get("what") or paras[1:4] or first[2:5] or first),
        "inside": rec.get("inside") or DEFAULT_INSIDE,
        "subject": "\n\n".join(paras),
        "thumbnail_url": product["thumbnail_url"],
        "price": product.get("formatted_price", ""),
    }
