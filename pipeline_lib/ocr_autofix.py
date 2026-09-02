"""OCR-check every generated panel; any panel with detectable text gets its
prompt reinforced with a stronger generic no-text clause and is regenerated
ONCE via a second Kaggle batch. This is the unattended version of the manual
fix loop used for issue 01 (D.B. Cooper) — it won't diagnose *why* a specific
scene keeps inviting text the way a human pass would, but it catches most of
what plain "no text" alone misses.
"""
import argparse
import json
import os
import sys

from rapidocr_onnxruntime import RapidOCR

import gen_flux_kaggle as gk

GENERIC_REINFORCEMENT = (
    " Every object in this scene must be completely blank, unmarked, or too "
    "worn/blurred to read — no signage, no papers with visible writing, no "
    "labels, no screens with text, nothing resembling letters or words of any "
    "kind, anywhere in the frame."
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-dir", required=True)
    ap.add_argument("--kaggle-user", default=os.environ.get("KAGGLE_USERNAME"))
    ap.add_argument("--slug", required=True)
    args = ap.parse_args()

    panels_dir = os.path.join(args.case_dir, "panels")
    prompts_path = os.path.join(args.case_dir, "panel_prompts.json")
    prompts = json.load(open(prompts_path, encoding="utf-8"))

    ocr = RapidOCR()
    flagged = []
    for p in prompts:
        path = os.path.join(panels_dir, p["file"])
        if not os.path.exists(path):
            continue
        result, _ = ocr(path)
        texts = [r[1] for r in result if len(r[1].strip()) >= 2] if result else []
        if texts:
            flagged.append(p)
            print(f"FLAGGED {p['file']}: {texts}")

    if not flagged:
        print("OCR check clean, no panels flagged")
        json.dump([], open(os.path.join(args.case_dir, "ocr_flagged.json"), "w"), indent=2)
        return

    # REPORT ONLY. This used to delete each flagged panel and re-roll it on a second Kaggle
    # kernel -- a fix-kernel that has never once succeeded, for a detector that misses the actual
    # defect (FLUX draws squiggles, and OCR does not read squiggles as text). The combination
    # cost a kernel launch per run, flagged 26% of panels, fixed none of them, and destroyed 59
    # panels the one time the delete was allowed to stick.
    #
    # So: flag, contact-sheet, and hand the judgement to the human who is already reviewing the
    # PDF. Regeneration happens only when they ask for it, per panel, via /regen.
    names = [p["file"] for p in flagged]
    json.dump(names, open(os.path.join(args.case_dir, "ocr_flagged.json"), "w"), indent=2)
    sheets = build_contact_sheets(panels_dir, names, args.case_dir)
    print(f"{len(flagged)} panels flagged -> {len(sheets)} contact sheet(s); no art was touched",
          flush=True)


def build_contact_sheets(panels_dir, names, out_dir, per_sheet=12, cols=4, cell=430):
    """Tile the flagged panels into a few labelled sheets.

    59 flagged panels is 6 Telegram albums at the 10-image cap, which is unreviewable next to a
    51-page PDF. Twelve to a sheet makes it ~5 images, each panel captioned with the filename to
    type into /regen.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("WARNING: Pillow missing, no contact sheets", flush=True)
        return []

    sheets = []
    for idx in range(0, len(names), per_sheet):
        batch = names[idx:idx + per_sheet]
        rows = (len(batch) + cols - 1) // cols
        label_h = 26
        sheet = Image.new("RGB", (cols * cell, rows * (cell + label_h)), (18, 18, 18))
        draw = ImageDraw.Draw(sheet)
        for i, fn in enumerate(batch):
            path = os.path.join(panels_dir, fn)
            x, y = (i % cols) * cell, (i // cols) * (cell + label_h)
            try:
                im = Image.open(path).convert("RGB")
                im.thumbnail((cell - 8, cell - 8))
                sheet.paste(im, (x + 4, y + 4))
            except Exception:
                draw.rectangle([x + 4, y + 4, x + cell - 4, y + cell - 4], outline=(90, 90, 90))
            draw.text((x + 6, y + cell + 4), fn, fill=(235, 235, 235))
        out = os.path.join(out_dir, f"ocr_flagged_sheet{idx // per_sheet + 1}.jpg")
        sheet.save(out, "JPEG", quality=88)
        sheets.append(out)
    return sheets
