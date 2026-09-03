"""Build the comic PDF, create a Gumroad DRAFT product (not public) with it,
send the plain PDF to Telegram, then register it with the Cloudflare Worker
(a plain HTTPS call to the Worker's own public URL, protected by a shared
secret — no separate Cloudflare API token needed). The Worker owns all
approval state in its own KV binding and sends the follow-up message with
Approve / Reject / Increase Pages buttons.
"""
import argparse
import glob
import json
import mimetypes
import os
import re
import secrets
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

GUMROAD_BIN = "gumroad"
DEFAULT_CATEGORY = "comics-and-graphic-novels"

# Flat tier pricing keyed by target page count, shared with the Worker's
# "Increase Pages" buttons (worker/worker.js pageCountKeyboard). 25pp is the
# pipeline's own default page count and keeps the base $2.99 price.
PAGE_PRICE_TIERS = {20: "0", 25: "2.99", 35: "3.99", 50: "4.99", 75: "6.99", 100: "8.99"}


def gumroad(args_list):
    result = subprocess.run([GUMROAD_BIN, *args_list, "--json"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gumroad CLI failed: {result.stderr or result.stdout}")
    return json.loads(result.stdout)


def pick_preview_panels(comic_dir, script, limit=3):
    """Pick interior panels to use as extra product previews / promo images.

    Deliberately drawn from the OPENING THIRD of the book only. The temptation
    is to grab the splash pages because they're the most striking, but splashes
    are the story's biggest beats — including the final page. Using those as
    free previews gives away the reveals and the ending, which is the opposite
    of what a preview is for. Early pages set atmosphere and raise the question
    without answering it.
    """
    panels_dir = os.path.join(comic_dir, "panels")
    pages = script.get("pages", [])
    early = pages[:max(1, len(pages) // 3)]

    files = []
    for page in early:
        if page.get("type") == "splash" and page.get("panel"):
            files.append(page["panel"]["file"])
        else:
            for row in page.get("rows", []):
                for cell in row:
                    files.append(cell["file"])

    chosen = [f for f in files if os.path.exists(os.path.join(panels_dir, f))]
    return [os.path.join(panels_dir, f) for f in chosen[:limit]]


def build_store_description(script):
    """The Gumroad product page copy.

    This used to be script["subject"], which the schema defines as ONE SENTENCE. POISONED GROUND
    therefore went on sale behind 141 characters while HEAVEN'S GATE -- written by hand before
    the pipeline existed -- had 1,103. The product page is where somebody decides whether to buy,
    and one sentence is not a decision.

    Uses the model's own store_description when it wrote one; otherwise composes from material
    the script already carries: the hook, the subject, what the issue covers, and the first
    factual paragraphs of the back matter.
    """
    authored = (script.get("store_description") or "").strip()
    if len(authored) > 300:
        return authored

    paras = []
    hook = (script.get("promo_hook") or "").strip()
    subject = (script.get("subject") or "").strip()
    if hook:
        paras.append(hook)
    if subject and subject != hook:
        paras.append(subject)

    facts = [ln.strip() for ln in (script.get("back_matter") or {}).get("lines", [])
             if ln.strip() and len(ln.strip()) > 60]
    if facts:
        paras.append(" ".join(facts[:2]))

    inside = [x.strip() for x in (script.get("promo_inside") or []) if x.strip()]
    if inside:
        paras.append("Inside: " + " · ".join(inside) + ".")

    pages = len(script.get("pages", []))
    paras.append(
        (f"{pages} story pages of documentary comics. " if pages else "")
        + "Based on real events and the public record. Dialogue is dramatized.")
    return "<p>" + "</p><p>".join(paras) + "</p>"


def slugify(title):
    """Title -> URL slug, so the product lives at /l/norjak rather than /l/vkzul.

    Gumroad hands out a random slug unless a custom permalink is set, and a
    random one is unshareable, unmemorable and tells a buyer nothing.
    """
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:40].strip("-") or "issue"


def stage_draft(name, pdf_path, cover_path, price, description, tags, category,
                preview_paths=None, thumbnail_path=None, permalink=None):
    # Deliberate defaults, all left OFF because the API's absence of a flag IS
    # the off state: pay-what-you-want, installments, quantity selection,
    # purchase limits and shipping. None help a $2.99 single-file download.
    args = ["products", "create", "--name", name, "--price", price,
            "--file", pdf_path, "--file-name", os.path.basename(pdf_path),
            # Once a PDF is downloaded there's nothing to return, which is why
            # no-refunds is the norm for low-cost digital downloads. Fine print
            # deliberately left blank.
            "--refund-period", "none"]
    if description:
        args += ["--description", description]
    if cover_path and os.path.exists(cover_path):
        args += ["--cover-image", cover_path]
    thumb = thumbnail_path or cover_path
    if thumb and os.path.exists(thumb):
        args += ["--thumbnail", thumb]
    for p in (preview_paths or []):
        args += ["--preview-image", p]
    for t in (tags or []):
        args += ["--tag", t]
    if category:
        args += ["--category", category]
    if permalink:
        args += ["--custom-permalink", permalink]
    try:
        data = gumroad(args)
        return data.get("product", data)["id"]
    except RuntimeError as e:
        if "permalink is already used" not in str(e):
            raise
        # Rebuilding a case reuses its permalink, so the second attempt collides with the draft
        # the first one left behind and the whole run dies at the last step. Update that draft
        # in place instead: a rebuild is meant to REPLACE the previous attempt, not to fail or
        # to litter the store with poisoned-ground-2.
        existing = next((p for p in gumroad(["products", "list"]).get("products", [])
                         if p.get("custom_permalink") == permalink
                         or (p.get("short_url") or "").rstrip("/").endswith("/" + permalink)), None)
        if not existing:
            raise
        if existing.get("published") or (existing.get("sales_count") or 0) > 0:
            # Never silently overwrite something buyers can already see.
            raise RuntimeError(
                f"permalink '{permalink}' belongs to a PUBLISHED product ({existing['id']}); "
                "refusing to overwrite it automatically")
        print(f"permalink '{permalink}' already on draft {existing['id']} -- updating it",
              flush=True)
        upd = ["products", "update", existing["id"], "--name", name, "--price", price,
               "--file", pdf_path, "--file-name", os.path.basename(pdf_path)]
        if description:
            upd += ["--description", description]
        # Deliberately NO --cover-image on the update path. Gumroad counts covers as previews
        # and caps them at 8, and each rebuild APPENDS rather than replacing -- so after a few
        # rebuilds the update itself started failing with "we have a limit of 8 previews",
        # taking a finished book down with it. The draft already carries the covers the first
        # staging gave it; a rebuild is here to replace the FILE, not to add more images.
        gumroad(upd)
        prune_stale_files(existing["id"])
        return existing["id"]


def prune_stale_files(product_id):
    """Leave exactly ONE downloadable file on the product: the newest upload.

    `products update --file` APPENDS. This is the same trap the covers hit four lines up, and it
    went unnoticed far longer for one reason: a failed cover upload breaks the build loudly,
    while a surplus download is completely invisible from the build log.

    Two different counts matter here and they are easy to confuse -- I confused them, and argued
    from the wrong one. `product["files"]` is the ASSET STORE, which retains orphaned uploads
    after their download rows are gone; NORJAK holds 5 and HEAVEN'S GATE 2 purely as leftovers.
    What a buyer actually sees is the fileEmbed list in the CONTENT document, and only POISONED
    GROUND ever accumulated those, reaching 10. Check content, never files, to judge this.

    Ten identical-looking rows would be merely untidy. What makes it a real defect is that the
    copies are NOT identical: they are separate builds, so they disagree. POISONED GROUND's older
    copies carry '$2.99' on the back cover while the product sells for $4.99 -- same 51 pages,
    same art, one substituted string. A buyer paying $4.99 could open a book that prints a
    different price, and would have no way to tell which of the ten was the real one.

    Keeping the LAST entry is what makes this correct rather than arbitrary: Gumroad returns
    files in upload order, so the last is the one this run just uploaded.

    Best-effort. A staged, priced, uploaded comic must not be lost to a tidying step, so every
    failure here warns and returns instead of raising.
    """
    try:
        product = gumroad(["products", "view", product_id])
        files = (product.get("product", product) or {}).get("files") or []
        if len(files) < 2:
            return
        keep = files[-1]["id"]

        pages = gumroad(["products", "content", "get", product_id])
        if isinstance(pages, dict):
            pages = pages.get("pages", [pages])
        for page in pages:
            body = page.get("description") or {}
            body["content"] = [
                node for node in body.get("content", [])
                if node.get("type") != "fileEmbed"
                or (node.get("attrs") or {}).get("id") == keep
            ]

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as fh:
            json.dump(pages, fh)
            path = fh.name
        try:
            gumroad(["products", "content", "set", product_id, path, "--yes"])
        finally:
            os.unlink(path)
        print(f"pruned {len(files) - 1} stale file(s) from {product_id}, kept {keep}", flush=True)
    except Exception as exc:  # noqa: BLE001 - tidying must never sink a finished build
        print(f"WARNING: could not prune stale files from {product_id}: {exc}", flush=True)


# Telegram bot API hard limit for sendDocument. Not configurable, not raisable by any plan.
TELEGRAM_DOC_LIMIT = 50 * 1024 * 1024


def make_review_copy(pdf_path, target_mb=45):
    """Rasterise the comic to a smaller PDF that Telegram will actually accept.

    ONLY for the review copy. The file uploaded to Gumroad is always the untouched print
    master -- quality is the product, and this must never be substituted for it.

    Steps down through DPI until it fits. Flat ink-and-halftone art compresses extremely well:
    the 114MB/80-page Heaven's Gate master came to 36.6MB at 200 DPI, still comfortably
    readable on a phone. Returns None on failure rather than raising, so a delivery problem
    can never lose a comic that already built and staged correctly.
    """
    try:
        import fitz
    except ImportError:
        print("WARNING: PyMuPDF not available, cannot build a review copy", flush=True)
        return None

    out_path = os.path.splitext(pdf_path)[0] + "_review.pdf"
    try:
        src = fitz.open(pdf_path)
        for dpi, quality in ((200, 85), (150, 80), (110, 75), (85, 70)):
            out = fitz.open()
            for i in range(src.page_count):
                pix = src[i].get_pixmap(dpi=dpi)
                out.new_page(width=pix.width, height=pix.height).insert_image(
                    fitz.Rect(0, 0, pix.width, pix.height),
                    stream=pix.pil_tobytes(format="JPEG", quality=quality))
            out.save(out_path, deflate=True, garbage=4)
            out.close()
            mb = os.path.getsize(out_path) / 1e6
            print(f"review copy: {dpi} DPI q{quality} -> {mb:.1f}MB", flush=True)
            if mb < target_mb:
                return out_path
        print("WARNING: could not get the review copy under the Telegram limit", flush=True)
        return None
    except Exception as e:
        print(f"WARNING: review copy failed ({e})", flush=True)
        return None


def telegram_send_document(token, chat_id, file_path, caption, filename=None):
    boundary = "----shadowgaspboundary"
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    parts = [f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n"]
    if caption:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n")
    # Caller may override the name. Every rebuild produced a file called
    # <TITLE>_issue03.pdf, and a viewer that caches by filename then showed a stale
    # copy: the back-cover IMAGE from the same run read $4.99 while the document
    # opened at $2.99. A unique name per build removes the collision.
    filename = filename or os.path.basename(file_path)
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; "
                 f"filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n")
    header = "".join(parts).encode()
    with open(file_path, "rb") as f:
        body = header + f.read() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                  headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def telegram_send_photo(token, chat_id, file_path, caption):
    """Same multipart shape as telegram_send_document, but as a photo so it renders inline.

    A contact sheet is only useful if it appears in the chat -- sent as a document it is just
    another attachment to open, which defeats the point of glancing at 12 panels at once.
    """
    boundary = "----shadowgaspphoto"
    parts = [_form_field(boundary, "chat_id", str(chat_id))]
    if caption:
        parts.append(_form_field(boundary, "caption", caption))
    parts.append(
        "--" + boundary + "\r\n"
        'Content-Disposition: form-data; name="photo"; filename="'
        + os.path.basename(file_path) + '"\r\n'
        "Content-Type: image/jpeg\r\n\r\n")
    with open(file_path, "rb") as f:
        body = "".join(parts).encode() + f.read() + ("\r\n--" + boundary + "--\r\n").encode()
    req = urllib.request.Request(
        "https://api.telegram.org/bot" + token + "/sendPhoto", data=body, method="POST",
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def _form_field(boundary, name, value):
    return ("--" + boundary + "\r\n"
            'Content-Disposition: form-data; name="' + name + '"\r\n\r\n' + value + "\r\n")


def register_with_worker(worker_url, shared_secret, token, case_name, product_id, title,
                         video_id="", product_url="", pages="", flagged=None,
                         case_id="", issue_no="", hook=""):
    # video_id / product_url / pages are what the "Funnel to YouTube" button needs. They are
    # carried here because the case folder is deleted at the end of the run, so by the time the
    # button is tapped this KV record is the ONLY place the link between the comic and the
    # published short it came from still exists.
    req = urllib.request.Request(
        f"{worker_url.rstrip('/')}/register",
        data=json.dumps({
            "token": token, "case": case_name, "product_id": product_id, "title": title,
            "video_id": video_id, "product_url": product_url, "pages": str(pages),
            # Also feeds the durable per-comic index the Worker keeps for /links.
            "case_id": case_id, "issue_no": issue_no,
            # The selling line for the video description. The script writes one for exactly this
            # job and it was going unused, so every funnel fell back to generic copy that told
            # viewers the comic was the same material they had just watched free.
            "hook": hook,
            # Which panels OCR flagged, so /regen can check the names typed against reality
            # instead of dispatching a Kaggle kernel for a filename that does not exist.
            "flagged": flagged or [],
        }).encode(),
        headers={"Content-Type": "application/json", "X-Shared-Secret": shared_secret,
                     # Cloudflare answers 403 "error code: 1010" to urllib's default
                     # Python-urllib/3.x agent, so the request never reaches the Worker at
                     # all. Same bug already fixed twice on the notify path.
                     "User-Agent": "shadow-gasp-comic-pipeline"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return r.status



def _case_head(name):
    """A case's leading name: everything before a " / " qualifier or a trailing parenthetical.

    "Operation Nimrod / Iranian Embassy Siege 1980 (full long-form documentary)" and the
    "Operation Nimrod" a human types at /make are the same case; only this reduction sees that.
    """
    head = name.split("/")[0]
    head = re.sub(r"\(.*?\)", "", head)
    return " ".join(head.split()).strip().lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-dir", required=True)
    ap.add_argument("--case-id", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--target-pages", default="25")
    ap.add_argument("--price", default=None, help="Overrides the tier price derived from --target-pages")
    ap.add_argument("--video-id", default="",
                    help="YouTube id of the published short this case came from, if any. Enables "
                         "the 'Funnel to YouTube' button on the Telegram draft.")
    args = ap.parse_args()

    # Resolve the short this case came from, if the workflow did not pass one.
    #
    # --video-id is filled from pick_case's output, but pick_case is SKIPPED whenever a case is
    # named explicitly -- which is every manual /make. So POISONED GROUND arrived with no
    # 🔗 Funnel button even though its short (ula5Affft-w) has been live all along, and the
    # comic had nothing pointing at it. The ledger already knows; just look it up.
    # ⚠️ The match CANNOT be string equality. The ledger stores a descriptive case name --
    # "Operation Nimrod / Iranian Embassy Siege 1980 (full long-form documentary)" -- while a
    # build is dispatched with the short name a human types, "Operation Nimrod". Those are never
    # equal, so this lookup reported "no published short recorded" with BOTH Nimrod videos
    # sitting in the file. It only ever worked when the name happened to be typed identically,
    # which is why POISONED GROUND got a funnel button and Nimrod did not.
    #
    # So: exact first, then compare the case HEAD -- the leading name, before any " / " qualifier
    # or trailing parenthetical. Verified against all 74 videos in the ledger: no two DIFFERENT
    # cases share a head, so this cannot bind a comic to the wrong video. Two heads do carry
    # several videos each (Nimrod and David Koresh), and in both the entries are the same case's
    # teaser and its long-form -- take the most recently published, which is the fuller video and
    # the better thing to send a reader to.
    if not args.video_id:
        try:
            ledger = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "cases_used.json")
            entries = [c for c in json.load(open(ledger, encoding="utf-8"))["cases"]
                       if c.get("videoId")]
            want = " ".join((args.title or "").split()).strip().lower()
            hits = [c for c in entries if c.get("case", "").strip().lower() == want]
            how = "exact name"
            if not hits:
                hits = [c for c in entries if _case_head(c.get("case", "")) == _case_head(want)]
                how = "case name"
            if hits:
                pick = max(hits, key=lambda c: c.get("publishedAt", ""))
                args.video_id = pick["videoId"]
                extra = f", newest of {len(hits)}" if len(hits) > 1 else ""
                print(f"video for this case found in the ledger by {how}{extra}: "
                      f"{args.video_id} ({pick.get('publishedAt', '?')})", flush=True)
            else:
                print(f"no published video recorded for {args.title!r} -- no funnel button",
                      flush=True)
        except Exception as e:
            print(f"WARNING: could not look up the case's video ({e})", flush=True)

    comic_dir = args.case_dir
    scripts = glob.glob(os.path.join(comic_dir, "script_issue*.json"))
    if not scripts:
        raise SystemExit("No script_issueNN.json found")
    script_path = scripts[0]
    script = json.load(open(script_path, encoding="utf-8"))

    build_comic = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_comic.py")
    # ABSOLUTE path. script_path is built from --case-dir, which the workflow passes relative to
    # the repo root ("cases/<slug>/..."), but this runs with cwd=comic_dir -- so the relative
    # form resolved to cases/<slug>/cases/<slug>/script_issue01.json and the build died on a
    # missing file. Never surfaced before because no run had ever reached this step.
    subprocess.run([sys.executable, build_comic, "--script", os.path.abspath(script_path)],
                   cwd=comic_dir, check=True)

    pdf_path = os.path.join(comic_dir, script["output"])

    # Price the book that was actually DELIVERED, not the one that was asked for.
    #
    # target_pages is a floor plus a +50 panel buffer, so a request for 35 came back as 51 --
    # and the price was still taken from 35, selling a 51-page comic at the 35-page tier. Charge
    # for the highest tier the delivered page count actually reaches.
    # Count the PDF, not the script. The buyer downloads a 51-page file; the script's 46 "story
    # pages" exclude the cover, title page and back matter, and pricing off that number sold a
    # 51-page book at the 35-page tier. Whatever the buyer can page through is what they paid
    # for. Falls back to the story count if the PDF cannot be read.
    if args.price is None:
        delivered = len(script.get("pages", [])) or int(args.target_pages)
        source = "story pages"
        try:
            import fitz
            with fitz.open(pdf_path) as _d:
                delivered, source = _d.page_count, "PDF pages"
        except Exception as e:
            print(f"WARNING: could not count PDF pages ({e}); pricing off the script",
                  flush=True)
        tier = max((n for n in PAGE_PRICE_TIERS if n <= delivered),
                   default=min(PAGE_PRICE_TIERS))
        args.price = PAGE_PRICE_TIERS[tier]
        print(f"pricing: {delivered} {source} delivered (asked {args.target_pages}) "
              f"-> {tier}pp tier -> ${args.price}", flush=True)

    # The back cover PRINTS a price, and nothing was syncing it with what Gumroad charges: the
    # script writer invented "$2.99" from the schema example while the storefront sold the book
    # at $4.99. A buyer sees both. The tier price is only knowable after the PDF exists (it
    # depends on the page count), so patch the script and rebuild once -- the rebuild is
    # assembly only, no GPU and no API call.
    printed = (script.get("back_cover") or {}).get("price")
    wanted = f"${args.price}" if not str(args.price).startswith("$") else str(args.price)
    if printed and printed != wanted:
        script.setdefault("back_cover", {})["price"] = wanted
        with open(script_path, "w", encoding="utf-8") as fh:
            json.dump(script, fh, indent=2, ensure_ascii=False)
        print(f"back cover price {printed} -> {wanted}; rebuilding the PDF", flush=True)
        subprocess.run([sys.executable, build_comic, "--script", os.path.abspath(script_path)],
                       cwd=comic_dir, check=True)

    # Read the price back OUT of the finished PDF, so the caption reports what the file actually
    # renders rather than what the code believes it set. Six near-identical drafts went out
    # differing only in small details, with no way to tell them apart at a glance.
    rendered_price = "?"
    back_cover_png = None
    try:
        import fitz
        with fitz.open(pdf_path) as _doc:
            last = _doc[_doc.page_count - 1]
            text = last.get_text()
            _m = re.search(r"\$\s?\d+(?:\.\d{2})?", text)
            rendered_price = _m.group(0) if _m else "none found"
            # Rasterise the back cover and ship it too. Extracted text can disagree with what a
            # reader actually sees -- a stale copy, a second price drawn elsewhere, a glyph that
            # does not extract -- and the only way to settle that is to look at the page.
            back_cover_png = os.path.join(comic_dir, "_back_cover_check.png")
            last.get_pixmap(dpi=110).save(back_cover_png)
        print(f"back cover renders: {rendered_price}", flush=True)
        print(f"all $ amounts on the last page: {re.findall(r'[$]s?[0-9.]+', text)}", flush=True)
    except Exception as e:
        print(f"WARNING: could not read the price back from the PDF ({e})", flush=True)

    cover_path = os.path.join(comic_dir, "panels", "cover.jpg")

    description = build_store_description(script)
    # Gumroad rejects any tag of 20 characters or more, and the whole product create call fails
    # with it -- a finished 51-page book was refused over one keyword. The model writes these
    # freely ("hanford nuclear reservation"), so they have to be trimmed here rather than
    # trusted. Shorten on a word boundary where possible, then drop anything still too long,
    # de-duplicated and case-insensitive so trimming cannot produce two identical tags.
    tags, seen = [], set()
    for raw in script.get("keywords", "").split(","):
        t = raw.strip()
        while len(t) >= 20 and " " in t:
            t = t.rsplit(" ", 1)[0].strip()
        if t and len(t) < 20 and t.lower() not in seen:
            seen.add(t.lower())
            tags.append(t)
    tags = tags[:5]
    print(f"gumroad tags: {tags}", flush=True)

    # Purpose-built social promo graphic (hook-led, not a comic page). Built
    # here at build time because the case folder is deleted after this run --
    # it rides along as a Gumroad preview so it can be fetched again at
    # publish time and handed over for posting.
    panels = os.path.join(comic_dir, "panels")
    hook = script.get("promo_hook") or script.get("tagline", "")
    sub = "documentary comic"

    # Three different shapes for three different jobs. cover.jpg stays 9:16
    # because that's the comic's actual front cover page inside the PDF — but
    # Gumroad's product hero is wide and its storefront tile is square, so
    # reusing the portrait cover for those just gets it cropped badly.
    promo_path = os.path.join(comic_dir, "promo.jpg")
    banner_path = None
    try:
        import gen_promo_card
        promo_path = gen_promo_card.build(pdf_path, promo_path)
    except Exception as e:
        print(f"WARNING: promo card build failed ({e}) — continuing without it")
        promo_path = None

    # Square storefront tile, styled as a comic cover. A shop tile for a comic
    # IS its cover -- series banner, title, issue number. A bare atmospheric
    # image reads as a documentary still rather than something purchasable.
    thumb_path = cover_path
    try:
        import gen_store_tile
        thumb_path = gen_store_tile.build(pdf_path, os.path.join(comic_dir, "store_tile.jpg"))
    except Exception as e:
        print(f"WARNING: store tile build failed ({e}) — falling back to cover")

    # Product-page hero: the comic shown as an object, not a mood image.
    try:
        import gen_store_hero
        # Pass the script through: the hero's side panel carries the issue number, format and
        # hook -- the things the cover art cannot say at gallery size.
        cover_path = gen_store_hero.build(
            pdf_path, os.path.join(comic_dir, "store_hero.jpg"),
            meta={"series": script.get("series"), "title": script.get("title"),
                  "issue_no": script.get("issue_no"), "hook": script.get("promo_hook")})
    except Exception as e:
        print(f"WARNING: store hero build failed ({e}) — falling back")
        if banner_path and os.path.exists(banner_path):
            cover_path = banner_path

    previews = ([promo_path] if promo_path else []) + pick_preview_panels(comic_dir, script)
    # The buyer-facing name, used for the Gumroad product AND for the line written into the
    # video description. Registering args.title instead put the CASE name into both -- /funnel
    # was about to write "READ THE COMIC: Hanford Nuclear Reservation contamination cover-up"
    # into a public description instead of the comic's actual title.
    product_name = f"{script['series']} #{script['issue_no']}: {script['title']}"
    product_id = stage_draft(
        name=product_name,
        pdf_path=pdf_path, cover_path=cover_path, price=args.price,
        description=description, tags=tags, category=DEFAULT_CATEGORY,
        preview_paths=previews, thumbnail_path=thumb_path,
        permalink=slugify(script["title"]),
    )
    print(f"Staged Gumroad draft: {product_id}")

    # Custom landing page, built from the same script data, using the
    # product's own just-uploaded cover URL. Only ever published if Gumroad's
    # own sanitizer reports it clean -- a broken landing page would make the
    # product unpurchasable, worse than just leaving the default page.
    try:
        import gen_landing_page
        cover_data = gumroad(["products", "view", product_id])
        cover_url = (cover_data.get("product", cover_data)).get("thumbnail_url")
        if cover_url:
            landing_path = os.path.join(comic_dir, "landing.html")
            with open(landing_path, "w", encoding="utf-8") as f:
                f.write(gen_landing_page.build_html(script, cover_url))
            ok, err = gen_landing_page.publish_if_safe(product_id, landing_path)
            print(f"Landing page: {'published' if ok else 'SKIPPED (' + str(err) + ')'}")
    except Exception as e:
        print(f"WARNING: landing page step failed ({e}) — default product page stays in place")

    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    # Telegram's bot API refuses documents over 50MB. Gumroad gets the untouched 300 DPI print
    # master either way; this only affects the review copy that comes to the phone. An 80-page
    # issue is ~114MB, so without this the draft simply never arrives and the comic looks like
    # it failed -- which is exactly what happened on Heaven's Gate.
    send_path, note = pdf_path, "full comic"
    if os.path.getsize(pdf_path) > TELEGRAM_DOC_LIMIT:
        preview = make_review_copy(pdf_path)
        if preview:
            send_path = preview
            note = "full comic, preview quality (Gumroad has the 300dpi master)"
        else:
            note = "PREVIEW BUILD FAILED - read it on Gumroad"

    import hashlib as _hl, time as _t
    _digest = _hl.sha1(open(send_path, "rb").read()).hexdigest()[:8]
    _stamp = _t.strftime("%H%M%S")
    _unique = f"{os.path.splitext(os.path.basename(send_path))[0]}_{_stamp}_{_digest}.pdf"
    print(f"sending {send_path} as {_unique} "
          f"({os.path.getsize(send_path)/1e6:.1f}MB, sha1 {_digest})", flush=True)
    result = telegram_send_document(
        bot_token, chat_id, send_path, filename=_unique,
        caption=(f"{args.title} — issue {script.get('issue_no', '?')} — {note}\n"
                 f"back cover prints {rendered_price} · Gumroad ${args.price}\n"
                 "(approval buttons in the next message)"),
    )
    if not result.get("ok"):
        raise SystemExit(f"Telegram send failed: {result}")
    print(f"Delivered PDF to Telegram, message_id={result['result']['message_id']}")

    # The back cover as an IMAGE, straight after the PDF, so the price on the page can be
    # checked at a glance without opening a 40MB file or trusting a log line.
    if back_cover_png and os.path.exists(back_cover_png):
        try:
            telegram_send_photo(bot_token, chat_id, back_cover_png,
                                caption=f"back cover of the PDF just sent — reads {rendered_price}")
        except Exception as e:
            print(f"WARNING: could not send the back-cover check image ({e})", flush=True)

    # A second, independent copy of the script itself.
    #
    # The script is the expensive artefact -- it costs a real API call and it is what every
    # rebuild and every art regeneration is derived from. Until now it lived in exactly two
    # places, both of which lose it: cases/, which is rm -rf'd at the end of every run, and the
    # Worker's KV, which is private but was expiring. It is never committed, because this repo
    # is public and the script IS the product. Shipping it to the same private Telegram chat
    # that already receives the PDF costs nothing and means a script can never be lost to an
    # infrastructure failure.
    try:
        pp_path = os.path.join(comic_dir, "panel_prompts.json")
        bundle = os.path.join(comic_dir, f"{args.case_id}_script_bundle.json")
        with open(bundle, "w", encoding="utf-8") as f:
            json.dump({"case": args.title, "case_id": args.case_id,
                       "target_pages": args.target_pages, "video_id": args.video_id,
                       "script": script,
                       "panel_prompts": json.load(open(pp_path, encoding="utf-8"))
                       if os.path.exists(pp_path) else None},
                      f, ensure_ascii=False, indent=2)
        r2 = telegram_send_document(
            bot_token, chat_id, bundle,
            caption=f"{args.title} — script + panel prompts (rebuild from this without paying "
                    f"for generation again)")
        print("Delivered script bundle to Telegram" if r2.get("ok")
              else f"WARNING: script bundle send failed: {r2}")
    except Exception as e:
        # Never fatal: the comic itself already shipped, and losing the backup copy must not
        # fail a build that otherwise succeeded.
        print(f"WARNING: could not deliver the script bundle ({e}) -- not fatal")

    # Minted before the sheets are sent, because the /regen instruction in their caption has to
    # quote it -- it is how the Worker knows which book a re-roll request belongs to.
    approval_token = secrets.token_urlsafe(8)

    # OCR contact sheets: which panels the scan thinks carry text, for eyeballing against the
    # PDF. Nothing has been regenerated -- the decision is the reviewer's, sent back as /regen.
    #
    # TWO reasons a panel is offered for re-roll, and both have to reach the chat or the reviewer
    # cannot act on them in one pass: OCR saw letterforms, or the tonal sweep measured the panel
    # dark and flat. The dark set is why an entire book of full-bleed splashes once shipped as
    # black slabs -- nothing looked, and nothing said so. Both feed the SAME `flagged` list the
    # Worker validates /regen against, so one /regen can name panels from either sheet and they
    # all re-roll in a single rebuild.
    flagged = []
    for label, source, prefix, icon, why in (
            ("OCR flagged", "ocr_flagged.json", "ocr_flagged_sheet", "\U0001f50d",
             "these carry readable text"),
            ("dark or flat", "dark_panels.json", "dark_sheet", "\U0001f311",
             "these measured dark or flat — no picture, or nearly none")):
        try:
            names = []
            fp = os.path.join(comic_dir, source)
            if os.path.exists(fp):
                names = json.load(open(fp, encoding="utf-8"))
            for nm in names:
                if nm not in flagged:
                    flagged.append(nm)
            sheets = sorted(glob.glob(os.path.join(comic_dir, prefix + "*.jpg")))
            # Show REAL panel names in the example, not p05_3/p06_1 placeholders -- on a sheet of
            # thirteen the reviewer wants to copy the line and edit it, not retype it.
            eg = " ".join(x.replace(".jpg", "") for x in names[:2]) or "p05_3 p06_1"
            for n, sheet in enumerate(sheets, 1):
                # The command goes on EVERY sheet, not just the first: you scroll to sheet 4, spot
                # a bad panel there, and the instruction has to be under your thumb, not 3
                # messages up.
                cap = (f"{icon} {label}: {len(names)} panel(s) — sheet {n}/{len(sheets)}. "
                       f"{why}. Nothing was regenerated.\n"
                       "Re-roll the bad ones (labels are the panel names, and one /regen can "
                       "mix panels from any sheet):\n"
                       f"/regen {approval_token} {eg}")
                telegram_send_photo(bot_token, chat_id, sheet, caption=cap)
            if sheets:
                print(f"sent {len(sheets)} {label} contact sheet(s) to Telegram", flush=True)
        except Exception as e:
            print(f"WARNING: could not send {label} contact sheets ({e}) -- not fatal", flush=True)
    register_with_worker(
        worker_url=os.environ["WORKER_URL"],
        shared_secret=os.environ["WORKER_SHARED_SECRET"],
        token=approval_token,
        case_name=args.title,
        product_id=product_id,
        title=product_name,
        video_id=args.video_id,
        flagged=flagged,
        case_id=args.case_id,
        issue_no=script.get("issue_no", ""),
        hook=script.get("promo_hook", ""),
        # Same permalink stage_draft() just set, so this is the buyer-facing URL, not a
        # random Gumroad slug. Still a DRAFT url at this point -- the funnel job refuses to
        # put it in a public description until the product is actually published.
        product_url=f"https://shadowgasp.gumroad.com/l/{slugify(script['title'])}",
        pages=args.target_pages,
    )
    print(f"Registered with Worker, token={approval_token}")


if __name__ == "__main__":
    main()
