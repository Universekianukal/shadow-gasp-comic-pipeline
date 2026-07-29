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
        return

    print(f"{len(flagged)} panels flagged, rewriting prompts and regenerating once...")
    by_file = {p["file"]: p for p in prompts}
    for p in flagged:
        by_file[p["file"]]["prompt"] = p["prompt"] + GENERIC_REINFORCEMENT
        os.remove(os.path.join(panels_dir, p["file"]))

    json.dump(prompts, open(prompts_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    retry_panels = [by_file[p["file"]] for p in flagged]
    failed = gk.run_batch(args.kaggle_user, f"{args.slug}-ocrfix", retry_panels, panels_dir, seed_base=9000)
    if failed:
        print(f"WARNING: {len(failed)} panels still failed after retry: {failed}", file=sys.stderr)

    still_flagged = []
    for p in retry_panels:
        path = os.path.join(panels_dir, p["file"])
        if not os.path.exists(path):
            continue
        result, _ = ocr(path)
        texts = [r[1] for r in result if len(r[1].strip()) >= 2] if result else []
        if texts:
            still_flagged.append(p["file"])
    if still_flagged:
        print(f"NOTE: {len(still_flagged)} panels still show OCR text after one retry "
              f"(accepted as-is, unattended run): {still_flagged}", file=sys.stderr)
    else:
        print("All previously flagged panels are clean after retry")


if __name__ == "__main__":
    main()
