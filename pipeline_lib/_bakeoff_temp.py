import sys, time
sys.path.insert(0, ".")
import llm as LLM

PROMPT = """You are writing for SHADOW GASP, a true-crime documentary comic series. Write ONE caption for a single splash-page panel (max 40 words, plain prose, no markdown) depicting: a Kaggle-hosted noir comic about the 1995 disappearance of a local TV news anchor on her way to work before dawn. The panel shows her car abandoned in an apartment parking lot with signs of struggle. Also write ONE back-matter fact (90-155 characters) about the real case. Output exactly two lines, labeled CAPTION: and FACT:"""

candidates = [
    "Qwen/Qwen2.5-72B-Instruct",
    "meta-llama/Llama-3.1-70B-Instruct",
    "mistralai/Mistral-Small-24B-Instruct-2501",
]

for model in candidates:
    print(f"\n=== {model} ===")
    try:
        c = LLM.LLM(provider="featherless", model=model, fallback=False)
        t0 = time.time()
        out = c.text(PROMPT, max_tokens=300)
        dt = time.time() - t0
        print(f"time={dt:.1f}s")
        print(out.strip()[:500])
    except Exception as e:
        print("FAILED:", e)
