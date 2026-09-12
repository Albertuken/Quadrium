"""
The Austrian comparison at the surveys' own year: 2010 against 2010.

WHY THIS EXISTS
-----------------
`run_mrio_against_surveys.py` found that the European MRIO keeps a region's
trade at home -- 0.25 times the purchases from the rest of the country that
surveys record, lower in ten regions of ten -- and every statement built on it
carried one caveat: **the years differ**. The Austrian surveys of Rokicki et
al. describe 2010; the archive file this project had extracted is 2018. A
region's trade can change in eight years, and "a factor of four in one
direction is hard to put down to that" is an argument, not a measurement.

The deposit holds the same three files for every year from 2008 to 2018
(its zip directory, read on 2026-09-11). So the comparison can be made at
2010, and the caveat either survives or goes.

WHAT IS CHECKED FIRST
-----------------------
That 2010 is the same object as 2018, because nothing about another year may
be assumed from the one that was studied: the same 2,720 units in the same
order, output by rows equal to output by columns unit by unit, and the side
files joined to the block by POSITION -- the correspondence
`run_mrio_side_join.py` established for 2018 -- rather than by their label
column. Only then the nine regions, each at 2010 against its own 2010 survey.

WHAT IT FINDS
---------------
2010 is the same object: the identical axis, one output vector (largest
difference 0), and side files that join the block by position (log-correlation
+0.87, against +0.88 for 2018).

                            MRIO / survey 2010, median over nine regions
    rest of Austria         MRIO 2010: 0.23       MRIO 2018: 0.24
    the region itself       MRIO 2010: 2.10

**The years were not the cause.** At the surveys' own year the archive records
the same quarter of the trade with the rest of the country, lower in nine of
nine, and the same doubling at home. The bias is how the archive was built, not
eight years of change. Catalonia's comparison, IDESCAT 2021 against the
archive's 2018, keeps the caveat; Austria's no longer has one.

Run:
    python3 validators/run_mrio_same_year.py
"""
from __future__ import annotations

import importlib.util
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MRIO = ROOT / "data" / "mrio"
AUSTRIA = MRIO / "truth" / "Austria"
FILES_2010 = ("MRIO_2010_272regions.xlsx", "Final_demand_2010.xlsx",
              "TAXSUB_VA_2010.xlsx")
S = 10
SURVEYED = ("AT11", "AT12", "AT13", "AT21", "AT22",
            "AT31", "AT32", "AT33", "AT34")
FAIL: list[str] = []

# Exit code 3, not 0. `check.sh` counts it as SKIPPED rather than as a pass:
# this validator opened no file and measured nothing, and a run that says
# "All checks passed" on evidence it never saw is the fault the suite exists
# to catch. It is not a failure -- a tree without the workbook still exits 0.
NOTHING_CHECKED = 3


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def shares(Z, X, VA, vh, regions, region):
    """own, rest of country, abroad -- as shares of the region's output."""
    k = regions.index(region)
    s = slice(k * S, (k + 1) * S)
    out = X[s].sum()
    home = [j for j, r in enumerate(regions) if r[:2] == region[:2] and j != k]
    away = [j for j, r in enumerate(regions) if r[:2] != region[:2]]
    own = Z[s, s].sum()
    roc = sum(Z[j * S:(j + 1) * S, s].sum() for j in home)
    abroad = sum(Z[j * S:(j + 1) * S, s].sum() for j in away) \
        + VA[s, vh.index("IM")].sum()
    return own / out, roc / out, abroad / out


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    missing = [f for f in FILES_2010 if not (MRIO / f).exists()]
    if missing or not AUSTRIA.is_dir() or not (
            (MRIO / "_mrio2018_cache.npz").exists()
            or (MRIO / "MRIO_2018_272regions.xlsx").exists()):
        what = ", ".join(missing) or "the 2018 block or the Austrian surveys"
        print(f"    -- absent: {what}. The deposit is Zenodo record 7875024;")
        print("       the 2010 files are in its Data/ folder.")
        print("\n" + "=" * 78)
        print("Nothing was checked: the 2010 archive files are not in this "
              "tree.")
        return NOTHING_CHECKED

    from quadrium.io_loader import (_mrio_block, _mrio_side,
                                    read_rokicki_components)

    spec = importlib.util.spec_from_file_location(
        "axis", ROOT / "validators" / "run_mrio_axis_scale.py")
    axis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(axis)
    from quadrium.io_loader import _mrio_relabel

    # `load_Z` reads the block's own labels and `_mrio_block` below returns
    # them corrected, so both sides are read the same way before comparing
    # (`run_mrio_labels.py`).
    Z18, lab18 = axis.load_Z()
    lab18 = _mrio_relabel(lab18)
    _, fh18, FD18 = axis.load_side(axis.FD, "rows")
    _, vh18, VA18 = axis.load_side(axis.VA, "columns")
    X18 = FD18[:, fh18.index("TOTAL")]

    Z10, lab10 = _mrio_block(MRIO / FILES_2010[0])
    fh10, FD10 = _mrio_side(MRIO / FILES_2010[1], "rows")
    vh10, VA10 = _mrio_side(MRIO / FILES_2010[2], "columns")
    X10 = FD10[:, fh10.index("TOTAL")]
    regions = list(dict.fromkeys(l.split("-", 1)[0] for l in lab10))

    check("2010 has the same 2,720 units, in the same order, as 2018",
          lab10 == lab18 and Z10.shape == Z18.shape,
          f"{len(lab10):,} labels, identical to 2018's")
    gap = float(np.abs(X10 - VA10[:, vh10.index("INPUT")]).max())
    check("output by rows equals output by columns, unit by unit, as in 2018",
          gap <= 1e-6 * float(np.abs(X10).max()),
          f"largest difference {gap:.3g}; one output vector, the condition "
          f"that made 2018 loadable")
    good = (X10 > 0) & (Z10.sum(1) > 0)
    corr = float(np.corrcoef(np.log(Z10.sum(1)[good]),
                             np.log(X10[good]))[0, 1])
    check("and the side files join the block by position, as in 2018",
          corr > 0.8,
          f"log-correlation of intermediate sales with the side file's "
          f"output {corr:+.2f}; run_mrio_side_join.py found +0.88 for 2018 by "
          f"position and -0.08 by label")

    rows = []
    for r in SURVEYED:
        c = read_rokicki_components(AUSTRIA, r)
        x = c["X_col"].sum()
        survey = (c["Z"].sum() / x,
                  c["imports"]["rest of country"].sum() / x,
                  c["imports"]["rest of world"].sum() / x)
        rows.append((r, survey,
                     shares(Z10, X10, VA10, vh10, regions, r),
                     shares(Z18, X18, VA18, vh18, regions, r)))

    print(f"\n    {'region':8}{'rest of country':>20}{'':>16}"
          f"{'own region':>14}")
    print(f"    {'':8}{'survey 2010':>13}{'MRIO 2010':>11}{'MRIO 2018':>11}"
          f"{'survey':>9}{'MRIO 2010':>11}")
    for r, sv, a10, a18 in rows:
        print(f"    {r:8}{sv[1]:>12.1%}{a10[1]:>11.1%}{a18[1]:>11.1%}"
              f"{sv[0]:>9.1%}{a10[0]:>11.1%}")
    print()

    sv = np.array([r[1] for r in rows])
    a10 = np.array([r[2] for r in rows])
    a18 = np.array([r[3] for r in rows])
    r10 = np.median(a10[:, 1] / sv[:, 1])
    r18 = np.median(a18[:, 1] / sv[:, 1])
    own10 = np.median(a10[:, 0] / sv[:, 0])
    lower = int((a10[:, 1] < sv[:, 1]).sum())

    check("at the surveys' own year the archive still gives every region less "
          "trade with the rest of Austria",
          lower == len(rows),
          f"lower in {lower} of {len(rows)}; median ratio {r10:.2f} in 2010 "
          f"against {r18:.2f} in 2018")
    check("and still keeps the difference at home",
          own10 > 1.5,
          f"purchases from the region itself, MRIO 2010 / survey 2010, median "
          f"{own10:.2f}")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED:")
        for f in FAIL:
            print(f"  - {f}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
