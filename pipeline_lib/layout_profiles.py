"""Give every comic a DIFFERENT page architecture.

WHY THIS EXISTS
Measured on the Heaven's Gate script: 75 pages, 12% splash, 88% SIX-panel, nothing in between.
Binary pacing, and every six-panel page ruled up identically. Three separate causes:

  1. ⭐ THE BIG ONE, in spec_panels.plan_page: `shapes` are tuples and `authored` arrives from
     script JSON as a LIST, so the "authored structure wins ties" rule compared (1,2,3) with
     [1,2,3] and never once fired. Every page silently took the planner's single favourite
     structure for its panel count. Not an LLM failure -- a type mismatch. Fixed there.
  2. gen_case_script.py stated its target page mix in PROSE and never checked it, so nothing
     noticed the collapse. audit() below now measures it.
  3. The target was the SAME FOR EVERY CASE, so even a perfectly obeyed mix would give all 111
     planned comics one rhythm. Across a catalogue that reads as a template.

The renderer was never the limit. With the tuple bug fixed, all six zero-cost six-panel
structures are honoured: [1,2,3] [1,3,2] [2,1,3] [2,3,1] [3,1,2] [3,2,1], and at five panels
[1,1,3] [1,2,2] [1,3,1] [2,1,2] [2,2,1] [3,1,1].

⚠️ [3,3] and [2,2,2] are NOT available on this trim and are correctly rejected: three panels
abreast across a 6.6in live area with only two tiers asks for ~0.45-aspect slivers, below the
readable floor. Do not put them in a tier_note.

HOW IT WORKS
Each case gets one PROFILE, chosen deterministically from its case id, so:
  * the same case always regenerates the same way (reproducible builds, re-runs are stable),
  * neighbouring cases get different profiles (the picker is a hash, not a counter),
  * and nobody has to remember which look was used last.

Profiles differ on the three things a reader actually perceives: how often the page opens up to
a single image, how many panels a normal page carries, and whether tiers run wide or stack.
"""
import hashlib


# density: page-type weights as {panels_on_page: share}. 1 == splash.
# tier_note: guidance on HOW panels sit in rows -- the renderer supports up to 3 per tier, and
#            a 3-panel page reads completely differently as [3] than as [1,2] or [2,1].
# ⚠️ Calibrated against the real production book, not invented. Heaven's Gate measured:
#   75 pages -> 12% splash, 88% SIX-panel, nothing in between, 5.4 panels/page.
# So the defect is not "too few panels", it is BINARY pacing: every page is either one image
# or six. These profiles keep a comparable overall density (a 25-page issue still has to carry
# its panel budget) while spreading pages across 2..6 so the book has a middle register.
# An early draft of this table topped out at 4-5 panels and would have fought the pipeline's
# own panel-count floor, leaving the audit permanently red.
PROFILES = {
    "classic": {
        "blurb": "the house rhythm: a wide establishing tier over tighter beats",
        "density": {1: 0.12, 4: 0.10, 5: 0.34, 6: 0.44},
        "tier_note": "Six-panel pages as [1,2,3]; five-panel as [1,1,3]. Open with the "
                     "full-measure establishing panel, then tighten.",
    },
    "cinematic": {
        "blurb": "widescreen: wide tiers up top, splashes used generously",
        "density": {1: 0.20, 4: 0.14, 5: 0.30, 6: 0.36},
        "tier_note": "Lead with full-measure LANDSCAPE tiers: [1,2,3] and [1,3,2] at six "
                     "panels, [1,1,3] or [1,2,2] at five. Never open on a [3] tier.",
    },
    "documentary": {
        "blurb": "dense and evidential: an even grid, dossier feel, splashes rare",
        "density": {1: 0.04, 5: 0.26, 6: 0.70},
        "tier_note": "Put the three-beat tier FIRST so the page reads as evidence in order: "
                     "[3,1,2] and [3,2,1] at six panels, [3,1,1] at five.",
    },
    "staccato": {
        "blurb": "fast cutting: three-beat tiers, abrupt changes of size",
        "density": {1: 0.10, 4: 0.10, 5: 0.32, 6: 0.48},
        "tier_note": "Cut fast: [3,1,2] and [2,1,3] at six panels, [2,1,2] at five -- a wide "
                     "beat dropped between tight tiers.",
    },
    "chamber": {
        "blurb": "close and claustrophobic: paired tall panels, little air",
        "density": {1: 0.10, 4: 0.14, 5: 0.34, 6: 0.42},
        "tier_note": "Favour paired PORTRAIT panels: [2,3,1] and [2,1,3] at six, [2,2,1] or "
                     "[2,1,2] at five. Keep full-measure establishing shots rare.",
    },
    "mosaic": {
        "blurb": "restless: the tier structure changes on every page",
        "density": {1: 0.10, 4: 0.14, 5: 0.34, 6: 0.42},
        "tier_note": "Rotate through [1,2,3], [3,1,2], [2,3,1], [1,3,2], [2,1,3], [3,2,1]. No "
                     "two consecutive pages may share a tier structure.",
    },
}

ORDER = sorted(PROFILES)

# Share of grid panels that should run off a page edge.
#
# The bleed machinery is fully built -- spec_panels.apply_bleed() sizes the cell and
# build_comic draws it -- but the script generator never asked for one, so the last issue used
# ZERO bleeds across 396 grid panels. That is most of why its pages read as tiled boxes rather
# than designed spreads. Kept modest and profile-dependent: a bleed is emphasis, and a page
# where everything bleeds has no emphasis left.
BLEED_SHARE = {
    "cinematic": 0.30,      # the widescreen look leans on images running off the page
    "mosaic": 0.22,
    "classic": 0.18,
    "chamber": 0.15,        # enclosure comes from the frame, so bleeds stay sparing
    "staccato": 0.12,       # hard cuts want hard edges
    "documentary": 0.08,    # a dossier page is deliberately contained
}


def profile_for(case_id):
    """Deterministic per-case profile. Same case -> same look, forever.

    Hash rather than round-robin: a counter would make the ledger's order decide the look, so
    inserting one case would reshuffle every comic after it and break reproducibility.
    """
    h = hashlib.sha1((case_id or "").encode("utf-8")).hexdigest()
    return ORDER[int(h[:8], 16) % len(ORDER)]


def avg_panels_per_page(name):
    """Expected panels per page for a profile.

    The pipeline's panel floor was a flat `pages * 2.2`, which is fine for one fixed rhythm but
    fights a profile system: a deliberately sparse issue would be pushed back toward density by
    a floor it never agreed to, and the audit would then read red forever. Callers should size
    the panel budget from this instead of a constant.
    """
    return sum(n * w for n, w in PROFILES[name]["density"].items())


def density_line(name):
    d = PROFILES[name]["density"]
    parts = []
    for n in sorted(d):
        label = "single-panel splash pages" if n == 1 else f"{n}-panel pages"
        parts.append(f"~{round(d[n] * 100)}% {label}")
    return ", ".join(parts)


def prompt_block(case_id):
    """The paragraph injected into the script-generation prompt."""
    name = profile_for(case_id)
    p = PROFILES[name]
    return (
        f'LAYOUT PROFILE FOR THIS ISSUE: "{name}" -- {p["blurb"]}.\n'
        f"- Distribute page types as: {density_line(name)}.\n"
        f"- {p['tier_note']}\n"
        f"- Give EVERY grid page an explicit \"rows\" structure, and vary it page to page. The\n"
        f"  previous issue measured 12% splash and 88% six-panel pages, every one ruled up\n"
        f"  identically -- that reads as a template, not a comic. The tier structure is what\n"
        f"  the reader feels, not just the panel count.\n"
        f"- Use ONLY these structures. Others ask for unreadable slivers on this trim and the\n"
        f"  planner will discard them:\n"
        f"    6 panels: [1,2,3] [1,3,2] [2,1,3] [2,3,1] [3,1,2] [3,2,1]\n"
        f"    5 panels: [1,1,3] [1,2,2] [1,3,1] [2,1,2] [2,2,1] [3,1,1]\n"
        f"    4 panels: [1,1,2] [1,2,1] [2,1,1]\n"
        f'- Use bleeds. Any panel may carry "bleed": a list of page edges it runs off, from\n'
        f'  "left" "right" "top" "bottom" -- only edges that panel actually touches. The last\n'
        f"  issue used ZERO bleeds across 396 grid panels, which is why its pages read as tiled\n"
        f"  boxes. Bleed roughly {int(BLEED_SHARE[profile_for(case_id)] * 100)}% of panels on\n"
        f"  this issue, on establishing shots and dramatic beats -- never on a panel whose\n"
        f"  caption sits near the bleeding edge.\n"
        f"- The percentages above are checked after generation and reported. Treat them as a\n"
        f"  target to hit, not a suggestion.\n"
    )


def audit(script, case_id, tolerance=0.15):
    """Compare a generated script against its profile. Returns (ok, report_lines).

    The old target lived only in prose and was never checked, which is exactly how a 59%
    instruction became an 85% outcome. Measuring it is the whole point.
    """
    name = profile_for(case_id)
    want = PROFILES[name]["density"]

    counts = {}
    pages = [p for p in script.get("pages", []) if p.get("type") in ("grid", "splash")]
    for pg in pages:
        if pg.get("type") == "splash":
            n = 1
        else:
            n = sum(len(row) for row in pg.get("rows", []))
        counts[n] = counts.get(n, 0) + 1

    total = sum(counts.values()) or 1
    lines = [f'layout profile: "{name}"  ({total} story pages)']
    ok = True
    for n in sorted(set(list(want) + list(counts))):
        got = counts.get(n, 0) / total
        exp = want.get(n, 0.0)
        flag = ""
        if abs(got - exp) > tolerance:
            flag = "  <-- OFF TARGET"
            ok = False
        label = "splash" if n == 1 else f"{n}-panel"
        lines.append(f"  {label:>9}: got {got * 100:5.1f}%   want {exp * 100:5.1f}%{flag}")
    return ok, lines
