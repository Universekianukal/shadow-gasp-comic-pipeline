"""Generic FLUX-on-Kaggle panel generator (works from any case directory
containing panel_prompts.json), adapted from the shadow_gasp local pipeline.

Requires KAGGLE_USERNAME / KAGGLE_API_TOKEN env vars (set as GitHub Actions
secrets) -- kaggle==2.2.2's CLI auths via KAGGLE_API_TOKEN, not the legacy
KAGGLE_USERNAME/KAGGLE_KEY pair (see pipeline.yml's Kaggle-auth comment).
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import sys
import time

DIMS = {
    "LANDSCAPE": (1280, 720),
    "SPLASH": (720, 1280),
    "PORTRAIT": (720, 1280),
    "SQUARE": (1024, 1024),
}

# ⚠️ THE CEILING FLUX ACTUALLY RENDERS AT — not the size the page wants.
#
# spec_panels solves the layout in inches and writes target_px at DPI=300, the press standard.
# For a full-bleed splash on this trim that is 2064x3128 = 6.46 MP, and until this cap existed
# it went straight into the pipeline. FLUX.1-schnell is trained around 1 MP; six and a half
# times that, at 4 steps and guidance 0, does not degrade gracefully -- it collapses. Measured
# on the Operation Nimrod build (run 33692626677), luminance out of 255 across all 288 panels:
#
#     6.46 MP   n= 13   mean 17.0    10 of 13 under 20    <-- EVERY full-bleed page in the book
#     2.21 MP   n= 21   mean 67.1     2 of 21
#     1.71 MP   n= 37   mean 46.1     8 of 37
#     0.84 MP   n= 66   mean 63.6     1 of 66
#     0.55 MP   n=104   mean 57.4     5 of 104
#
# All 13 splashes came back near-black; four of them measured a standard deviation of ~1.1,
# which is a flat dark slab with no picture in it at all. The prompts were innocent -- p16's
# reads "released hostage emerging from embassy doorway into daylight" and returned a grey
# rectangle. It is the resolution, and nothing else.
#
# So: generate inside the model's range, then upscale to target_px on the way down (see
# run_batch). 1.6 MP puts a tall splash at 1024x1552, within a hair of FLUX's native
# 1024x1536 portrait, and leaves every measured-healthy size essentially untouched (the
# largest, 2064x1072, shrinks 4%). The cost is resolution on splashes only: a 2x upscale
# lands near 150 DPI at printed size, against ~210 DPI for the shipped Heaven's Gate art.
# Softer than ideal, and incomparably better than a black page.
MAX_GEN_PX = 1_600_000
GEN_QUANT = 16          # FLUX wants both axes on a multiple of 16

# What counts as a degenerate panel, and how many times the kernel re-rolls one. Defined here
# and interpolated into KERNEL_TEMPLATE so the GPU-side re-roll and the host-side report below
# cannot drift into disagreeing about what "broken" means. The reasoning is in the template.
MIN_MEAN = 6.0
MIN_SD = 35.0
ATTEMPTS = 3


def gen_size(w, h):
    """The size to actually render (w, h) at, capped to MAX_GEN_PX at the same aspect."""
    if w * h <= MAX_GEN_PX:
        return w, h
    s = (MAX_GEN_PX / float(w * h)) ** 0.5
    return (max(GEN_QUANT, int(round(w * s / GEN_QUANT)) * GEN_QUANT),
            max(GEN_QUANT, int(round(h * s / GEN_QUANT)) * GEN_QUANT))

KERNEL_TEMPLATE = '''import os, sys, subprocess, json
def pip(*a): subprocess.run([sys.executable,"-m","pip","install","-q",*a], check=False)
pip("torch==2.4.1","torchvision==0.19.1","--index-url","https://download.pytorch.org/whl/cu121")
pip("diffusers==0.32.2","transformers==4.46.3","accelerate","sentencepiece","protobuf","bitsandbytes")

import torch, numpy as np
from huggingface_hub import login
login(token=os.environ.get("HF_TOKEN","{hf_token}"))
print("torch", torch.__version__, "cuda", torch.cuda.is_available(), flush=True)

from diffusers import FluxPipeline, FluxTransformer2DModel, BitsAndBytesConfig as DBnb
from transformers import T5EncoderModel, BitsAndBytesConfig as TBnb
repo="black-forest-labs/FLUX.1-schnell"
nf4=dict(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16)

tf=FluxTransformer2DModel.from_pretrained(repo, subfolder="transformer",
     quantization_config=DBnb(**nf4), torch_dtype=torch.float16)
te=T5EncoderModel.from_pretrained(repo, subfolder="text_encoder_2",
     quantization_config=TBnb(**nf4), torch_dtype=torch.float16)
pipe=FluxPipeline.from_pretrained(repo, transformer=tf, text_encoder_2=te, torch_dtype=torch.float16)
pipe.enable_model_cpu_offload()

# House style from trained weights rather than from prompt wording.
#
# The prompt writer can drift -- one book came out flat pale grey because its prompts omitted
# the contrast clause -- but a LoRA applies the look regardless of how the prompt is phrased.
# Loaded BEFORE cpu offload matters: diffusers wants the adapter on the assembled pipeline.
#
# Deliberately non-fatal. bitsandbytes 4-bit quantisation and PEFT adapters do not always
# compose, and a book with the base FLUX look is worth far more than a run that dies at panel
# zero. If it fails to load, the log says so loudly and generation continues unstyled.
LORA_REPO = "{lora_repo}"
LORA_TRIGGER = "{lora_trigger}"
LORA_OK = False
if LORA_REPO:
    try:
        from huggingface_hub import hf_hub_download
        _p = hf_hub_download(LORA_REPO, "sgnoir_lora_v1.safetensors",
                             token=os.environ.get("HF_TOKEN", "{hf_token}"))
        pipe.load_lora_weights(_p)
        LORA_OK = True
        print("LORA LOADED", LORA_REPO, flush=True)
    except Exception as e:
        print("LORA LOAD FAILED, continuing with base FLUX:", repr(e), flush=True)
print("PIPE READY", flush=True)

PANELS = {panels_json}
open("/kaggle/working/_prompts_fp.txt","w").write("{prompts_fp}")

# A degenerate panel is not black, which is why the old guard never caught one.
#
# The old test printed a warning at mean < 5 and fired ZERO times on the run where all 13
# full-bleed splashes came back unusable: they landed at mean 7-39, comfortably past a
# threshold set for a NaN tensor rather than for the failure that actually happens.
#
# ⭐ THE TEST IS TONAL SPREAD, NOT BRIGHTNESS. This is a noir book -- darkness is the house
# style, and plenty of perfectly good panels are dark (one measured mean 12.9). Brightness
# cannot tell "night" from "broken", but variance can. Measured on that run, standard
# deviation out of 255:
#
#     13 collapsed splashes    sd 1.1 - 26.1   (four at ~1.1: a solid rectangle, no picture)
#     34 good panels           sd 48.3 - 115.8
#
# A gap of 22 points with nothing in it. 35 sits in the middle of that gap. The mean test is
# kept only as a backstop for a genuinely black or blown-out frame, well below any real art.
MIN_MEAN = {min_mean}
MIN_SD   = {min_sd}
ATTEMPTS = {attempts}

for i, p in enumerate(PANELS):
    name, w, h, prompt = p["out"], p["w"], p["h"], p["prompt"]
    # Trigger only when the adapter is really in memory -- appending it to a base-model
    # run just wastes CLIP tokens on a phrase that means nothing.
    p_text = prompt + (", " + LORA_TRIGGER if (LORA_OK and LORA_TRIGGER) else "")
    best = None
    for attempt in range(ATTEMPTS):
        try:
            # A re-roll has to move the seed. Re-rendering the same prompt at the same seed
            # reproduces the same picture, which is not a retry.
            img=pipe(p_text, num_inference_steps=4, guidance_scale=0.0, height=h, width=w,
                     max_sequence_length=256,
                     generator=torch.Generator("cpu").manual_seed({seed_base}+i+100000*attempt)).images[0]
        except Exception as e:
            print("FAILED", name, repr(e), flush=True)
            break
        a=np.asarray(img.convert("L"), dtype=np.float32)
        m, sd = float(a.mean()), float(a.std())
        if best is None or sd > best[2]:
            best = (img, m, sd)
        if m >= MIN_MEAN and sd >= MIN_SD:
            break
        print("SUSPECT", name, "attempt", attempt+1, "mean", round(m,1), "sd", round(sd,1),
              "-- re-rolling", flush=True)
    torch.cuda.empty_cache()
    if best is None:
        continue
    # Save the best attempt even when all three are degenerate: a soft page is recoverable by
    # a targeted /regen, a missing one makes build_comic rule up a hole. The host repeats this
    # measurement on the downloaded file and prints the exact /regen line to paste.
    img, m, sd = best
    img.save(f"/kaggle/working/{{name}}", quality=92)
    bad = " <-- DEGENERATE, all %d attempts" % ATTEMPTS if (m < MIN_MEAN or sd < MIN_SD) else ""
    print("DONE", name, "meanpix", round(m,1), "sd", round(sd,1), bad, flush=True)
print("ALL DONE", flush=True)
'''


def build_panels_for_kernel(panels):
    """The exact {out,w,h,prompt} list the kernel renders from.

    Shared by run_batch and the recovery fingerprint so both sides agree byte for byte -- if
    they disagree about a fallback size, the fingerprint never matches and recovery silently
    never fires.
    """
    out = []
    for p in panels:
        w, h = target_px(p)
        gw, gh = gen_size(w, h)
        out.append({"out": p["file"].replace("/", "_"), "w": gw, "h": gh, "prompt": p["prompt"]})
    return out


def target_px(p):
    """The size the PAGE wants, at 300 DPI -- what the art is upscaled to after generation."""
    tp = p.get("target_px")
    if isinstance(tp, (list, tuple)) and len(tp) == 2 and all(isinstance(v, int) for v in tp):
        return tp[0], tp[1]
    return DIMS[p["shape"]]


def panels_from_kernel_source(kernel_id):
    """The exact PANELS list a previous kernel rendered, read back out of its own source.

    Stronger evidence than any stamp we wrote ourselves, and it works retroactively on kernels
    pushed before stamping existed.
    """
    try:
        d = tempfile.mkdtemp(prefix="kaggle_src_")
        subprocess.run(["kaggle", "kernels", "pull", kernel_id, "-p", d],
                       check=True, capture_output=True, timeout=240)
        src = ""
        for fn in os.listdir(d):
            if fn.endswith(".py"):
                src = open(os.path.join(d, fn), encoding="utf-8").read()
                break
        m = re.search(r"PANELS = (\[.*?\])" + chr(10), src, re.S)
        return json.loads(m.group(1)) if m else []
    except Exception:
        return []


def fingerprint_from_kernel_source(kernel_id):
    """Fingerprint a legacy kernel by reading the prompt list baked into its source."""
    prev = panels_from_kernel_source(kernel_id)
    return prompts_fingerprint(prev) if prev else ""


def prompts_fingerprint(panels_for_kernel):
    """Identity of the exact prompt set some art was rendered from.

    Panel FILENAMES are positional (p04_1.jpg), so they collide across two different scripts for
    the same case. Recovering art by filename alone would therefore drop script A's pictures
    under script B's captions -- structurally valid, silently wrong, and invisible to the OCR
    gate. The fingerprint is what makes recovery safe: art is only reused when it was rendered
    from byte-identical prompts.

    ⚠️ FILENAME AND PROMPT ONLY -- deliberately NOT the pixel dimensions. The property being
    protected is "this picture belongs under this caption", and that is carried entirely by the
    prompt. Size is a rendering-quality policy: when MAX_GEN_PX was introduced, hashing the
    dimensions too would have invalidated all 288 panels of a finished book over a change that
    affected 13 of them, and re-billed ~3.5h of T4 time to regenerate art that was already
    good. A policy knob must never be able to condemn correct art.
    """
    ident = [{"out": p["out"], "prompt": p["prompt"]} for p in panels_for_kernel]
    blob = json.dumps(ident, sort_keys=True).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()


def run_batch(kaggle_user, slug, panels, panels_dir, seed_base=3000):
    """Push one Kaggle kernel for the given list of {file,shape,prompt} dicts,
    poll to completion, download results into panels_dir. Returns list of
    files that failed to download."""
    kernel_id = f"{kaggle_user}/{slug}"
    kernel_dir = f"/tmp/kaggle_kernel_{slug}"
    os.makedirs(kernel_dir, exist_ok=True)
    os.makedirs(panels_dir, exist_ok=True)

    # ⚠️ Prefer the LAYOUT-DERIVED size over the nominal shape.
    #
    # DIMS is one fixed size per shape name -- LANDSCAPE is always 1280x720 (aspect 1.78). But
    # the page solver in build_comic.py decides a cell's real aspect from the composition: how
    # many panels share the tier, the neighbours' aspects, and how solve_rows water-filled the
    # heights. A "LANDSCAPE" panel sharing a three-panel tier may need aspect ~1.1. When the art
    # does not match its cell, build_comic crops (capped at MAX_CROP=0.10) or leaves the cell
    # short -- the empty space that has repeatedly forced panels to be regenerated on Kaggle.
    #
    # spec_panels.py solves the layout first and writes target_px/target_aspect back onto each
    # prompt entry. When that step has run, generate at exactly that size and the art fits the
    # page by construction. DIMS stays as the fallback for prompts that were never annotated.
    #
    # Built through the shared helper so the kernel and the recovery fingerprint can never
    # disagree about a size. Generation is capped at MAX_GEN_PX (see gen_size); the page's real
    # target_px is restored by upscaling on the way down, after the download below.
    panels_for_kernel = build_panels_for_kernel(panels)
    fitted = sum(1 for p in panels
                 if isinstance(p.get("target_px"), (list, tuple)) and len(p["target_px"]) == 2)
    capped = sum(1 for p in panels if gen_size(*target_px(p)) != target_px(p))
    print(f"panel sizing: {fitted}/{len(panels)} from layout (target_px), "
          f"{len(panels) - fitted} from nominal shape; {capped} capped to "
          f"{MAX_GEN_PX / 1e6:.1f}MP for generation and upscaled after", flush=True)

    hf_token = os.environ.get("HF_TOKEN", "")
    code = KERNEL_TEMPLATE.format(
        panels_json=json.dumps(panels_for_kernel), hf_token=hf_token, seed_base=seed_base,
        prompts_fp=prompts_fingerprint(panels_for_kernel),
        min_mean=MIN_MEAN, min_sd=MIN_SD, attempts=ATTEMPTS,
        lora_repo=os.environ.get("SGNOIR_LORA_REPO", ""),
        lora_trigger=os.environ.get("SGNOIR_LORA_TRIGGER", "sgnoir style"),
    )
    open(os.path.join(kernel_dir, "gen_flux.py"), "w", encoding="utf-8").write(code)
    json.dump({
        "id": kernel_id, "title": slug, "code_file": "gen_flux.py", "language": "python",
        "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_internet": True,
        "dataset_sources": [], "competition_sources": [], "kernel_sources": [],
        # enable_gpu alone gets whatever card is free, which is usually a P100 (sm_60).
        # This kernel loads the transformer and T5 in bitsandbytes NF4, and Pascal has no
        # tensor cores -- every 4-bit matmul dequantises and runs unaccelerated, which is
        # the difference between ~36s and several minutes per panel. Name the T4 explicitly.
        # (Undocumented enum; "NvidiaTeslaT4" is the value that works, and a wrong value is
        # silently ignored rather than erroring -- so verify the card in the kernel log.)
        "machine_shape": "NvidiaTeslaT4",
    }, open(os.path.join(kernel_dir, "kernel-metadata.json"), "w"), indent=2)

    # No timeout here used to mean a stalled/hung `kaggle` CLI call (network
    # stall, or the account's 2-concurrent-GPU-session cap) blocked the whole
    # Actions job indefinitely with zero visible error -- seen on a real
    # 75pp build that sat "in progress" for 80+ minutes with no kernel ever
    # created. Explicit timeout + bounded retry on the GPU-cap message (the
    # cap clears naturally as other kernels finish) instead of hanging forever.
    for attempt in range(1, 21):
        try:
            r = subprocess.run(["kaggle", "kernels", "push", "-p", "."], cwd=kernel_dir,
                                capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            print(f"push attempt {attempt}: timed out after 120s, retrying")
            continue
        if r.returncode == 0:
            break
        if "Maximum batch GPU session count" in (r.stdout + r.stderr):
            print(f"push attempt {attempt}: GPU sessions full, waiting 60s ...")
            time.sleep(60)
            continue
        raise RuntimeError(f"kaggle kernels push failed: {r.stdout} {r.stderr}")
    else:
        raise RuntimeError("kaggle kernels push: GPU sessions still full / unreachable after 20 attempts")

    # Bounded poll, but scaled to the batch size: a flat 45-min cap killed the
    # Actions job's WAIT on a real 75pp/151-panel build that was still
    # legitimately generating -- the underlying Kaggle kernel isn't tied to
    # the Actions job's lifecycle, so it kept running and actually finished
    # fine minutes later, its output briefly stranded until fetched manually.
    # ~1 min/panel (2 polls of 30s) plus headroom covers a normal-size comic
    # comfortably while still catching genuinely stuck kernels eventually.
    max_polls = max(90, len(panels) * 2)
    for _ in range(max_polls):
        time.sleep(30)
        try:
            r = subprocess.run(["kaggle", "kernels", "status", kernel_id],
                                capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            print("status check timed out, retrying")
            continue
        status = r.stdout.strip()
        print(status)
        if "COMPLETE" in status:
            break
        if "ERROR" in status or "CANCEL" in status:
            raise RuntimeError(f"Kaggle kernel failed: {r.stdout} {r.stderr}")
    else:
        raise RuntimeError(f"Kaggle kernel {kernel_id} still not COMPLETE after {max_polls * 30 // 60} min -- likely stuck")

    out_dir = os.path.join(kernel_dir, "out")
    subprocess.run(["kaggle", "kernels", "output", kernel_id, "-p", out_dir], check=True, timeout=180)

    failed = []
    degenerate = []
    for p in panels:
        src = os.path.join(out_dir, p["file"].replace("/", "_"))
        dst = os.path.join(panels_dir, p["file"])
        if not os.path.exists(src):
            failed.append(p["file"])
            continue
        os.replace(src, dst)
        m, sd = finish_panel(dst, target_px(p))
        if m < MIN_MEAN or sd < MIN_SD:
            degenerate.append((p["file"], m, sd))

    # Repeat the kernel's own check on what actually landed on disk. Saying it here as well as
    # in the Kaggle log is the point: nobody reads the Kaggle log, and the run this guard was
    # written for reported "success" while every full-bleed page in the book was a dark slab.
    if degenerate:
        print(f"WARNING: {len(degenerate)} panel(s) still degenerate after in-kernel "
              "re-rolls:", flush=True)
        for f, m, sd in degenerate:
            print(f"   {f}  mean {m:.1f}  sd {sd:.1f}", flush=True)
        print("   re-roll them with: -f regen_panels="
              f"\"{' '.join(f for f, _, _ in degenerate)}\"", flush=True)
    return failed


def finish_panel(path, target):
    """Upscale a generated panel to the size the page wants, and measure what landed.

    Generation is capped at MAX_GEN_PX, so a full-bleed splash arrives around 1024x1552 for a
    2064x3128 cell. build_comic would scale it anyway when it draws the page -- doing it here
    means the file on disk is the size the layout asked for, so nothing downstream has to know
    that the cap exists, and the measurement below is taken on the real deliverable.
    """
    # ImageStat rather than numpy: numpy is only ever present here as a transitive dependency
    # of rapidocr, and this step must not start depending on that staying true.
    from PIL import Image, ImageStat
    with Image.open(path) as im:
        im = im.convert("RGB")
        if im.size != tuple(target):
            im = im.resize(tuple(target), Image.LANCZOS)
            im.save(path, quality=92)
        st = ImageStat.Stat(im.convert("L"))
    return float(st.mean[0]), float(st.stddev[0])


def recover_from_previous_kernel(user, slug, prompts, panels_dir):
    """Pull art from an earlier run's kernel instead of paying for the GPU twice.

    cases/ is rm -rf'd at the end of EVERY run (the repo is public and the art is the paid
    product), so a failure anywhere after art generation used to throw the finished panels away.
    That is exactly what happened on 2026-09-01: all 154 panels generated, the optional OCR
    retry errored, and ~90 minutes of T4 time was deleted.

    Kaggle keeps a completed kernel's output, so the art outlives the runner. Downloading it
    costs nothing but bandwidth and lets the "All panels already present" check below do its
    job. Best-effort by design: no previous kernel, a failed download, or a partial one just
    means the normal generation path fills in whatever is still missing.
    """
    if not user:
        return
    kernel_id = f"{user}/{slug}"
    try:
        r = subprocess.run(["kaggle", "kernels", "status", kernel_id],
                           capture_output=True, text=True, timeout=120)
        if "COMPLETE" not in (r.stdout or ""):
            return
    except Exception:
        return

    print(f"found a completed kernel {kernel_id} -- recovering its art before generating",
          flush=True)
    out_dir = os.path.join(tempfile.mkdtemp(prefix="kaggle_recover_"), "out")
    try:
        subprocess.run(["kaggle", "kernels", "output", kernel_id, "-p", out_dir],
                       check=True, timeout=1800)
    except Exception as e:
        print(f"  recovery download failed ({e}) -- generating from scratch", flush=True)
        return

    # ⭐ MATCH PER PANEL, NOT PER BOOK.
    #
    # This used to be one SHA1 over the whole list: any difference at all and NOTHING was
    # recovered. That is only correct while every kernel renders the entire book. It does not:
    # a targeted `--regen` pushes a kernel containing ONLY the handful of panels being
    # re-rolled, to the same kernel id, overwriting the full-book kernel that came before. So
    # the run after a /regen sees a 13-panel kernel, fails the whole-list hash against a
    # 288-panel script, and regenerates all 288 -- hours of T4 time to replace art that was
    # already good and already sitting in the download directory.
    #
    # The safety property was never about the list. It is "this picture was rendered from this
    # caption's prompt", which is a per-panel fact, so check it per panel. Strictly safer than
    # the whole-list hash it replaces: that one recovered files by NAME once the global hash
    # matched, this one verifies every file it takes.
    prev = {p["out"]: p["prompt"] for p in panels_from_kernel_source(kernel_id)}

    # Fast path for the ordinary case, and the fallback when the source cannot be read: an
    # intact whole-list stamp still vouches for every panel in one go.
    fp_path = os.path.join(out_dir, "_prompts_fp.txt")
    stamp = open(fp_path).read().strip() if os.path.exists(fp_path) else ""
    whole_book = bool(stamp) and stamp == prompts_fingerprint(build_panels_for_kernel(prompts))

    if not prev and not whole_book:
        print("  cannot establish what the previous kernel rendered -- regenerating rather "
              "than putting old art under new captions", flush=True)
        return

    os.makedirs(panels_dir, exist_ok=True)
    recovered = mismatched = 0
    for p in prompts:
        name = p["file"].replace("/", "_")
        src = os.path.join(out_dir, name)
        dst = os.path.join(panels_dir, p["file"])
        if not os.path.exists(src) or os.path.exists(dst):
            continue
        if not whole_book and prev.get(name) != p["prompt"]:
            mismatched += 1
            continue
        os.replace(src, dst)
        recovered += 1
    print(f"  recovered {recovered}/{len(prompts)} panels from the previous run"
          + (f" ({mismatched} skipped: rendered from a different prompt)" if mismatched else ""),
          flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-dir", required=True, help="directory containing panel_prompts.json and panels/")
    ap.add_argument("--kaggle-user", default=os.environ.get("KAGGLE_USERNAME"))
    ap.add_argument("--slug", required=True)
    ap.add_argument("--regen", default="",
                    help="Comma/space separated panel files to force re-rolling, e.g. "
                         "'p05_3.jpg p06_1.jpg'. They are removed after recovery so the normal "
                         "missing-panel path regenerates them, on a different seed.")
    args = ap.parse_args()

    panels_dir = os.path.join(args.case_dir, "panels")
    prompts = json.load(open(os.path.join(args.case_dir, "panel_prompts.json"), encoding="utf-8"))
    recover_from_previous_kernel(args.kaggle_user, args.slug, prompts, panels_dir)

    # Forced re-rolls, requested per panel from Telegram after a human looked at the OCR contact
    # sheets. Deleting AFTER recovery is what makes this work: recovery restores the full set,
    # then these few are dropped so the missing-panel path below regenerates exactly them.
    forced = [f for f in re.split(r"[,\s]+", args.regen.strip()) if f]
    for f in forced:
        f = f if f.endswith(".jpg") else f + ".jpg"
        path = os.path.join(panels_dir, f)
        if os.path.exists(path):
            os.remove(path)
        else:
            print(f"  /regen: {f} is not a panel of this book, ignoring", flush=True)
    if forced:
        print(f"forced re-roll of {len(forced)} panel(s): {forced}", flush=True)
    missing = [p for p in prompts if not os.path.exists(os.path.join(panels_dir, p["file"]))]
    if not missing:
        print("All panels already present, skipping")
        return
    print(f"{len(missing)}/{len(prompts)} panels need generation")
    # A different seed base for a forced re-roll -- re-rendering the same prompt at the same
    # seed reproduces the same picture, which is not a fix.
    seed = 3000 + (7000 if forced else 0)
    failed = run_batch(args.kaggle_user, args.slug, missing, panels_dir, seed_base=seed)
    if failed:
        print(f"WARNING: {len(failed)} panels failed to generate: {failed}", file=sys.stderr)


if __name__ == "__main__":
    main()
