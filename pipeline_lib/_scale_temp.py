import sys
sys.path.insert(0, ".")
import llm as LLM

# Roughly mimic the real script-gen call's scale: big system prompt, big max_tokens.
big_system = "You write true-crime documentary comics. " * 200  # ~1400 words filler, mimics house-style bulk
prompt = "Write a 3-sentence summary of a fictional 1990s missing-person case, in plain prose."

c = LLM.LLM(provider="featherless", model="Qwen/Qwen2.5-72B-Instruct", fallback=False)
for mt in [4000, 16000, 24000, 51200]:
    try:
        out = c.text(prompt, system=big_system, max_tokens=mt)
        print(f"max_tokens={mt}: OK, {len(out)} chars")
    except Exception as e:
        print(f"max_tokens={mt}: FAILED - {e}")
