"""Keep the Gumroad storefront in step with the catalogue (store_sync.yml, hourly).

    cd pipeline_lib && python -m store_design.sync [--dry-run]

1. Any PUBLISHED comic whose landing page is not in this design (a build that fell back to the
   old template, or a comic made before it) gets one, built from its current page's own text.
2. --cut-issues 54,55: cut CANDIDATE characters for existing comics from their committed carousel
   slides (on the Actions runner, not a laptop). Nothing goes live from this.
   --approve 54_3_1,56_4_4: move reviewed candidates into chars/ and re-render those comics.
   --refresh-issues 54,56: re-render those comics' landing pages (e.g. after removing a character).
3. The store pages (home + /case-files-N) are rebuilt from the product list and pushed only when
   their HTML differs from what was last pushed (state.json).

Publication is read from the Gumroad API's `published` field -- never from a page answering 200,
because a draft's page answers 200 too.
"""
import argparse
import glob
import hashlib
import json
import os

from . import cases, landing, publish, store_pages

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")
REPO = os.path.dirname(os.path.dirname(HERE))


def _load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def cut_characters(issues):
    from . import characters

    cut = {}
    for n in issues:
        entries = glob.glob(os.path.join(REPO, "carousel", "entries", f"{n:03d}-*.json"))
        if not entries:
            print(f"#{n}: no carousel entry -- no pages to cut from")
            continue
        with open(entries[0], encoding="utf-8") as f:
            d = json.load(f)["dir"]
        slides = [os.path.join(REPO, "carousel", d, f"{i}.jpg") for i in (2, 3, 4)]
        cut[n] = characters.cut_issue(n, [s for s in slides if os.path.exists(s)])
        print(f"#{n}: candidate characters {cut[n] or 'none usable'}")
    return cut


CANDIDATES = os.path.join(HERE, "candidates")


def _close(issue):
    """The owner's decision is made: drop the issue's remaining candidates, sheet and manifest."""
    for path in glob.glob(os.path.join(CANDIDATES, f"{issue:02d}_*")):
        os.remove(path)


def approve(keys):
    """The owner's picks go live; the rest of those issues' candidates are dropped."""
    issues = set()
    for key in keys:
        src = os.path.join(CANDIDATES, f"{key}.json")
        if not os.path.exists(src):
            print(f"::warning::no candidate {key}")
            continue
        os.replace(src, os.path.join(HERE, "chars", f"{key}.json"))
        issues.add(int(key.split("_", 1)[0]))
        print(f"approved {key}")
    for n in issues:
        _close(n)
    return issues


def auto_approve(products):
    """A comic PUBLISHED with nothing picked gets its top candidates (the owner's rule)."""
    from .characters import AUTO_PICK

    published = {store_pages.issue_no(p["name"]) for p in store_pages.live_issues(products)}
    issues = set()
    for path in glob.glob(os.path.join(CANDIDATES, "*_pending.json")):
        with open(path, encoding="utf-8") as f:
            pending = json.load(f)
        n = int(pending["issue"])
        if n not in published:
            continue
        for key in pending["ranked"][:AUTO_PICK]:
            src = os.path.join(CANDIDATES, f"{key}.json")
            if os.path.exists(src):
                os.replace(src, os.path.join(HERE, "chars", f"{key}.json"))
                print(f"#{n} published with no pick -- auto-approved {key}")
        _close(n)
        issues.add(n)
    return issues


def upgrade_landings(products, dry_run, force=()):
    done, failed = [], []
    for p in store_pages.live_issues(products):
        try:
            current = cases.live_landing(p)
        except Exception as e:
            failed.append((p["name"], f"could not read live page: {e}"))
            continue
        n = store_pages.issue_no(p["name"])
        if current and cases.V2_MARKER in current and n not in force:
            continue
        page = landing.build_html(cases.from_live_page(p, current), cases.related(products, n))
        if dry_run:
            done.append(p["name"])
            continue
        ok, err = publish.publish_landing(p["id"], page)
        (done if ok else failed).append(p["name"] if ok else (p["name"], err))
    return done, failed


def sync_store(products, dry_run):
    state = _load_state()
    pages = store_pages.build_pages(products, publish.user_bio())
    existing = None
    pushed, failed = [], []
    for k, (slug, html) in enumerate(pages.items(), 1):
        digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
        if state.get(slug) == digest:
            continue
        if dry_run:
            pushed.append(slug)
            continue
        if existing is None:
            existing = publish.list_pages()
        ok, err = publish.push_store_page(slug, html, f"Case Files · Page {k}", existing)
        if ok:
            state[slug] = digest
            pushed.append(slug)
        else:
            failed.append((slug, err))
    if not dry_run:
        with open(STATE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(state, f, indent=1, sort_keys=True)
            f.write("\n")
    return pushed, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cut-issues", default="", help="comma-separated issue numbers")
    ap.add_argument("--approve", default="", help="comma-separated candidate keys, e.g. 54_3_1")
    ap.add_argument("--refresh-issues", default="", help="comma-separated issue numbers")
    a = ap.parse_args()

    def _list(value):
        return [x for x in value.replace(" ", "").split(",") if x]

    if a.cut_issues:
        cut_characters([int(x) for x in _list(a.cut_issues)])
    force = approve(_list(a.approve)) | {int(x) for x in _list(a.refresh_issues)}
    products = publish.list_products()
    if not a.dry_run:
        force |= auto_approve(products)
    upgraded, bad_landings = upgrade_landings(products, a.dry_run, force)
    pushed, bad_pages = sync_store(products, a.dry_run)
    print(f"landing pages upgraded: {upgraded or 'none'}")
    print(f"store pages pushed: {pushed or 'none (unchanged)'}")
    for item in bad_landings + bad_pages:
        print(f"::error::{item}")
    if bad_landings or bad_pages:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
