"""
The UK analytical table, six editions, and the tolerance rule they falsify.

THE FIXTURE THIS PROJECT IS BUILT AROUND WAS ONE FILE
------------------------------------------------------
`UK_IOAT_2023_domestic_ixi.xlsx` is the project's founding table. Every
identity, every multiplier and the whole of `precision.py` were written against
it, and `load_uk_analytical_iot` navigated it by fixed row and column numbers.
The ONS publishes nine editions of these tables. The loader read one, and read
the other eight one line out of true — then reported the result as the DATA
failing:

    iot_pxp_2022.xlsx does not balance and will not be loaded.
      worst row: CPA_F41, F42 & F43 off by 406,662.169 (Construction)

That file balances exactly. Two things are not constant across editions and both
were hard-coded:

  * **The classification.** The 2023 edition merged `CPA_C254` (weapons and
    ammunition) into `CPA_C25`, so 2016-2022 are 105 x 105 and 2023 is 104 x 104.
  * **The axis.** The product-by-product workbook labels its axis `CPA` /
    `Product`; the industry-by-industry one says `SIC` / `Industry`, with no
    prefix on the codes at all.

Both axes are now found by the `_T` total the sheet prints at the end of each
block, every primary-input row by the label beside it, and the row codes are
required to equal the column codes before a number is read. The derivation is
then checked against the totals the ONS itself prints — `_T`, `TU`, `GVA` — so a
block located one line out fails as the loader's mistake and not as an
accusation against the office.

THE TOLERANCE RULE, AND THE LINE IN IT THAT WAS WRONG
------------------------------------------------------
`precision.py` records the measurement that closed `OQ-B-02`:

    ONS UK 2022   unrounded   113   1.16e-10   5.7e-06   float64

and concludes that the project's flat `ABS_TOL = 1e-6` "survived because the
founding fixture is the ONS table, which is published unrounded."

**The ONS table is not published unrounded.** In all six editions measured here
the intermediate block is full precision — under 0.6 % of its cells are whole
numbers — and **final demand, output and total use are every one of them
integers**. The interior is unrounded; the margins are rounded to whole
millions.

Pooling the blocks hides it, and hides it in the safe-looking direction: 105
unrounded cells against 10 rounded ones is 99.1 % unrounded, so
`printed_decimals` answers `None` for the pool and the identity is judged at
float64 accumulation — **5.7e-06 against a real detectability floor of 5.0**,
nine final-demand integers and one output integer at half a unit each. Six
orders of magnitude too tight, on the fixture the module was written around.

It went unnoticed because the ONS's rounded margins happen to be mutually
consistent in four editions of six. `assertable_tolerance_mixed` measures each
block on its own and adds the floors, which is what the floor of a sum is.

WHAT THAT CHANGES, AND WHAT IT DOES NOT
----------------------------------------
It admits the 2022 revised tables, where `CPA_G46` is −1 and `CPA_G47` is +1 —
one rounding unit, cancelling. It does NOT admit 2021, where 83 of 105 rows
disagree with their own printed total and `CPA_D351` (electricity transmission
and distribution) is out by **259**: 259 rounding units is not rounding, and
that edition is still refused.

WHAT A REVISION IS WORTH KNOWING
---------------------------------
The ONS published 2022 twice. Same year, same office, one year apart. Output
rises 1.36 % and the **output multipliers move by a median of 2.0 %, a mean of
2.4 %, and up to 14.8 %** — 70 of the 103 shared products move by more than 1 %.

That is the number to hold next to any disaggregation this engine produces. The
Spanish pilot's key was 9.8 points wrong and the report called that its headline
uncertainty; a table's own revision moves a multiplier by 15 %. Which of the two
dominates is not obvious, and now it does not have to be guessed.

Run:
    python3 validators/run_uk_editions.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "ons" / "iot"
FIXTURE = ROOT / "UK_IOAT_2023_domestic_ixi.xlsx"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def _leaf_fd(R, L):
    """The final-demand columns the loader keeps: `P3 S1` is a subtotal of its
    three components, and a column whose code is a strict prefix of another's is
    a subtotal of it."""
    cols = list(range(L["first_fd_col"], L["tu_col"]))
    codes = [str(R[3][j]) for j in cols]
    return [j for j, c in zip(cols, codes)
            if not any(o != c and o.startswith(c) for o in codes)]


def multipliers(t):
    A = t.Z / np.where(t.X == 0, 1.0, t.X)
    return np.linalg.inv(np.eye(t.n) - A).sum(0)


def main() -> int:
    from quadrium.io_loader import (LoaderError, _num, _open_workbook,
                                    _uk_layout, load_uk_analytical_iot)
    from quadrium.precision import (assertable_tolerance,
                                    assertable_tolerance_mixed,
                                    printed_decimals)

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    files = sorted(DATA.glob("iot_pxp_*.xlsx"))
    check("the editions are here, not one of them",
          len(files) >= 6, f"{len(files)} product-by-product workbooks, "
                           f"2019 to 2023, plus the industry fixture")

    # 1 -- what loads, at what size, on which axis.
    print()
    print(f"    {'file':<26}{'axis':>6}{'n':>6}{'year':>7}{'output':>14}")
    loaded, refused = {}, {}
    for f in files + ([FIXTURE] if FIXTURE.exists() else []):
        try:
            t = load_uk_analytical_iot(f)
            loaded[f.name] = t
            print(f"    {f.name:<26}{t.table_id.split('-')[2]:>6}{t.n:>6}"
                  f"{t.year:>7}{t.X.sum():>14,.0f}")
        except LoaderError as exc:
            refused[f.name] = str(exc)
            print(f"    {f.name:<26}{'refused':>33}")

    check("every edition but one loads, on both axes",
          len(loaded) >= 6 and any(t.table_id.startswith("UK-IOT-IXI")
                                   for t in loaded.values())
          and any(t.table_id.startswith("UK-IOT-PXP")
                  for t in loaded.values()),
          "the loader read one file of nine and blamed the other eight for "
          "not balancing")
    check("the two 2023 editions are the same economy read two ways",
          abs(loaded["iot_pxp_2023.xlsx"].X.sum()
              - loaded[FIXTURE.name].X.sum()) < 1.0,
          f"product by product {loaded['iot_pxp_2023.xlsx'].X.sum():,.0f}, "
          f"industry by industry {loaded[FIXTURE.name].X.sum():,.0f} — "
          f"different classifications, one total")

    # 2 -- the classification change, which is what broke the fixed offsets.
    a, b = loaded["iot_pxp_2022.xlsx"], loaded["iot_pxp_2023.xlsx"]
    gone = sorted(set(a.sector_codes) - set(b.sector_codes))
    came = sorted(set(b.sector_codes) - set(a.sector_codes))
    check("the classification changed between editions",
          (a.n, b.n) == (105, 104) and gone == ["CPA_C254", "CPA_C25OTHER"]
          and came == ["CPA_C25"],
          f"{a.n} products in 2022, {b.n} in 2023: "
          f"{' + '.join(gone)} merged into {came[0]}")

    # 3 -- the precision measurement, block by block, on every edition.
    print()
    print(f"    {'file':<26}{'interior':>10}{'final dem.':>12}"
          f"{'output':>9}{'pooled':>9}{'floor':>9}")
    mixed_ok = True
    for f in files:
        R = _open_workbook(f)["IOT"]
        L = _uk_layout(R, f.name)
        rows = range(L["first_row"], L["end_row"])
        cols = range(L["first_col"], L["end_col"])
        Z = np.array([[_num(R[i][j]) for j in cols] for i in rows])
        X = np.array([_num(R[L["row_output"]][j]) for j in cols])
        fd = _leaf_fd(R, L)
        Y = np.array([[_num(R[i][j]) for j in fd] for i in rows])
        d = [printed_decimals(v.ravel()) for v in (Z, Y, X)]
        pooled = printed_decimals(np.concatenate([Z.ravel(), Y.ravel(),
                                                  X.ravel()]))
        floor = assertable_tolerance_mixed((Z.ravel(), Z.shape[0]),
                                           (Y.ravel(), Y.shape[1]), (X, 1))
        mixed_ok &= (d[0] is None and d[1] == 0 and d[2] == 0
                     and pooled is None)
        print(f"    {f.name:<26}{str(d[0]):>10}{str(d[1]):>12}"
              f"{str(d[2]):>9}{str(pooled):>9}{floor:>9.2f}")

    check("every edition is unrounded inside and rounded at the margins",
          mixed_ok,
          "interior full precision, final demand and output whole numbers — "
          "in all six, which is why pooling them was never noticed")

    R = _open_workbook(files[0])["IOT"]
    L = _uk_layout(R, files[0].name)
    rows = range(L["first_row"], L["end_row"])
    cols = range(L["first_col"], L["end_col"])
    Z = np.array([[_num(R[i][j]) for j in cols] for i in rows])
    X = np.array([_num(R[L["row_output"]][j]) for j in cols])
    fd = _leaf_fd(R, L)
    Y = np.array([[_num(R[i][j]) for j in fd] for i in rows])
    pooled_tol = assertable_tolerance(
        np.concatenate([Z.ravel(), Y.ravel(), X.ravel()]),
        Z.shape[0] + Y.shape[1] + 1)
    mixed_tol = assertable_tolerance_mixed((Z.ravel(), Z.shape[0]),
                                           (Y.ravel(), Y.shape[1]), (X, 1))
    check("and pooling them understates the floor by six orders of magnitude",
          mixed_tol / pooled_tol > 1e5,
          f"pooled {pooled_tol:.2e}, block by block {mixed_tol:.2f} — a factor "
          f"of {mixed_tol / pooled_tol:,.0f}. precision.py's own table records "
          f"the ONS as 'unrounded' with a floor of 5.7e-06")

    # 4 -- what the corrected floor admits, and what it still refuses.
    print()
    rev = loaded.get("iot_pxp_2022revised.xlsx")
    check("one rounding unit, cancelling, now loads",
          rev is not None,
          "CPA_G46 at -1 and CPA_G47 at +1 in the 2022 revised tables — the "
          "pooled bound called that a table that does not balance")
    msg = refused.get("iot_pxp_2021.xlsx", "")
    check("and 259 rounding units still does not",
          "CPA_D351" in msg and "259" in msg and "5.000" in msg,
          "83 of 105 rows in the 2021 edition disagree with their own printed "
          "total; electricity transmission and distribution by 259")
    check("the refusal states the floor and where it came from",
          "OQ-B-02" in msg and "unrounded interior" in msg
          and "0 dp final demand" in msg,
          "a bound a reader cannot reconstruct is a bound they have to trust")

    # 5 -- what a revision does to the numbers this engine exists to produce.
    print()
    first, revised = loaded["iot_pxp_2022.xlsx"], rev
    shared = [c for c in first.sector_codes if c in set(revised.sector_codes)]
    ia = [first.sector_codes.index(c) for c in shared]
    ib = [revised.sector_codes.index(c) for c in shared]
    ma, mb = multipliers(first)[ia], multipliers(revised)[ib]
    rel = (mb - ma) / ma * 100.0
    k = int(np.argmax(np.abs(rel)))
    print(f"    the same year, published twice, {len(shared)} shared products:")
    print(f"      output           {first.X.sum():>12,.0f} -> "
          f"{revised.X.sum():>12,.0f}   "
          f"{(revised.X.sum() / first.X.sum() - 1) * 100:+.2f} %")
    print(f"      |Δ multiplier|   median {np.median(np.abs(rel)):.2f} %   "
          f"mean {np.abs(rel).mean():.2f} %   max {np.abs(rel).max():.2f} %")
    print(f"      worst            {shared[k]} "
          f"{first.sector_labels[ia[k]].strip()[:40]}  "
          f"{ma[k]:.4f} -> {mb[k]:.4f}")
    check("a revision moves the multipliers this engine produces",
          np.median(np.abs(rel)) > 1.0 and np.abs(rel).max() > 10.0,
          f"{(np.abs(rel) > 1).sum()} of {len(shared)} products move more than "
          f"1 %, {(np.abs(rel) > 5).sum()} more than 5 %. The Spanish pilot's "
          f"allocation key was 9.8 points wrong and that was reported as the "
          f"headline uncertainty; the table underneath it moves 14.8 % when "
          f"the office looks again")
    check("and both editions are still productive tables",
          all(max(abs(np.linalg.eigvals(
              t.Z / np.where(t.X == 0, 1.0, t.X)))) < 1.0
              for t in (first, revised)),
          "spectral radius 0.569 and 0.574 — the revision does not break the "
          "Leontief condition, it moves the answer inside it")

    print()
    print("    The loader read one file of nine and called the other eight")
    print("    unbalanced. The tolerance module was written around that one")
    print("    file and recorded it as unrounded, which it is not.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
