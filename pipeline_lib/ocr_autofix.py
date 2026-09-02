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

    # Move aside, never delete.
    #
    # This used to os.remove() each flagged panel before regenerating it, which was survivable
    # only while a failed fix-kernel aborted the whole build. Once that step was made
    # non-fatal -- so an optional retry could not destroy a finished book -- the delete became
    # SILENT DATA LOSS instead: the fix kernel errored, 59 panels stayed gone, and the run
    # reported success while shipping a 51-page comic full of "art pending" placeholders.
    # The original art is imperfect but real, and it always beats a placeholder.
    backup_dir = os.path.join(panels_dir, "_ocr_backup")
    os.makedirs(backup_dir, exist_ok=True)
    for p in flagged:
        by_file[p["file"]]["prompt"] = p["prompt"] + GENERIC_REINFORCEMENT
        live = os.path.join(panels_dir, p["file"])
        if os.path.exists(live):
            os.replace(live, os.path.join(backup_dir, os.path.basename(p["file"])))

    json.dump(prompts, open(prompts_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    retry_panels = [by_file[p["file"]] for p in flagged]
    try:
        failed = gk.run_batch(args.kaggle_user, f"{args.slug}-ocrfix", retry_panels, panels_dir,
                              seed_base=9000)
    except Exception as e:
        print(f"WARNING: the OCR fix kernel failed ({e}) -- restoring the originals",
              file=sys.stderr)
        failed = [p["file"] for p in retry_panels]
    if failed:
        print(f"WARNING: {len(failed)} panels not regenerated: {failed}", file=sys.stderr)

    # Restore anything the retry did not actually replace, whatever went wrong above.
    restored = 0
    for p in retry_panels:
        live = os.path.join(panels_dir, p["file"])
        keep = os.path.join(backup_dir, os.path.basename(p["file"]))
        if not os.path.exists(live) and os.path.exists(keep):
            os.replace(keep, live)
            restored += 1
    if restored:
        print(f"restored {restored} original panel(s) the retry failed to replace", flush=True)

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
