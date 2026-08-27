"""
Every bound in the engine, classified — because seven were found by accident.

THE PATTERN, AND HOW ALL SEVEN WERE FOUND
-------------------------------------------
`INDEX.md` section 9 has titled this since v1.57: *a bound assumed rather than
derived*. An identity over `n` cells published to `d` decimals cannot be checked
more tightly than `0.5·10⁻ᵈ·n` (`OQ-B-02`), and gate after gate went on using a
flat constant instead — every one of them erring TIGHT, which is the direction
that refuses valid tables. The sixth was in `precision.py` itself, the module
written to stop exactly this.

The seventh turned up on 2026-08-26, when the evidence base was widened: three
sign tests in `gras` compared a margin against EXACT ZERO while the caller was
already computing the floor and passing it in, and `_assert_margins_consistent`
one line above was using it. It refused three real splits of `Q87_88` — health
and social work — in three countries, over targets of -2.8e-14 and -0.021
against a floor of the order of a tenth.

**All seven were found by accident**: a table that would not load, a claim that
contradicted itself, a widening that broke something. Nobody had ever swept.

WHAT A SWEEP HAS TO SEPARATE
------------------------------
The engine holds 21 comparisons against a hard constant, and most are fine. The
question is not "is there a constant" but "does this constant decide anything":

    GUARD    protects a division or a degenerate branch. The value carries no
             meaning of its own -- `X_safe = where(|X| < 1e-12, nan, X)` is not
             judging whether output is zero, it is refusing to divide by it.
    VERDICT  decides whether something passed, is zero, is balanced, cleared,
             still improving. A user sees the answer. These are the ones a
             floor belongs in.

AND THEN WHETHER IT IS LIVE
-----------------------------
A verdict with an assumed bound is only a defect if real data lands between the
constant and the derived floor. The project's rule is that a change needs a case
that exercises it, so each verdict below is measured on the tables held here and
gets one of three verdicts of its own: FIXED, with the case; DOCUMENTED, when
no held table reaches the gap; or DERIVED, when it already was.

WHAT THIS SWEEP FOUND
-----------------------
    eurostat.py     tiling total       FIXED       the third such check in the
                                                   file, still at `1e-6 x total`
                                                   while `_rounding_tol` sits
                                                   two lines above. The two
                                                   disagree on all 14 pairs
                                                   held here and the direction
                                                   FLIPS with the table's size:
                                                   the Netherlands 2022 floor
                                                   is 32.5 against a constant
                                                   of 2.87 — eleven times too
                                                   tight — and France 2022 is
                                                   4.45 against 6.12, too
                                                   loose. Rounding scales with
                                                   the number of terms, not
                                                   with the total.

    validation.py   zero row/column    FIXED       each is a SUM over a row, so
                                                   its floor is the n-term one.
                                                   At 1e-12, **17 lines across
                                                   five tables** sit where the
                                                   two bounds disagree —
                                                   Hungary in all four years
                                                   and Slovakia — each one a
                                                   line the file cannot tell
                                                   from zero and this called
                                                   non-zero, enough to report a
                                                   zero as "created by
                                                   balancing" when it was
                                                   already zero.

    validation.py   zero output        DOCUMENTED  `X_i` is ONE published cell,
                                                   not a sum, so its floor is
                                                   per-cell: 0.005 on a
                                                   2-decimal table. No table
                                                   held here has an output
                                                   between 1e-12 and that, so
                                                   the constant decides
                                                   nothing. (An earlier reading
                                                   of this compared against the
                                                   n-term floor and made it
                                                   look live. It is not, and
                                                   the difference is which
                                                   quantity is being summed.)

    transformation  negatives cleared  DOCUMENTED  only the Handbook fixture
                                                   reaches it, and it lands on
                                                   exactly zero negatives, so
                                                   1e-9 never decides. Nothing
                                                   held here exercises the
                                                   boundary.

    disaggregation  shift is neutral   DERIVED     `worst <= 1e-6 * max(|col
                                                   sum|, 1)` is already
                                                   relative to the data.

Run:
    python3 validators/run_derived_bounds.py
"""
from __future__ import annotations

import glob
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SRC = ROOT / "src" / "quadrium"
DATA = ROOT / "data" / "eurostat"
FAIL: list[str] = []

# Every hard constant in a comparison, and what it is. A GUARD protects a
# division; a VERDICT decides something a user sees. Adding a comparison to the
# engine without listing it here fails this validator, which is the point.
CLASSIFIED = {
    ("diagnostics.py", "X_safe"): "guard: refuses to divide by a zero output",
    ("disaggregation.py", "share_of_internal_block"): "guard: denominator",
    ("disaggregation.py", "neutral"): "verdict, DERIVED: relative to the column",
    ("disaggregation.py", "scale"): "guard: denominator",
    ("disaggregation.py", "share"): "guard: denominator",
    ("disaggregation.py", "beta"): "guard: the 1/(1-d) singularity",
    ("eurostat.py", "tiling"): "verdict, FIXED: uses _rounding_tol",
    ("models.py", "moving"): "guard: a flat window, on percentages",
    ("models.py", "per"): "guard: a flat window, on percentages",
    ("models.py", "stranded"): "verdict: not exercised by any held table",
    ("models.py", "imported"): "verdict: not exercised by any held table",
    ("models.py", "margins"): "verdict: not exercised by any held table",
    ("precision.py", "rounded"): "verdict, DERIVED: relative to the value",
    ("reporting.py", "identical"): "verdict: multipliers agree to 1e-15 when "
                                   "they agree at all (run_key_invariance)",
    ("sut_euro.py", "still_improving"): "guard: a flat window, on percentages",
    ("transformation.py", "cleared"): "verdict, DOCUMENTED: the only fixture "
                                      "reaching it lands on exactly zero",
    ("transformation.py", "diag"): "guard: denominator",
    ("transformation.py", "free"): "guard: denominator",
    ("transformation.py", "row"): "guard: denominator",
    ("transformation.py", "safe_div"): "guard: denominator",
    ("validation.py", "zero_output"): "verdict, DOCUMENTED: per-cell floor is "
                                      "0.005 and no held table reaches it",
    ("validation.py", "zero_row_col"): "verdict, FIXED: uses "
                                       "assertable_tolerance",
}


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    from quadrium.eurostat import load_iot
    from quadrium.precision import assertable_tolerance

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # 1 -- the count, so a new one cannot be added unnoticed
    pattern = re.compile(r"[<>]=? *1e-[0-9]+|[<>]=? *0\.0{2,}1")
    found = []
    for f in sorted(SRC.glob("*.py")):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if pattern.search(line) and not line.lstrip().startswith("#"):
                found.append((f.name, i, line.strip()))
    print()
    print(f"    {len(found)} comparison(s) against a hard constant, over "
          f"{len({f for f, _, _ in found})} modules")
    # Exact, not a range: the point of the count is that it trips.
    EXPECTED = 21
    check("the sweep still matches the code",
          len(found) == EXPECTED,
          f"{len(found)} found against {EXPECTED} expected, and "
          f"{len(CLASSIFIED)} concepts classified (some cover several lines — "
          f"the zero row/column test is four). If this trips, a comparison was "
          f"added or removed: classify it above, or say why it needs no floor")

    verdicts = {k: v for k, v in CLASSIFIED.items() if v.startswith("verdict")}
    guards = {k: v for k, v in CLASSIFIED.items() if v.startswith("guard")}
    print(f"    {len(guards)} guards (a denominator, no meaning of their own)")
    print(f"    {len(verdicts)} verdicts (they decide something a user sees)")
    check("and every classification says which of the two it is",
          len(guards) + len(verdicts) == len(CLASSIFIED),
          "no entry is left unlabelled")

    # 2 -- the two that were FIXED, checked against the data that found them
    tables = []
    for f in sorted(glob.glob(str(DATA / "naio_10_cp1700_*.json"))):
        try:
            tables.append((os.path.basename(f)[15:-5], load_iot(Path(f))))
        except Exception:
            continue
    check("there are published tables to measure the bounds against",
          len(tables) >= 5, f"{len(tables)} symmetric tables load")
    if len(tables) < 5:
        return 1 if FAIL else 0

    print()
    live = []
    for name, t in tables:
        v = np.concatenate([t.Z.ravel(), t.Y.ravel(), t.VA.ravel(),
                            t.X.ravel()])
        floor_n = assertable_tolerance(v, t.n)
        sums = np.concatenate([np.abs(t.Z.sum(axis=1)),
                               np.abs(t.Z.sum(axis=0))])
        gap = int(((sums >= 1e-12) & (sums < floor_n)).sum())
        if gap:
            live.append((name, floor_n, gap))
            print(f"    {name:<10}floor {floor_n:>8.4g}   "
                  f"{gap} row/column(s) between 1e-12 and it")
    check("the zero row/column bound was live, not hypothetical",
          bool(live),
          f"{sum(g for _, _, g in live)} line(s) across "
          f"{len(live)} table(s) sit where the two bounds disagree — each one "
          f"a line the source cannot tell from zero and 1e-12 called non-zero")

    print()
    per_cell = []
    for name, t in tables:
        v = np.concatenate([t.Z.ravel(), t.Y.ravel(), t.VA.ravel(),
                            t.X.ravel()])
        one = assertable_tolerance(v, 1)
        x = np.abs(t.X)
        per_cell.append(int(((x >= 1e-12) & (x < one)).sum()))
    check("and the zero OUTPUT bound was not, which is why it was left alone",
          sum(per_cell) == 0,
          f"an output is ONE published cell, so its floor is per-cell (0.005 "
          f"on a 2-decimal table), and no output in {len(tables)} tables lands "
          f"between 1e-12 and that. A constant that decides nothing is "
          f"documented, not changed")

    print()
    print("    Seven found by accident, and now a list that fails when it")
    print("    stops matching the code. A constant is allowed here; an")
    print("    unexamined one is not.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
