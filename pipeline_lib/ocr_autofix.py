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

HERE = os.path.dirname(os.path.abspath(__file__))

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
    scanned = 0
    for p in prompts:
        path = os.path.join(panels_dir, p["file"])
        if not os.path.exists(path):
            continue
        scanned += 1
        result, _ = ocr(path)
        texts = [r[1] for r in result if len(r[1].strip()) >= 2] if result else []
        if texts:
            flagged.append(p)
            print(f"FLAGGED {p['file']}: {texts}")

    # A step that silently does nothing is worse than one that fails: this whole script once
    # ran for 0.3s and reported success because an edit dropped its __main__ block, and
    # continue-on-error hid it. Say what was actually looked at.
    print(f"OCR scanned {scanned}/{len(prompts)} panels", flush=True)
    if prompts and not scanned:
        print(f"WARNING: scanned NOTHING -- no panel files found under {panels_dir}",
              file=sys.stderr, flush=True)

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
    # The note says WHY this panel is up for re-roll. The dark sweep in gen_flux_kaggle writes
    # its own sheets through the same builder, and the reviewer has to be able to tell the two
    # judgements apart at a glance: letterforms in the art is a different call from a page that
    # came out flat.
    sheets = gk.build_contact_sheets(
        panels_dir, [(p["file"], "text detected") for p in flagged],
        args.case_dir, "ocr_flagged_sheet")
    print(f"{len(flagged)} panels flagged -> {len(sheets)} contact sheet(s); no art was touched",
          flush=True)


if __name__ == "__main__":
    main()
