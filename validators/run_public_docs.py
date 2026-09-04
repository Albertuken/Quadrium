"""
The documents a stranger reads first, checked against the tree they describe.

WHY THIS EXISTS
-----------------
`run_docs_current.py` audits `CLAUDE.md` and `INDEX.md` — the documents this
project writes for itself — and it has caught a stale count on nearly every
session that changed one. The two documents a stranger actually reads,
`README.md` and `docs/GUIDE.md`, had no such check, and by 2026-09-01 both were
wrong:

    README   "Sixty-seven validators" / "67 runnable checks"   -- there were 94
    README   "40 unit tests"                                   -- there were 54
    GUIDE    "Multi-region tables. Single-region only."         -- false since
             "Regional disaggregation. Sectors, not territories."  v1.81/v1.83

The counts drifted because nothing counted. The two capability claims are worse
than drift: they were true when written and were made false by the engine's own
progress, which is the failure mode a project that ships features fastest is
most exposed to. A reader who believes them declines to try the thing that works.

WHAT IS CHECKED, AND WHY THESE THINGS
---------------------------------------
Counts, because they rot silently. Every long option of the command line,
because a feature nobody documents is a feature nobody finds. And **the list of
what the engine will not do**, item by item, against what it demonstrably does —
that is the check that would have caught both false sentences the day the
feature landed, and it is the reason this file is not just three `len()` calls.

FINDING THE TWO DOCUMENTS
---------------------------
`docs/GUIDE.md` is written in the private tree and copied out; `README.md` is
maintained in the public one. So each tree holds one of them at hand and the
other in its sibling, and this file looks in both places rather than passing on
whichever it happens to find. A check that skips half its subject is the kind of
vacuous pass this project removes validators for.

Run:
    python3 validators/run_public_docs.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
FAIL: list[str] = []

# Options argparse defines that no user guide needs to explain.
UNDOCUMENTED_OK = {"--help"}

# Each claim in the guide's "what it will not do" list, paired with the thing
# whose existence would make it false. Adding a capability without revisiting
# the list is exactly what happened; this makes it impossible to do twice.
WONT_DO = (
    ("Multi-region tables", "multi-region tables",
     lambda: _has_attr("quadrium.models", "IOTable", "region_codes")),
    ("Regional disaggregation", "regionalisation",
     lambda: _module_exists("quadrium.regionalise")),
)


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def _module_exists(name: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(name) is not None


def _has_attr(module: str, cls: str, attr: str) -> bool:
    import importlib
    try:
        return attr in getattr(importlib.import_module(module), cls).__dataclass_fields__
    except Exception:
        return False


def _find(name: str, sub: str = "") -> Path | None:
    """The document, whether this is the public tree or its private sibling."""
    here = ROOT / sub / name if sub else ROOT / name
    if here.exists():
        return here
    sibling = ROOT.parent / "Quadrium" / (f"{sub}/{name}" if sub else name)
    return sibling if sibling.exists() else None


def _count_tree(base: Path):
    """What the README's OWN repository holds.

    Counted beside the README and not beside this file, because the public tree
    ships fewer validators than the private one -- several read a methodological
    library or data that is not redistributed. Counting here would make the
    README wrong in the private tree and right in the public one, which is the
    same class of mistake this file exists to catch.
    """
    vdir = base / "library" / "validators"
    if not vdir.exists():
        vdir = base / "validators"
    n_val = len(list(vdir.glob("run_*.py"))) + len(list(vdir.glob("check_*.py")))
    tests = base / "tests" / "test_engine.py"
    n_tests = (len(re.findall(r"^def (test_\w+)", tests.read_text(), re.M))
               if tests.exists() else 0)
    ex = base / "examples"
    return n_val, n_tests, len(list(ex.glob("*.py"))) if ex.exists() else 0


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    readme = _find("README.md")
    guide = _find("GUIDE.md", "docs")
    check("both documents a stranger reads are reachable from here",
          readme is not None and guide is not None,
          f"README {readme}, GUIDE {guide}")
    if readme is None or guide is None:
        return 1

    rt, gt = readme.read_text(), guide.read_text()
    n_val, n_test, n_ex = _count_tree(readme.parent)

    # ---- the counts
    print()
    print(f"    {'':<28}{'the tree':>10}{'the README says':>20}")
    claims = {}
    for label, pat, actual in (
            ("validators", r"(\d+)\s+runnable checks", n_val),
            ("unit tests", r"(\d+)\s+unit tests", n_test),
            ("worked examples", r"(\w+)\s+worked pilots", n_ex)):
        m = re.search(pat, rt)
        said = m.group(1) if m else "—"
        claims[label] = (said, actual)
        print(f"    {label:<28}{actual:>10}{said:>20}")

    for label in ("validators", "unit tests"):
        said, actual = claims[label]
        check(f"the README's count of {label} is the tree's",
              said.isdigit() and int(said) == actual,
              f"says {said}, the tree has {actual}")

    # The pilots are written as a word, not a digit.
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
    said, actual = claims["worked examples"]
    check("and its count of worked examples is too",
          words.get(said.lower(), -1) == actual,
          f"says {said!r}, examples/ holds {actual}")

    # ---- prose counts, which drift separately from the layout block
    for pat, actual, what in ((r"Sixty-seven|Sixty‑seven", n_val, "validators"),):
        stale = re.search(pat, rt)
        check(f"and no spelled-out count of {what} contradicts it",
              stale is None,
              f"found {stale.group(0)!r} in the prose while the tree has "
              f"{actual}" if stale else "none in the prose")

    # ---- every option the command line offers is in the guide
    print()
    from quadrium import cli
    import argparse
    seen = set()
    parser_opts = set()
    for line in Path(cli.__file__).read_text().splitlines():
        m = re.search(r'ap\.add_argument\("(--[a-z-]+)"', line)
        if m:
            parser_opts.add(m.group(1))
    missing = sorted(o for o in parser_opts
                     if o not in UNDOCUMENTED_OK and o not in gt)
    check("every option the command line offers appears in the guide",
          not missing,
          f"{len(parser_opts)} options, all documented" if not missing
          else f"missing: {', '.join(missing)}")

    # ---- and the guide does not deny something the engine does
    print()
    for phrase, what, does in WONT_DO:
        wont = re.search(rf"^-\s+\*\*{re.escape(phrase)}", gt, re.M)
        check(f"the guide does not say it cannot do {what}",
              not (wont and does()),
              f"the list still carries {phrase!r} while the engine has it"
              if wont and does() else
              (f"{phrase!r} is not claimed as a limitation" if does()
               else f"the engine does not have it, so the claim stands"))

    # ---- the four worked examples, which the guide never mentioned until
    # v1.84: the README listed them and the tutorial did not, so the route a
    # reader is actually walked down never met them.
    ex_dir = readme.parent / "examples"
    scripts = sorted(p.name for p in ex_dir.glob("*.py")) if ex_dir.exists() else []
    unmentioned = [n for n in scripts if n not in gt]
    check("the guide names every worked example, not just the README",
          scripts and not unmentioned,
          f"{len(scripts)} in examples/, all named in the guide" if not unmentioned
          else f"missing from the guide: {', '.join(unmentioned)}")

    # ---- and there is something to look at without installing anything
    print()
    # Beside the README, not beside this file: the question is what the PUBLIC
    # repository ships, and the private tree's own outputs/ are working runs.
    runs = readme.parent / "outputs"
    published = ([p for p in runs.iterdir()
                  if p.is_dir() and (p / "report.md").exists()]
                 if runs and runs.is_dir() else [])
    check("a finished run is published, so the output can be read without "
          "installing anything",
          bool(published),
          f"{', '.join(p.name for p in published)}" if published else
          "outputs/ holds no run with a report.md. The owner asked to see what "
          "a user would see before installing, and nothing here answers that")
    if published:
        named = [p.name for p in published if p.name in rt or p.name in gt]
        check("and it is linked from a document, not merely present",
              bool(named),
              f"{', '.join(named)} is named in the README or the guide — a "
              f"folder nobody mentions is a folder nobody finds")

        # A PUBLISHED RUN NEEDS A PAGE THAT SAYS WHAT IT WAS.
        # `report.md` is the engine's verbatim output, which is the right thing
        # to publish and the wrong thing to hand somebody first: it opens on
        # solver diagnostics. A reader deciding whether this is worth their
        # afternoon needs the question, the inputs and the answer.
        # Read from the PUBLIC tree, like everything else in this section, and
        # the narration lives only there. It is a public artefact: it exists so
        # a reader can judge the work without installing, and a second copy in
        # the private tree that sync_public.py does not carry would be two
        # sources of truth waiting to disagree.
        for run in published:
            page = run / "README.md"
            report = (run / "report.md").read_text()
            check(f"{run.name} says what it WAS, not only what it printed",
                  page.exists(),
                  "README.md beside report.md" if page.exists() else
                  "report.md opens on solver diagnostics; a reader deciding "
                  "whether to spend an afternoon on this needs the question, "
                  "the inputs and the answer first")
            if not page.exists():
                continue

            # AND ITS FIGURES MUST BE THE RUN'S.
            # This file exists because counts rot when nothing counts them.
            # A narration quoting figures from a report that has since been
            # regenerated is the same failure in a more persuasive form.
            quoted = set(re.findall(r"\b\d{1,3}(?:,\d{3})+\.\d\b|\b1\.\d{3}\b",
                                    page.read_text()))
            missing = sorted(q for q in quoted if q not in report)
            check(f"and every figure {run.name}'s page quotes is in the report "
                  f"it narrates",
                  not missing,
                  f"{len(quoted)} figures checked against report.md, all "
                  f"present" if not missing else
                  f"not in the report: {', '.join(missing[:6])}")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
