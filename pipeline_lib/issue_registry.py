"""Assign each comic its issue number, once, and remember it.

gen_case_script defaulted --issue-no to "01", so EVERY book shipped as issue 01 no matter how
many already existed. POISONED GROUND came out as #01 colliding with NORJAK, and Heaven's Gate
shipped as #04 while Gumroad sold it as #2 -- the number is baked into four separate strings in
the script JSON and into the printed PDF, so correcting it afterwards means a rebuild.

The registry is names and numbers only -- no script, no art -- so it is safe to commit to this
public repo, the same reasoning that lets cases_used.json live here.

Seeded with the four books that already exist, whose numbering was settled from the Gumroad
storefront (see the comic-issue-numbering memory): the storefront is the authority, because
NORJAK and HEAVEN'S GATE are published and their numbers are visible to buyers.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(os.path.dirname(HERE), "issues.json")

SEED = {
    "norjak": 1,
    "heavens-gate": 2,
    "jonestown-massacre-peoples-temple-1978": 3,
    "iranian-embassy-siege": 4,
}


def _load():
    if not os.path.exists(REGISTRY_PATH):
        return {"issues": dict(SEED)}
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("issues", {})
    for k, v in SEED.items():
        data["issues"].setdefault(k, v)
    return data


def assign(case_id):
    """Return this case's issue number as a zero-padded string, assigning one if new.

    Idempotent on purpose: a rebuild of the same case must produce the SAME number, or the
    reprint would contradict the copy already delivered. Only a genuinely new case advances the
    counter.
    """
    data = _load()
    issues = data["issues"]
    if case_id in issues:
        return f"{issues[case_id]:02d}"

    nxt = max(issues.values(), default=0) + 1
    issues[case_id] = nxt
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    print(f"issue registry: {case_id} -> #{nxt:02d}", flush=True)
    return f"{nxt:02d}"


def peek(case_id):
    """The number this case would get, without assigning it."""
    issues = _load()["issues"]
    return f"{issues.get(case_id, max(issues.values(), default=0) + 1):02d}"
