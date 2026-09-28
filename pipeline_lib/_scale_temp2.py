import sys, time
sys.path.insert(0, ".")
import llm as LLM

big_system = "You write true-crime documentary comics. " * 200
prompt = "Write a 3-sentence summary of a fictional 1990s missing-person case, in plain prose."

for model in ["Qwen/Qwen3-32B", "Qwen/Qwen3-Next-80B-A3B-Instruct"]:
    print(f"\n=== {model} ===")
    c = LLM.LLM(provider="featherless", model=model, fallback=False)
    for mt in [16000, 32000, 48000, 64000]:
        t0 = time.time()
        try:
            out = c.text(prompt, system=big_system, max_tokens=mt)
            dt = time.time() - t0
            print(f"max_tokens={mt}: OK in {dt:.1f}s, {len(out)} chars")
        except Exception as e:
            dt = time.time() - t0
            print(f"max_tokens={mt}: FAILED after {dt:.1f}s - {e}")
