"""Comic PDF -> fixed-layout EPUB 3 (one full page per screen), for Gumroad buyers.

    python pipeline_lib/pdf_to_epub.py <comic.pdf> <out.epub> --title "SHADOW GASP #03: POISONED GROUND" --id <product-id>

A comic is pictures laid out on pages, so the only faithful EPUB is a pre-paginated one: every PDF
page becomes a JPEG shown edge to edge on its own screen, exactly as printed. Reflowable EPUB would
tear the panels and lettering apart. Apple Books, Kobo, Google Play Books and most EPUB 3 readers
honour fixed layout.

The identifier is derived from the Gumroad product id, so a rebuilt EPUB stays the "same book" in a
reader's library instead of appearing as a duplicate. The file passes epubcheck (store workflows run
it where Java is available).
"""
import argparse
import datetime
import html
import io
import os
import uuid
import zipfile

import fitz  # PyMuPDF
from PIL import Image

PAGE_HEIGHT = 2000   # px; sharp on tablets, ~0.3-0.6 MB a page
JPEG_QUALITY = 85
AUTHOR = "Shadow Gasp"
LANG = "en"


def _render(page):
    zoom = PAGE_HEIGHT / page.rect.height
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    return buf.getvalue(), img.width, img.height


def _page_xhtml(n, w, h, title):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{LANG}" lang="{LANG}">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width={w}, height={h}"/>
<title>{html.escape(title)} - page {n}</title>
<style>html,body{{margin:0;padding:0;width:{w}px;height:{h}px;overflow:hidden;background:#000}}
img{{display:block;width:{w}px;height:{h}px}}</style>
</head>
<body><img src="images/p{n:03d}.jpg" alt="Page {n}"/></body>
</html>
"""


def build(pdf_path, out_path, title, book_id, description=""):
    doc = fitz.open(pdf_path)
    ident = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, 'shadowgasp-gumroad:' + book_id)}"
    modified = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest, spine = [], []
    tmp = out_path + ".part"
    with zipfile.ZipFile(tmp, "w") as z:
        # The mimetype entry must come first and be stored uncompressed.
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>
""", compress_type=zipfile.ZIP_DEFLATED)
        first_size = None
        for i, page in enumerate(doc, 1):
            data, w, h = _render(page)
            first_size = first_size or (w, h)
            # JPEGs are already compressed; storing them keeps the build fast.
            z.writestr(f"OEBPS/images/p{i:03d}.jpg", data, compress_type=zipfile.ZIP_STORED)
            z.writestr(f"OEBPS/p{i:03d}.xhtml", _page_xhtml(i, w, h, title), compress_type=zipfile.ZIP_DEFLATED)
            props = ' properties="cover-image"' if i == 1 else ""
            manifest.append(f'<item id="img{i:03d}" href="images/p{i:03d}.jpg" media-type="image/jpeg"{props}/>')
            manifest.append(f'<item id="p{i:03d}" href="p{i:03d}.xhtml" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="p{i:03d}"/>')
        pages = doc.page_count
        start = 3 if pages > 3 else 1   # cover, title page, then the story
        z.writestr("OEBPS/nav.xhtml", f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{LANG}" lang="{LANG}">
<head><meta charset="UTF-8"/><title>{html.escape(title)}</title></head>
<body>
<nav epub:type="toc" id="toc"><h1>Contents</h1><ol>
<li><a href="p001.xhtml">Cover</a></li>
<li><a href="p{start:03d}.xhtml">Start reading</a></li>
</ol></nav>
<nav epub:type="landmarks" hidden="hidden"><ol>
<li><a epub:type="cover" href="p001.xhtml">Cover</a></li>
<li><a epub:type="bodymatter" href="p{start:03d}.xhtml">Start reading</a></li>
</ol></nav>
</body>
</html>
""", compress_type=zipfile.ZIP_DEFLATED)
        w, h = first_size
        desc = f"<dc:description>{html.escape(description)}</dc:description>" if description else ""
        z.writestr("OEBPS/content.opf", f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="{LANG}"
  prefix="rendition: http://www.idpf.org/vocab/rendition/#">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">{ident}</dc:identifier>
<dc:title>{html.escape(title)}</dc:title>
<dc:creator>{AUTHOR}</dc:creator>
<dc:publisher>{AUTHOR}</dc:publisher>
<dc:language>{LANG}</dc:language>
{desc}
<meta property="dcterms:modified">{modified}</meta>
<meta property="rendition:layout">pre-paginated</meta>
<meta property="rendition:orientation">portrait</meta>
<meta property="rendition:spread">none</meta>
<meta name="cover" content="img001"/>
<meta name="original-resolution" content="{w}x{h}"/>
</metadata>
<manifest>
<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
{chr(10).join(manifest)}
</manifest>
<spine>
{chr(10).join(spine)}
</spine>
</package>
""", compress_type=zipfile.ZIP_DEFLATED)
    os.replace(tmp, out_path)
    return out_path, pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("out")
    ap.add_argument("--title", required=True)
    ap.add_argument("--id", required=True, help="Gumroad product id (makes the EPUB identifier stable)")
    ap.add_argument("--description", default="")
    a = ap.parse_args()
    path, pages = build(a.pdf, a.out, a.title, a.id, a.description)
    print(f"epub: {path}  {pages} pages  {os.path.getsize(path) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
