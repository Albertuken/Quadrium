"""
Every year of the European MRIO is the object 2018 is -- checked, not assumed.

WHY
-----
`load_eu_mrio` loads any year from 2008 to 2018. What made 2018 loadable was
established on 2018 alone: one output vector (the rows' TOTAL equals the
columns' INPUT unit by unit), a block laid out region by region, and side
files whose data follows the block's order while their own label column does
not (`run_mrio_side_join.py`). The loader checks the first two on every load.
The third it cannot: it joins by position because 2018 was shown to need it,
and a year whose files were ordered some other way would load silently wrong.
So this checks it for every year in the folder, as `run_mrio_same_year.py`
did for 2010.

WHAT IT FINDS
---------------
All eleven, 2008 to 2018: the same 2,720 units in the same order as 2018,
output by rows equal to output by columns to the last digit, intermediate
sales correlating with the side file's output at +0.86 to +0.89 by position,
NPISH identical to GGFC, and the same four empty regions every year. One year
other than 2018 is then loaded through the engine, for one region, to show
the route a workbook takes works end to end.

The block's row sums are cached per year, beside the files and gitignored,
because reading eleven 35 MB workbooks costs three minutes. The cache is an
optimisation and never a source of truth: it is keyed on the file's size and
modification time and rebuilt from the workbook whenever either moves.

Run:
    python3 validators/run_mrio_years.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MRIO = ROOT / "data" / "mrio"
S = 10
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


def files(year):
    return (MRIO / f"MRIO_{year}_272regions.xlsx",
            MRIO / f"Final_demand_{year}.xlsx",
            MRIO / f"TAXSUB_VA_{year}.xlsx")


def header(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        row = next(wb.worksheets[0].iter_rows(values_only=True, max_row=1))
    finally:
        wb.close()
    return [str(x) for x in row[1:] if x is not None]


def row_sums(path):
    """The block's row sums, from a cache keyed on the file, or from it."""
    from quadrium.io_loader import _mrio_block

    st = path.stat()
    cache = path.with_name(f"_{path.stem}_rowsums.npz")
    if cache.exists():
        d = np.load(cache, allow_pickle=False)
        if int(d["size"]) == st.st_size and int(d["mtime"]) == st.st_mtime_ns:
            return d["rowsum"]
    Z, _ = _mrio_block(path)
    rs = Z.sum(1)
    np.savez_compressed(cache, size=st.st_size, mtime=st.st_mtime_ns,
                        rowsum=rs)
    return rs


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    from quadrium.io_loader import _MRIO_YEARS, _mrio_side, load_eu_mrio

    present = [y for y in _MRIO_YEARS if all(p.exists() for p in files(y))]
    if not present:
        print("    -- no year of the archive is in data/mrio/. The deposit is "
              "Zenodo record 7875024;")
        print("       its Data/ folder holds three files for each year.")
        print("\n" + "=" * 78)
        print("Nothing was checked: the archive is not in this tree.")
        return NOTHING_CHECKED

    ref_year = 2018 if 2018 in present else present[0]
    ref = header(files(ref_year)[0])
    rows = []
    for y in present:
        blk, fdf, vaf = files(y)
        lab = header(blk)
        fh, FD = _mrio_side(fdf, "rows")
        vh, VA = _mrio_side(vaf, "columns")
        X = FD[:, fh.index("TOTAL")]
        gap = float(np.abs(X - VA[:, vh.index("INPUT")]).max())
        rs = row_sums(blk)
        good = (X > 0) & (rs > 0)
        corr = float(np.corrcoef(np.log(rs[good]), np.log(X[good]))[0, 1])
        dup = bool(np.array_equal(FD[:, fh.index("NPISH")],
                                  FD[:, fh.index("GGFC")]))
        R = len(lab) // S
        empty = tuple(lab[j * S].split("-", 1)[0] for j in range(R)
                      if X[j * S:(j + 1) * S].sum() <= 0)
        rows.append((y, lab == ref, gap, corr, dup, empty, X.sum()))

    print(f"\n    {'year':6}{'same axis':>10}{'|TOTAL-INPUT|':>15}"
          f"{'position r':>12}{'NPISH=GGFC':>12}{'empty':>7}")
    for y, same, gap, corr, dup, empty, _ in rows:
        print(f"    {y:<6}{str(same):>10}{gap:>15.3g}{corr:>+12.2f}"
              f"{str(dup):>12}{len(empty):>7}")
    print()

    check(f"every year in the folder has the same 2,720 units, in the same "
          f"order, as {ref_year}",
          all(r[1] for r in rows), f"{len(rows)} year(s): "
          f"{', '.join(str(r[0]) for r in rows)}")
    check("and one output vector: rows and columns agree unit by unit",
          all(r[2] <= 1e-6 * r[6] for r in rows),
          f"largest difference in any year {max(r[2] for r in rows):.3g}")
    check("and side files that join the block by POSITION, as in 2018",
          all(r[3] > 0.8 for r in rows),
          f"log-correlation of intermediate sales with the side file's output "
          f"{min(r[3] for r in rows):+.2f} to {max(r[3] for r in rows):+.2f}; "
          f"by label it was -0.08 in 2018")
    check("and the same empty regions every year",
          len({r[5] for r in rows}) == 1,
          f"{', '.join(rows[0][5])} in every year" if len({r[5] for r in rows})
          == 1 else "they differ between years")
    print(f"    NPISH identical to GGFC in {sum(r[4] for r in rows)} of "
          f"{len(rows)} year(s); the loader drops it only where it is")

    other = next((y for y in present if y != 2018), None)
    if other is not None:
        t = load_eu_mrio(MRIO, "ES51", other)
        row = float(np.abs(t.Z.sum(1) + t.Y.sum(1) - t.X).max())
        col = float(np.abs(t.Z.sum(0) + t.VA.sum(0) - t.X).max())
        check(f"and a year other than 2018 loads through the engine: {other}",
              t.year == other and str(other) in t.table_id
              and max(row, col) < 1e-9 * float(t.X.max()),
              f"{t.table_id}: output {t.X.sum():,.0f}, both identities closed "
              f"with the residue carried, as for 2018")

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
