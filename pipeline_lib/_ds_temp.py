import sys, time
sys.path.insert(0, ".")
import llm as LLM

PROMPT = """You are writing for SHADOW GASP, a true-crime documentary comic series. Write ONE caption for a single splash-page panel (max 40 words, plain prose, no markdown) depicting: a noir comic panel about the 1995 disappearance of a local TV news anchor on her way to work before dawn. The panel shows her car abandoned in an apartment parking lot with signs of struggle. Also write ONE FLUX image prompt for this exact panel following these rules: start with exactly 'Noir true-crime comic artwork, ink outlines, halftone shading, 1995 palette. Heavy black ink and deep shadow retained even in bright daylight, strong tonal contrast, never washed out or high-key. The illustration fills the whole image, running to all four edges.' then a concrete scene description, then end with exactly 'All visible surfaces are smooth and unmarked.' Keep the whole prompt under 60 words, never use negation words like no/without/avoid. Also write ONE back-matter fact (90-155 characters) about the real case. Output exactly three lines labeled CAPTION:, PROMPT:, FACT:"""

big_system = "You write true-crime documentary comics for SHADOW GASP, following strict house style rules. " * 100
model = "deepseek-ai/DeepSeek-V3.2"
c = LLM.LLM(provider="featherless", model=model, fallback=False)

print(f"=== {model}: quality sample ===")
t0=time.time()
out = c.text(PROMPT, max_tokens=500)
print(f"time={time.time()-t0:.1f}s")
print(out)

print(f"\n=== {model}: scale test ===")
for mt in [16000, 32000, 48000, 64000]:
    t0 = time.time()
    try:
        out2 = c.text("Write a 3-sentence summary of a fictional 1990s missing-person case.", system=big_system, max_tokens=mt)
        print(f"max_tokens={mt}: OK in {time.time()-t0:.1f}s, {len(out2)} chars")
    except Exception as e:
        print(f"max_tokens={mt}: FAILED after {time.time()-t0:.1f}s - {e}")
