"""Generic FLUX-on-Kaggle panel generator (works from any case directory
containing panel_prompts.json), adapted from the shadow_gasp local pipeline.

Requires KAGGLE_USERNAME / KAGGLE_API_TOKEN env vars (set as GitHub Actions
secrets) -- kaggle==2.2.2's CLI auths via KAGGLE_API_TOKEN, not the legacy
KAGGLE_USERNAME/KAGGLE_KEY pair (see pipeline.yml's Kaggle-auth comment).
"""
import argparse
import json
import os
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
print("PIPE READY", flush=True)

PANELS = {panels_json}

for i, p in enumerate(PANELS):
    name, w, h, prompt = p["out"], p["w"], p["h"], p["prompt"]
    try:
        img=pipe(prompt, num_inference_steps=4, guidance_scale=0.0, height=h, width=w,
                 max_sequence_length=256, generator=torch.Generator("cpu").manual_seed({seed_base}+i)).images[0]
        img.save(f"/kaggle/working/{{name}}", quality=92)
        m=float(np.asarray(img).mean())
        print("DONE", name, "meanpix", round(m,1), ("<-- BLACK/NaN!" if m<5 else ""), flush=True)
    except Exception as e:
        print("FAILED", name, repr(e), flush=True)
    torch.cuda.empty_cache()
print("ALL DONE", flush=True)
'''


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
    panels_for_kernel = []
    fitted = 0
    for p in panels:
        tp = p.get("target_px")
        if isinstance(tp, (list, tuple)) and len(tp) == 2 and all(isinstance(v, int) for v in tp):
            w, h = tp
            fitted += 1
        else:
            w, h = DIMS[p["shape"]]
        panels_for_kernel.append({"out": p["file"].replace("/", "_"), "w": w, "h": h, "prompt": p["prompt"]})
    print(f"panel sizing: {fitted}/{len(panels)} from layout (target_px), "
          f"{len(panels) - fitted} from nominal shape", flush=True)

    hf_token = os.environ.get("HF_TOKEN", "")
    code = KERNEL_TEMPLATE.format(
        panels_json=json.dumps(panels_for_kernel), hf_token=hf_token, seed_base=seed_base,
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
    for p in panels:
        src = os.path.join(out_dir, p["file"].replace("/", "_"))
        dst = os.path.join(panels_dir, p["file"])
        if os.path.exists(src):
            os.replace(src, dst)
        else:
            failed.append(p["file"])
    return failed


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

    os.makedirs(panels_dir, exist_ok=True)
    recovered = 0
    for p in prompts:
        src = os.path.join(out_dir, p["file"].replace("/", "_"))
        dst = os.path.join(panels_dir, p["file"])
        if os.path.exists(src) and not os.path.exists(dst):
            os.replace(src, dst)
            recovered += 1
    print(f"  recovered {recovered}/{len(prompts)} panels from the previous run", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-dir", required=True, help="directory containing panel_prompts.json and panels/")
    ap.add_argument("--kaggle-user", default=os.environ.get("KAGGLE_USERNAME"))
    ap.add_argument("--slug", required=True)
    args = ap.parse_args()

    panels_dir = os.path.join(args.case_dir, "panels")
    prompts = json.load(open(os.path.join(args.case_dir, "panel_prompts.json"), encoding="utf-8"))
    recover_from_previous_kernel(args.kaggle_user, args.slug, prompts, panels_dir)
    missing = [p for p in prompts if not os.path.exists(os.path.join(panels_dir, p["file"]))]
    if not missing:
        print("All panels already present, skipping")
        return
    print(f"{len(missing)}/{len(prompts)} panels need generation")
    failed = run_batch(args.kaggle_user, args.slug, missing, panels_dir)
    if failed:
        print(f"WARNING: {len(failed)} panels failed to generate: {failed}", file=sys.stderr)


if __name__ == "__main__":
    main()
