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

HERE = os.path.dirname(os.path.abspath(__file__))

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

# How many panels one Kaggle kernel may render before the work is split across another.
#
# Not a Kaggle limit and not a timeout -- a host-RAM ceiling. The render loop allocates a fresh
# float32 array per attempt for the tonal check and never releases host memory (its only
# cleanup, torch.cuda.empty_cache(), is GPU-side), so RSS grows with panel count until the OOM
# killer takes the session. Observed: 225 and 228 panels finish comfortably; 471 was killed at
# roughly panel 380, 3h21m in, having produced nothing the pipeline could then use.
#
# 200 sits below every run that has ever succeeded, with room to spare. Raising it trades that
# margin for fewer kernel startups (~2 min each), which is a bad trade against losing hours.
MAX_PANELS_PER_KERNEL = 200


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


def list_case_kernels(user, base_slug):
    """Every kernel holding art for this case, most recently run FIRST.

    A case's art lives across several kernels, not one -- see next_kernel_id for why. Ordering
    matters: a panel re-rolled last week and re-rolled again today exists in two kernels, and the
    newest is the one the reviewer asked for.
    """
    if not user:
        return []
    try:
        r = subprocess.run(["kaggle", "kernels", "list", "--user", user, "-s", base_slug, "-v"],
                           capture_output=True, text=True, timeout=120)
    except Exception:
        return []
    import csv
    import io
    rows = []
    try:
        for row in csv.DictReader(io.StringIO(r.stdout or "")):
            ref = (row.get("ref") or "").strip()
            name = ref.split("/", 1)[-1]
            # Kaggle's -s is a fuzzy search, so it also returns other cases' kernels. Only the
            # base slug and its numbered siblings belong to this book.
            if not re.fullmatch(re.escape(base_slug) + r"(-\d+)?", name):
                continue
            rows.append(((row.get("lastRunTime") or ""), ref))
    except Exception:
        return []
    rows.sort(reverse=True)
    return [ref for _, ref in rows]


def next_kernel_id(user, base_slug):
    """A kernel id that does not exist yet, so pushing NEVER destroys art.

    ⭐ THE KERNEL IS THE ONLY ART STORE. cases/ is rm -rf'd after every run, so the previous
    kernel's output is the sole surviving copy of a book's panels. Pushing a new version of a
    kernel REPLACES that output -- which meant a targeted /regen of 13 panels left a kernel
    holding only those 13, and the next run of that book had to regenerate the other 275 at a
    different seed, changing art that was already approved. Two re-rolls in a row could never
    both survive: the store ping-ponged and was never complete.

    Writing each batch to a fresh kernel makes the store append-only. Recovery then overlays all
    of a case's kernels, newest first, so every panel ever rendered stays reachable.
    """
    used = set()
    for ref in list_case_kernels(user, base_slug):
        name = ref.split("/", 1)[-1]
        m = re.fullmatch(re.escape(base_slug) + r"-(\d+)", name)
        used.add(int(m.group(1)) if m else 1)
    if not used:
        return f"{user}/{base_slug}"      # first generation of this book
    n = 2
    while n in used:
        n += 1
    return f"{user}/{base_slug}-{n}"


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
    # A FRESH kernel every time -- never a new version of an existing one, which would replace
    # the only surviving copy of everything that kernel holds. See next_kernel_id.
    kernel_id = next_kernel_id(kaggle_user, slug)
    kernel_name = kernel_id.split("/", 1)[-1]
    print(f"generating into a new kernel: {kernel_id}", flush=True)
    kernel_dir = "/tmp/kaggle_kernel_" + kernel_name
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
        # ⚠️ TITLE MUST SLUGIFY TO THE ID. Kaggle rejects a push whose title does not resolve to
        # the kernel id with "title does not resolve to the specified id" + 409 Conflict. This
        # was harmless while the id was always <slug>, and broke the moment append-only naming
        # started producing <slug>-2 against a title still reading <slug>.
        "id": kernel_id, "title": kernel_name, "code_file": "gen_flux.py", "language": "python",
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
    for p in panels:
        src = os.path.join(out_dir, p["file"].replace("/", "_"))
        dst = os.path.join(panels_dir, p["file"])
        if not os.path.exists(src):
            failed.append(p["file"])
            continue
        os.replace(src, dst)
        finish_panel(dst, target_px(p))
    # The degenerate check is NOT here. It runs over the whole book in scan_dark() instead --
    # art recovered from a previous kernel never passes through this loop, and a dark panel is
    # just as dark whether this run rendered it or inherited it.
    return failed


def scan_dark(panels_dir, prompts):
    """Every panel in the finished book that came out dark or flat, worst first.

    Deliberately sweeps the WHOLE book, not just what this run rendered. Most of a rebuild is
    recovered from the previous kernel and never passes through the download loop, so checking
    only fresh art would report a clean book while 275 inherited panels went unlooked-at.

    Returns [(file, mean, sd)] using the same MIN_MEAN/MIN_SD the kernel re-rolls on, so what
    lands in Telegram and what the GPU already retried mean the same thing.
    """
    from PIL import Image, ImageStat
    out = []
    for p in prompts:
        path = os.path.join(panels_dir, p["file"])
        if not os.path.exists(path):
            continue
        try:
            with Image.open(path) as im:
                st = ImageStat.Stat(im.convert("L"))
        except Exception as e:
            # An unreadable panel is a defect worth re-rolling, not a reason to abandon the scan.
            print(f"  could not measure {p['file']}: {e}", flush=True)
            out.append((p["file"], 0.0, 0.0))
            continue
        m, sd = float(st.mean[0]), float(st.stddev[0])
        if m < MIN_MEAN or sd < MIN_SD:
            out.append((p["file"], m, sd))
    return sorted(out, key=lambda r: r[2])


def build_contact_sheets(panels_dir, entries, out_dir, prefix,
                         per_sheet=12, cols=4, cell=430):
    """Tile panels up for review, each labelled with the name to type into /regen.

    `entries` is a list of (filename, note). The note is what puts the reviewer in the picture:
    a panel is up for re-roll either because OCR saw letterforms in it or because it measured
    dark and flat, and those are different judgements to make by eye.

    Lives here rather than in ocr_autofix because it needs nothing but Pillow, while that module
    imports RapidOCR at the top -- so the dark sheets stay buildable in the art step even on a
    run where the OCR step falls over, which is a step marked continue-on-error precisely
    because it does.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("WARNING: Pillow missing, no contact sheets", flush=True)
        return []

    # PIL's default bitmap font is ~11px and unreadable once Telegram scales a 1700px sheet down
    # to phone width -- the label is the whole point, since it is what gets typed into /regen.
    font = note_font = None
    for cand in (os.path.join(os.path.dirname(HERE), "fonts", "Montserrat-Bold.ttf"),
                 os.path.join(HERE, "fonts", "Montserrat-Bold.ttf")):
        try:
            font = ImageFont.truetype(cand, 30)
            note_font = ImageFont.truetype(cand, 21)
            break
        except Exception:
            continue

    sheets = []
    for idx in range(0, len(entries), per_sheet):
        batch = entries[idx:idx + per_sheet]
        rows = (len(batch) + cols - 1) // cols
        label_h = 74
        sheet = Image.new("RGB", (cols * cell, rows * (cell + label_h)), (18, 18, 18))
        draw = ImageDraw.Draw(sheet)
        for i, (fn, note) in enumerate(batch):
            path = os.path.join(panels_dir, fn)
            x, y = (i % cols) * cell, (i // cols) * (cell + label_h)
            try:
                im = Image.open(path).convert("RGB")
                im.thumbnail((cell - 8, cell - 8))
                sheet.paste(im, (x + 4, y + 4))
            except Exception:
                draw.rectangle([x + 4, y + 4, x + cell - 4, y + cell - 4], outline=(90, 90, 90))
            draw.text((x + 8, y + cell + 4), fn.replace(".jpg", ""),
                      fill=(255, 214, 90), font=font)
            if note:
                draw.text((x + 8, y + cell + 40), note, fill=(190, 190, 190), font=note_font)
        out = os.path.join(out_dir, f"{prefix}{idx // per_sheet + 1}.jpg")
        sheet.save(out, "JPEG", quality=88)
        sheets.append(out)
    return sheets


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
    os.makedirs(panels_dir, exist_ok=True)
    kernels = list_case_kernels(user, slug)
    if not kernels:
        print(f"no existing kernel for {slug} -- generating from scratch", flush=True)
        return
    print(f"{len(kernels)} kernel(s) hold art for this case: {', '.join(kernels)}", flush=True)

    total = 0
    for kernel_id in kernels:
        # Stop as soon as the book is whole. Kernels are ordered newest-first, so the panels
        # already taken are the most recent renders of themselves -- an older kernel must never
        # overwrite a re-roll the reviewer asked for.
        wanted = [p for p in prompts
                  if not os.path.exists(os.path.join(panels_dir, p["file"]))]
        if not wanted:
            break
        total += recover_one_kernel(kernel_id, wanted, panels_dir)
    print(f"  recovered {total}/{len(prompts)} panels from {len(kernels)} kernel(s)", flush=True)


def recover_one_kernel(kernel_id, wanted, panels_dir):
    """Take from one kernel every panel in `wanted` it can vouch for. Returns how many."""
    try:
        r = subprocess.run(["kaggle", "kernels", "status", kernel_id],
                           capture_output=True, text=True, timeout=120)
        status = r.stdout or ""
        # ⭐⭐ A KILLED KERNEL IS THE ONE MOST WORTH HARVESTING.
        #
        # This used to require "COMPLETE", which threw away exactly the art it should have
        # saved. The Phantom of Heilbronn ran 3h21m, rendered ~380 of its 471 panels, and was
        # OOM-killed at 80%; its status is ERROR, so recovery skipped it without downloading a
        # byte, and the retry started all 471 again -- and would have died at the same place.
        # Two full GPU days for nothing, with the panels sitting in the kernel the whole time.
        #
        # Asking "did the run finish?" is the wrong question. The right one is "does this
        # kernel hold panels I can vouch for?", and that is answered per panel below: every
        # file is matched against the prompt it was rendered from, taken from the kernel's own
        # source. A half-finished kernel therefore yields fewer panels; it cannot yield a wrong
        # one. The status check is strictly weaker than the guard that follows it.
        #
        # RUNNING and QUEUED are still skipped -- that output is mid-write, and there is no
        # reason to race a kernel that will be listed again on the next pass.
        if "RUNNING" in status or "QUEUED" in status:
            print(f"  {kernel_id}: still running, skipping", flush=True)
            return 0
        if "COMPLETE" not in status:
            print(f"  {kernel_id}: status is not COMPLETE ({status.strip()[:60]}) -- "
                  "harvesting whatever panels it finished", flush=True)
    except Exception:
        return 0

    out_dir = os.path.join(tempfile.mkdtemp(prefix="kaggle_recover_"), "out")
    try:
        subprocess.run(["kaggle", "kernels", "output", kernel_id, "-p", out_dir],
                       check=True, timeout=1800)
    except Exception as e:
        print(f"  {kernel_id}: download failed ({e}), skipping", flush=True)
        return 0
    # ⭐ MATCH PER PANEL, NOT PER BOOK.
    #
    # This used to be one SHA1 over the whole list: any difference at all and NOTHING was
    # recovered. That is only correct while every kernel renders the entire book, and none of
    # them do -- a targeted --regen renders a handful, so a per-book hash compares 13 panels
    # against a 288-panel script, fails, and regenerates everything.
    #
    # The safety property was never about the list. It is "this picture was rendered from this
    # caption's prompt", which is a per-panel fact, so check it per panel. Strictly safer than
    # the whole-list hash it replaces: that one recovered files by NAME once the global hash
    # matched, this one verifies every file it takes.
    prev = {p["out"]: p["prompt"] for p in panels_from_kernel_source(kernel_id)}

    # Fallback when the source cannot be read: an intact whole-list stamp vouches for the lot.
    fp_path = os.path.join(out_dir, "_prompts_fp.txt")
    stamp = open(fp_path).read().strip() if os.path.exists(fp_path) else ""
    whole_book = bool(stamp) and stamp == prompts_fingerprint(build_panels_for_kernel(wanted))

    if not prev and not whole_book:
        print(f"  {kernel_id}: cannot establish what it rendered -- skipping rather than "
              "putting its art under new captions", flush=True)
        return 0

    recovered = mismatched = 0
    for p in wanted:
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
    print(f"  {kernel_id}: recovered {recovered}"
          + (f" ({mismatched} skipped: rendered from a different prompt)" if mismatched else ""),
          flush=True)
    return recovered


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
        print("All panels already present, skipping generation")
    else:
        print(f"{len(missing)}/{len(prompts)} panels need generation")
        # A different seed base for a forced re-roll -- re-rendering the same prompt at the same
        # seed reproduces the same picture, which is not a fix.
        seed = 3000 + (7000 if forced else 0)

        # ⭐⭐ CHUNK. One kernel cannot carry a whole large book.
        #
        # Every panel in a kernel run allocates a fresh float32 array for the tonal check, and
        # the only cleanup in the loop is torch.cuda.empty_cache(), which frees GPU memory and
        # does nothing for host RAM. RSS therefore climbs monotonically with panel count. At
        # ~225 panels the run finishes first -- which is why every book so far has worked. The
        # Phantom of Heilbronn asked for 471 and was OOM-killed by the host at panel ~380,
        # three hours and twenty minutes in.
        #
        # Splitting is nearly free here because the art store is already append-only:
        # next_kernel_id() hands each chunk its own kernel, and recover_from_previous_kernel
        # overlays them newest-first. The cap is what makes a 100-page issue buildable at all.
        #
        # Seeds must stay tied to a panel's position in the WHOLE book, not its position in a
        # chunk, or chunking would silently change the art of every panel after the first 200.
        failed = []
        chunks = [missing[i:i + MAX_PANELS_PER_KERNEL]
                  for i in range(0, len(missing), MAX_PANELS_PER_KERNEL)]
        if len(chunks) > 1:
            print(f"splitting across {len(chunks)} kernels "
                  f"(max {MAX_PANELS_PER_KERNEL} panels each) to stay inside the memory the "
                  f"host gives one session", flush=True)
        for n, chunk in enumerate(chunks):
            if len(chunks) > 1:
                print(f"--- chunk {n + 1}/{len(chunks)}: {len(chunk)} panels ---", flush=True)
            failed += run_batch(args.kaggle_user, args.slug, chunk, panels_dir,
                                seed_base=seed + n * MAX_PANELS_PER_KERNEL)
        if failed:
            print(f"WARNING: {len(failed)} panels failed to generate: {failed}", file=sys.stderr)

    # Measure the finished book and hand the bad panels to the reviewer.
    #
    # Runs on EVERY path, including "all panels already present" -- that branch used to return
    # early, which is exactly the run where nothing new was rendered and therefore nothing new
    # was ever looked at. The output is two files stage_and_deliver picks up: the names, which
    # become re-rollable via /regen, and contact sheets showing what they actually look like.
    dark = scan_dark(panels_dir, prompts)
    names = [f for f, _, _ in dark]
    json.dump(names, open(os.path.join(args.case_dir, "dark_panels.json"), "w"), indent=2)
    if not dark:
        print(f"tonal scan clean: 0/{len(prompts)} panels dark or flat", flush=True)
        return
    print(f"WARNING: {len(dark)}/{len(prompts)} panel(s) came out dark or flat "
          f"(mean<{MIN_MEAN} or sd<{MIN_SD}):", file=sys.stderr, flush=True)
    for f, m, sd in dark:
        print(f"   {f}  mean {m:.1f}  sd {sd:.1f}", flush=True)
    sheets = build_contact_sheets(
        panels_dir, [(f, f"dark  mean {m:.0f}  sd {sd:.0f}") for f, m, sd in dark],
        args.case_dir, "dark_sheet")
    print(f"{len(dark)} dark panel(s) -> {len(sheets)} contact sheet(s); no art was touched",
          flush=True)


if __name__ == "__main__":
    main()
