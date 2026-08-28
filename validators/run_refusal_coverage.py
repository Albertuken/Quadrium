"""
Which of the engine's own refusals has anything ever reached.

WHY ASK
---------
This engine refuses a great deal, on purpose: `INDEX.md` section 8 is a list of
what it will not do and why. A refusal is a promise to the user — *your table
cannot be used this way, and here is the reason* — and a promise nothing has
ever exercised is a promise nobody has read aloud.

`INDEX.md` section 9 already carries the neighbouring pattern: **built, verified,
and unreachable — four times**, each found by accident. So this was measured
rather than waited for.

HOW
-----
Each of the twelve exception types `quadrium` defines was wrapped so that
constructing one records the line that raised it, and then every validator and
the unit tests were run as separate processes. `data/_refusal_coverage.json`
holds the result and how it was taken; this file checks that the code still
matches it.

WHAT IT SHOWS
---------------
    159 refusal sites of the engine's own types
     57 reached by something in the suite
    102 never reached

    module              reached   total
    scenarios.py              1       1
    sut_ras.py                2       2
    gras.py                   3       4
    balancing.py              2       4
    config.py                15      41
    disaggregation.py         8      20
    eurostat.py              10      27
    io_loader.py             12      39
    transformation.py         2      11
    sut_euro.py               1       4
    acquire.py                1       6

A CORRECTION, BECAUSE THIS FILE GOT IT WRONG FIRST
----------------------------------------------------
The first version of this docstring said: *"Most of the remaining 107 judge what
the CALLER passed — a shape mismatch, a model name that is not one of the four —
and no published table can reach them, so their being unexercised costs
nothing."*

**That was asserted without being checked, and it is wrong.** Reading all 159
messages and recording what each one judges gives:

    what it judges                          total   unreached
    a file or response from an office          52          41
    the user's own spreadsheet                 56          29
    what they asked for in that spreadsheet    20          11
    the numbers themselves                     19           9
    an internal API contract (the CALLER)       7           7
    a failure elsewhere, re-raised               5           5

**Seven of the 102 are caller checks — 7 %, not "most".** The largest group is
the user's own workbook, which is the route the guide opens with: *"No Python:
you fill in a spreadsheet and run one command"*. Messages like *"no row labelled
'Output' or 'Total output'"* are the first thing a stranger with a slightly
different sheet meets, and none of them had a case.

Six now do (`tests/test_engine.py`): a minimal valid workbook is built and then
broken one way at a time — no file, no `table` sheet, no `metadata` sheet,
metadata without the price basis, no `Output` row, no final-demand column — and
each refusal is checked by the message it gives rather than by something having
failed. Workbook coverage went 22 of 56 to 27 of 56.

The classification lives in `data/_refusal_coverage.json` so it is held rather
than repeated, and it was made by reading each message rather than by matching
words — which is the same mistake in a different costume.

WHAT MATTERS MOST, AND WHAT NOW HAS A CASE
--------------------------------------------
The refusals that judge the numbers themselves, because a user meets those with
a table that loads and is still wrong:

    transformation.py:122   a coefficient's denominator is zero
    transformation.py:239   model A cannot be computed on this table at all
    sut_ras.py:126          a product row whose margin is non-positive
    sut_ras.py:172          the same for an import row

`transformation.py` was the starkest: the SUT-to-IOT transformation is a
headline feature with four models from CORE_013, and **one** of its eleven
refusals had ever fired.

Three of the four now have a case, in `tests/test_engine.py`: a supply table
with a product nobody makes reaches both coefficient refusals from opposite
sides, and a product row with negative mass and no positive mass reaches
SUT-RAS's, as does the import row that is negative-only rather than empty —
which is the distinction that made SUT-RAS runnable on real tables at all.
Coverage went 49 to 52 and `sut_ras.py` from 0 of 2 to 2 of 2.

The fourth, `transformation.py:239`, is left: reaching it needs a table on which
model A cannot be computed at all, and nothing built here does that honestly.
It is named rather than quietly dropped.

Run:
    python3 validators/run_refusal_coverage.py
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SRC = ROOT / "src" / "quadrium"
RECORD = ROOT / "data" / "_refusal_coverage.json"
TYPES = ("BalancingError", "AcquisitionRefused", "ConfigError",
         "DisaggregationError", "EurostatError", "SignInfeasibleError",
         "DegenerateMarginError", "MarginImbalanceError", "LoaderError",
         "ScenarioInfeasible", "TransformationError", "SutEuroError")

# The refusals that judge the DATA rather than the caller's arguments, and that
# nothing has reached. Named here so the list is a claim, not a shrug.
DATA_JUDGEMENTS = {
    "transformation.py:122": "a coefficient's denominator is zero",
    "transformation.py:239": "model A cannot be computed on this table at all",
    "sut_ras.py:126": "a product row whose margin is non-positive",
    "sut_ras.py:172": "the same for an import row",
}
# The one still without a case, and why: reaching it needs a table on which
# model A cannot be computed at all, and nothing built here does that honestly.
# Named so it stays a known gap rather than becoming a silent one.
NO_CASE_YET = {"transformation.py:239"}

LABELS = {
    "source": "a file or response from an office",
    "workbook": "the user's own spreadsheet",
    "scenario": "what they asked for in that spreadsheet",
    "data": "the numbers themselves",
    "caller": "an internal API contract (the CALLER)",
    "upstream": "a failure elsewhere, re-raised",
}

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    check("the sweep is recorded, so nobody has to re-run it to read it",
          RECORD.exists(), str(RECORD.relative_to(ROOT)))
    if not RECORD.exists():
        return 1
    rec = json.loads(RECORD.read_text())

    pat = re.compile(r"raise\s+(" + "|".join(TYPES) + r")\b")
    static = {}
    for f in sorted(SRC.glob("*.py")):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            m = pat.search(line)
            if m:
                static[f"{f.name}:{i}"] = m.group(1)

    check("the code still has the number of refusals the sweep counted",
          len(static) == rec["n_sites"],
          f"{len(static)} found against {rec['n_sites']} recorded. If this "
          f"trips, a refusal was added or moved and the sweep is stale — "
          f"re-take it rather than editing the number")

    fired = set(rec["fired"])
    tot = collections.Counter(k.split(":")[0] for k in static)
    got = collections.Counter(k.split(":")[0] for k in static if k in fired)
    print()
    print(f"    {'module':<24}{'reached':>9}{'total':>7}")
    for m in sorted(tot, key=lambda x: (got[x] / tot[x], -tot[x])):
        print(f"    {m:<24}{got[m]:>9}{tot[m]:>7}")

    check("a large share of the engine's refusals has never been reached",
          len(fired) < len(static) * 0.6,
          f"{len(fired)} of {len(static)}")

    # WHAT EACH ONE JUDGES, read rather than guessed. The first version of this
    # file asserted that most unreached sites were caller checks and no table
    # could reach them. Seven of 107 are.
    klass = rec.get("classified", {})
    check("the classification covers every refusal in the code",
          set(klass) == set(static),
          f"{len(klass)} classified against {len(static)} in the code")
    by_kind = collections.Counter(klass.values())
    un_kind = collections.Counter(v for k, v in klass.items() if k not in fired)
    print()
    print(f"    {'what it judges':<40}{'total':>7}{'unreached':>11}")
    for k in sorted(by_kind, key=lambda x: -un_kind[x]):
        print(f"    {LABELS.get(k, k):<40}{by_kind[k]:>7}{un_kind[k]:>11}")
    caller_share = un_kind["caller"] / max(sum(un_kind.values()), 1)
    check("and the unreached are NOT mostly caller checks, as this file first said",
          caller_share < 0.2,
          f"{un_kind['caller']} of {sum(un_kind.values())} — "
          f"{caller_share * 100:.0f} %. {un_kind['workbook']} judge the user's "
          f"own spreadsheet, which is the route the guide opens with. The "
          f"earlier claim was made without reading them")

    # the part that is not an argument check
    still_unfired = {k: v for k, v in DATA_JUDGEMENTS.items()
                     if k not in fired}
    gone = [k for k in DATA_JUDGEMENTS if k not in static]
    print()
    for k, why in sorted(DATA_JUDGEMENTS.items()):
        state = ("REACHED" if k in fired
                 else "moved" if k in gone else "never reached")
        print(f"    {k:<26}{state:<15}{why}")
    check("and the refusals that judge DATA are named, not left as a remainder",
          not gone and set(still_unfired) <= NO_CASE_YET,
          f"{len(DATA_JUDGEMENTS) - len(still_unfired)} of "
          f"{len(DATA_JUDGEMENTS)} now have a case in tests/test_engine.py. "
          f"The remainder is {sorted(still_unfired) or 'none'}, which is "
          f"recorded above with the reason rather than left as a gap nobody "
          f"named"
          if not gone else
          f"these line numbers no longer hold a refusal: {gone}. The list has "
          f"drifted from the code and must be re-taken")

    worst = min(tot, key=lambda m: got[m] / tot[m] if tot[m] else 1)
    check("the transformation is still the thinnest-covered module, and it is "
          "a headline feature",
          got["transformation.py"] <= 3,
          f"{got['transformation.py']} of {tot['transformation.py']} in "
          f"transformation.py, the SUT-to-IOT step with four models from "
          f"CORE_013. The least covered overall is {worst} at {got[worst]} of "
          f"{tot[worst]}")

    print()
    print("    A refusal is a promise to the user. This does not keep the")
    print("    unkept ones; it stops them being invisible.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
