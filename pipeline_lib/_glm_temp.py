import sys, time
sys.path.insert(0, ".")
import llm as LLM

big_system = "You write true-crime documentary comics for SHADOW GASP, following strict house style rules. " * 200
model = "zai-org/GLM-5.2"
c = LLM.LLM(provider="featherless", model=model, fallback=False)

print(f"=== {model}: scale test ===")
for mt in [16000, 32000, 48000, 64000]:
    t0 = time.time()
    try:
        out = c.text("Write a 3-sentence summary of a fictional 1990s missing-person case.", system=big_system, max_tokens=mt)
        print(f"max_tokens={mt}: OK in {time.time()-t0:.1f}s, {len(out)} chars")
    except Exception as e:
        print(f"max_tokens={mt}: FAILED after {time.time()-t0:.1f}s - {e}")
