"""
The archive's branches within a region agree with Eurostat: no second fault.

WHY
-----
`run_mrio_labels.py` found that nineteen of the archive's region labels name
another region, and found it by comparing a region's SIZE with something
outside the archive. The same question has a smaller twin: within a region,
does each of the ten branches carry the branch it says? A sector order that
had been printed in the wrong order would be invisible to every check the
project had, exactly as the region labels were.

Eurostat publishes regional value added by branch on the archive's own A10
grouping (`nama_10r_3gva`, current prices, million euro, kept in
`data/eurostat/` with its provenance). Comparing SHARES within a region needs
no exchange rate and no scale.

WHAT IT FOUND, ON 2018
------------------------
Nothing wrong, and that is the result:

    largest branch difference in a region   median 1.2 pts, p90 2.5, max 8.7
    sum over the ten branches               median 4.0 pts, p90 7.1, max 33.1
    reordering the branches would gain      median 0.0 pts, p90 1.3
    regions where reordering would gain more than 5 points: 1

Every branch's median difference is within 0.3 points, so no branch is
systematically over- or under-weighted either. The worst region is IE04
(Northern and Western Ireland), where the archive puts more industry and less
professional services than Eurostat does -- the part of Ireland's accounts
that multinational activity moves around, not a labelling fault.

WHAT IT WOULD CATCH
---------------------
If a region's branches were printed in another order, the reordering test
would gain the difference between the true composition and the printed one --
tens of points for any region whose branches differ in size, which is every
region. It gains nothing.

Run:
    python3 validators/run_mrio_sectors.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MRIO = ROOT / "data" / "mrio"
GVA = ROOT / "data" / "eurostat" / "nama_10r_3gva_ALL_2018.json"
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


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    import openpyxl

    from quadrium.config import MRIO_EUROSTAT_CODE, MRIO_REDRAWN
    from quadrium.eurostat import _Cube
    from quadrium.io_loader import (_MRIO_SECTORS, _mrio_files, _mrio_relabel,
                                    _mrio_side)

    try:
        blk, _, vaf = _mrio_files(MRIO, 2018)
    except Exception:                                     # noqa: BLE001
        blk = None
    if blk is None or not GVA.exists():
        print("    -- the 2018 archive or Eurostat's regional value added by "
              "branch is absent.")
        print("\n" + "=" * 78)
        print("Nothing was checked: the archive or the value-added file is "
              "not in this tree.")
        return NOTHING_CHECKED

    sectors = list(_MRIO_SECTORS)
    wb = openpyxl.load_workbook(blk, read_only=True, data_only=True)
    try:
        head = next(wb.worksheets[0].iter_rows(values_only=True, max_row=1))
    finally:
        wb.close()
    regions = list(dict.fromkeys(
        l.split("-", 1)[0]
        for l in _mrio_relabel([str(x) for x in head[1:] if x is not None])))
    vh, VA = _mrio_side(vaf, "columns")
    va = VA[:, vh.index("VA")]
    cube = _Cube(json.loads(GVA.read_text()))

    try:
        from scipy.optimize import linear_sum_assignment
    except ImportError:                                   # pragma: no cover
        linear_sum_assignment = None

    worst, total, gain, diffs, names = [], [], [], [], []
    for k, r in enumerate(regions):
        if r in MRIO_REDRAWN or r.startswith("UK"):
            continue
        g = MRIO_EUROSTAT_CODE.get(r, r)
        e = [cube.at(nace_r2=s, geo=g, time="2018") for s in sectors]
        a = va[k * S:(k + 1) * S]
        if any(x is None for x in e) or a.sum() <= 0 or sum(e) <= 0:
            continue
        sa = np.asarray(a, float) / float(np.sum(a))
        se = np.asarray(e, float) / float(np.sum(e))
        worst.append(100 * float(np.abs(sa - se).max()))
        total.append(100 * float(np.abs(sa - se).sum()))
        diffs.append(sa - se)
        names.append(r)
        if linear_sum_assignment is not None:
            cost = np.abs(sa[:, None] - se[None, :])
            _, ci = linear_sum_assignment(cost)
            gain.append(100 * (float(np.abs(sa - se).sum())
                               - float(cost[np.arange(S), ci].sum())))

    w, t, D = np.array(worst), np.array(total), np.array(diffs)
    check("every region of the archive with employment has Eurostat's ten "
          "branches too", len(names) == 230, f"{len(names)} regions compared")
    check("a region's branches carry the shares Eurostat gives them, within a "
          "point or two",
          round(float(np.median(w)), 1) == 1.2
          and round(float(np.percentile(w, 90)), 1) == 2.5,
          f"largest branch in a region: median {np.median(w):.1f} points, p90 "
          f"{np.percentile(w, 90):.1f}, max {w.max():.1f} "
          f"({names[int(np.argmax(w))]}); summed over the ten: median "
          f"{np.median(t):.1f}, p90 {np.percentile(t, 90):.1f}, max "
          f"{t.max():.1f} ({names[int(np.argmax(t))]})")
    if gain:
        g = np.array(gain)
        check("and no region's branches would fit Eurostat better in another "
              "order, which is what a printed-in-the-wrong-order archive "
              "would look like",
              float(np.median(g)) < 0.05 and int((g > 5).sum()) <= 1,
              f"reordering gains a median {np.median(g):.1f} points, p90 "
              f"{np.percentile(g, 90):.1f}, and more than 5 points in "
              f"{int((g > 5).sum())} of {len(g)} regions")
    else:
        print("    -- scipy is absent from this interpreter, so the "
              "reordering test was not run")
    bias = {s: 100 * float(np.median(D[:, i])) for i, s in enumerate(sectors)}
    check("and no branch is over- or under-weighted across the archive",
          max(abs(v) for v in bias.values()) < 0.5,
          ", ".join(f"{s} {v:+.2f}" for s, v in bias.items()))

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
