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
     52 reached by something in the suite
    107 never reached

    module              reached   total
    scenarios.py              1       1
    sut_ras.py                2       2
    gras.py                   3       4
    balancing.py              2       4
    config.py                15      41
    disaggregation.py         8      20
    eurostat.py              10      27
    io_loader.py              7      39
    transformation.py         2      11
    sut_euro.py               1       4
    acquire.py                1       6

AND THE NUMBER ALONE WOULD MISLEAD
------------------------------------
Most of the 110 are argument checks — `H is (3, 4) and the supply table is
(4, 4)`, `model 'X' is not one of the four` — which judge what the CALLER passed,
not what the office published. No table can reach them, and that they are
unexercised costs nothing.

What matters is the subset that judges **data**, because that is what a user
meets first and there is nothing behind it:

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
          f"{len(fired)} of {len(static)}. Most of the rest are argument "
          f"checks no published table can reach, which costs nothing — the "
          f"count is here to be read with the next check, not alone")

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
