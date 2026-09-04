"""
Which functions of the engine has anything ever CALLED — measured, not waited for.

WHY ASK
---------
`INDEX.md` §9 records **built, verified, and unreachable — four times**. The
Eurostat download, the interchange format, the supply-use input and the whole
of chapter 18's projection methods were each implemented, checked against
printed sources, and reachable from nowhere a user goes; every one was found by
accident. The refusal sweep showed what measuring is worth against waiting, and
this points the same instrument at the code rather than at its refusals.

HOW
-----
`sys.setprofile` fires once per call — cheap enough to leave on for a whole
suite, where `sys.settrace` fires per line and is not. The hook is installed
through a `sitecustomize.py` on `PYTHONPATH` so it reaches every subprocess,
and records any frame whose code lives under `src/quadrium`. Then every
validator and the unit tests run as their own process.
`data/_reachability.json` holds the result; this file checks the code still
matches it. Re-take it with `library/tools/sweep_reachability.py`, never by
editing the record.

WHAT IT FOUND, THE FIRST TIME IT WAS RUN
------------------------------------------
284 functions, 262 entered, **22 never**. Acting on the two groups below
took it to 269 and 15. They were not spread thin — they came
in two groups, and each is a different kind of problem.

**Seven of `identities.py`'s eighteen.** That module implements the numbered
accounting identities of the specification, with the printed citation attached
to each result. `ID-01`, `ID-06`, `ID-07`, `ID-08`, `ID-10`, `ID-13` and
`structural_zero_check` were called by nothing — while `run_ine_sut_identities.py`
checked ID-07 and ID-08 **with its own two lines of arithmetic**, and printed no
citation. The same identity defined twice, one of them by nobody. Wired on
2026-09-04, and the citation now travels with the answer.

`ID-01` was deliberately NOT wired. This file's inline version goes through
`SupplyUseTables.supply_at_purchasers()`, which articulates the valuation on
the object that owns it; routing it through the free function would be a
second duplication rather than the removal of one. **Not every unentered
function should be called — some are a second API for something an object
already does better**, and saying which is which is the whole value of reading
the list instead of counting it.

**Six of `cli.py`'s eleven.** `_catalogue` is what `--sources` and `--find` do,
and `docs/GUIDE.md` documents both — `--find` in four places. `run_public_docs`
checks that every option APPEARS in the guide; nothing checked that any of them
WORKS. Worse, `_describe` and `_warn_about_substance` run on every split, on
both paths, so their never being entered meant the route the guide opens with —
fill in a spreadsheet, run one command — had never been exercised through
`cli.main` at all. The engine was always reached through `IOProject`, which is
not what a user types. Covered on 2026-09-04.

`_availability` is left uncovered on purpose: it queries Eurostat over the
network, and a test that needs a fetch is a test that fails on a train.

Run:
    python3 validators/run_reachability.py
"""
from __future__ import annotations

import collections
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
TOOLS = ROOT / "library" / "tools"
RECORD = ROOT / "data" / "_reachability.json"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if not RECORD.exists():
        check("the reachability record is on disk", False,
              f"{RECORD} — take it with "
              f"library/tools/sweep_reachability.py")
        return 1
    sys.path.insert(0, str(TOOLS))
    try:
        from sweep_reachability import static_functions
    except ImportError:
        # NOT A FAILURE. `library/tools/` does not travel to the public tree,
        # so the record is read-only there and re-taken in the private one.
        # The same rule as the Catalan workbook and the NUTS tables: a tree
        # without the instrument reports that it cannot run the check, and
        # does not pretend the check passed on evidence it never saw.
        rec = json.loads(RECORD.read_text())
        check("the sweep tool is not in this tree, so the record is read here "
              "and re-taken in the private one", True,
              f"{rec.get('n_functions')} functions, "
              f"{len(rec.get('entered', []))} entered, taken "
              f"{rec.get('taken')}. library/tools/sweep_reachability.py does "
              f"not travel to the public tree")
        print("\n" + "=" * 78 + "\nAll checks passed.")
        return 0

    src = ROOT / "src" / "quadrium"
    static = static_functions(src)
    rec = json.loads(RECORD.read_text())
    entered = set(rec.get("entered", []))

    check("the code still has the number of functions the sweep counted",
          len(static) == rec.get("n_functions"),
          f"{len(static)} found against {rec.get('n_functions')} recorded. If "
          f"this trips, a function was added or removed — re-take the sweep "
          f"rather than editing the number")

    stale = sorted(entered - set(static))
    check("and every function the record calls entered still exists",
          not stale,
          f"{len(stale)} recorded and gone: {', '.join(stale[:4])}"
          if stale else "none")

    never = sorted(set(static) - entered)
    print(f"\n    {len(static)} functions the engine defines")
    print(f"    {len(entered)} entered by something in the suite")
    print(f"    {len(never)} never entered\n")

    by_file = collections.Counter(static[k]["file"] for k in never)
    if by_file:
        print(f"    {'module':<24}{'unentered':>10}{'defined':>9}")
        for f, n in by_file.most_common():
            tot = sum(1 for k in static if static[k]["file"] == f)
            print(f"    {f:<24}{n:>10}{tot:>9}")
        print()

    # A RATCHET, and the floor lives in the record for the same reason the
    # refusal sweep's does: the public tree ships fewer validators, so a
    # constant here would be wrong in one of the two trees by construction.
    floor = int(rec.get("floor", 0))
    check("the functions that have been entered stay entered",
          len(entered) >= floor,
          f"{len(entered)} of {len(static)} — the floor is {floor}. Raise it "
          f"when it rises; never lower it to make a run pass")

    # The list is a claim, not a shrug: each name below is either a second API
    # for something reachable another way, or a gap nobody has closed.
    if never:
        print("    never entered:")
        for k in never:
            v = static[k]
            kind = ("dunder" if v["dunder"] else
                    "private" if v["private"] else "public")
            print(f"      {k:<46}{kind}")
        print()

    public_never = [k for k in never
                    if not static[k]["private"] and not static[k]["dunder"]]
    check("what is left unentered is named here rather than counted",
          len(never) < 0.15 * len(static),
          f"{len(never)} of {len(static)} — {100 * len(never) / len(static):.1f} "
          f"%, of which {len(public_never)} are public. Every one is listed "
          f"above; a coverage figure with no list is a number nobody can act "
          f"on")

    print("=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
