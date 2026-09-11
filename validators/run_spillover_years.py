"""
The archive's spillover by year: its median barely moves, a region's does.

WHY
-----
`load_eu_mrio` loads any year from 2008 to 2018. The report prints a region's
spillover for the year loaded, and every archive-wide figure the engine quotes
was measured on 2018. That raises two questions, and they have different
answers:

    does the 11.7 % median depend on 2018?        no -- 10.8 % to 12.3 %
                                                  over eleven years
    does a region's own figure depend on the year? yes -- a median 5.1 points
                                                  between its highest and
                                                  lowest year, 9.8 at the
                                                  90th percentile, 28.2 at
                                                  most

And regions keep their order: rank correlation +0.86 between 2008 and 2018.
So the report now says that a region's figure is that year's, and how far it
has moved across the deposit, rather than letting it read as a constant.

WHAT IS MEASURED
------------------
For every year in data/mrio/, the full inverse, split per unit into its own
region's rows and everyone else's, exactly as `run_mrio_spillovers.py` does,
with the regions that trade with no other region excluded. A region's figure
is its summed leakage over its summed multiplier, as the loader computes it.

Each year's results are cached beside its files and gitignored, keyed on the
three files' sizes and modification times, because eleven inverses of a
2,720-square system cost four minutes. The cache is an optimisation and never a
source of truth: it is rebuilt whenever a file moves.

Run:
    python3 validators/run_spillover_years.py
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


def measure(year):
    """Per-unit spillover shares, the island mask, and each region's figure."""
    from quadrium.io_loader import _mrio_block, _mrio_side

    fs = files(year)
    key = np.array([[f.stat().st_size, f.stat().st_mtime_ns] for f in fs])
    cache = fs[0].with_name(f"_{fs[0].stem}_spill.npz")
    if cache.exists():
        d = np.load(cache, allow_pickle=False)
        if np.array_equal(d["key"], key):
            return d["share"], d["island"], d["region"], [str(r) for r in
                                                           d["regions"]]
    Z, lab = _mrio_block(fs[0])
    fh, FD = _mrio_side(fs[1], "rows")
    X = FD[:, fh.index("TOTAL")]
    regions = list(dict.fromkeys(l.split("-", 1)[0] for l in lab))
    R = len(regions)
    A = Z / np.where(X > 0, X, np.inf)
    L = np.linalg.inv(np.eye(len(A)) - A)
    m = L.sum(0)
    intra = np.empty_like(m)
    for r in range(R):
        sl = slice(r * S, (r + 1) * S)
        intra[sl] = L[sl, sl].sum(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(m > 0, (m - intra) / m, np.nan)
    island = np.array([
        (Z[r * S:(r + 1) * S].sum()
         - Z[r * S:(r + 1) * S, r * S:(r + 1) * S].sum()) < 1e-9
        and (Z[:, r * S:(r + 1) * S].sum()
             - Z[r * S:(r + 1) * S, r * S:(r + 1) * S].sum()) < 1e-9
        for r in range(R)])
    region = np.array([
        float((m[r * S:(r + 1) * S] - intra[r * S:(r + 1) * S]).sum()
              / m[r * S:(r + 1) * S].sum())
        if not island[r] and m[r * S:(r + 1) * S].sum() > 0 else np.nan
        for r in range(R)])
    np.savez_compressed(cache, key=key, share=share, island=island,
                        region=region, regions=np.array(regions))
    return share, island, region, regions


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    from quadrium.io_loader import _MRIO_YEARS
    from quadrium.regionalise import EVIDENCE

    present = [y for y in _MRIO_YEARS if all(f.exists() for f in files(y))]
    if len(present) < 2:
        print(f"    -- {len(present)} year(s) of the archive in data/mrio/; "
              f"a change across years needs at least two.")
        print("\n" + "=" * 78)
        print("Nothing was checked: fewer than two years of the archive are "
              "in this tree.")
        return NOTHING_CHECKED

    per_year, names = {}, None
    print(f"\n    {'year':6}{'p10':>7}{'median':>8}{'p90':>7}{'regions':>9}")
    for y in present:
        share, island, region, regions = measure(y)
        names = names or regions
        keep = np.repeat(~island, S) & np.isfinite(share)
        p10, p50, p90 = np.percentile(share[keep], [10, 50, 90]) * 100
        per_year[y] = (p50, dict(zip(regions, region)))
        print(f"    {y:<6}{p10:>6.1f}%{p50:>7.1f}%{p90:>6.1f}%"
              f"{int((~island).sum()):>9}")
    print()

    medians = [per_year[y][0] for y in present]
    check("the archive's median spillover does not depend on the year",
          all(10.5 <= v <= 12.5 for v in medians),
          f"{min(medians):.1f} % to {max(medians):.1f} % across "
          f"{len(present)} years; 2018's is "
          f"{per_year[2018][0]:.1f} %" if 2018 in per_year else "")

    full = [r for r in names
            if all(np.isfinite(per_year[y][1].get(r, np.nan)) for y in present)]
    spans = np.array([100 * (max(per_year[y][1][r] for y in present)
                             - min(per_year[y][1][r] for y in present))
                      for r in full])
    check("while a region's own figure does, by several points",
          float(np.median(spans)) > 3.0,
          f"{len(full)} regions in every year; the distance between a "
          f"region's highest and lowest year is {np.median(spans):.1f} points "
          f"at the median, {np.percentile(spans, 90):.1f} at the 90th "
          f"percentile, {spans.max():.1f} at most")

    first, last = present[0], present[-1]
    a = np.array([per_year[first][1][r] for r in full])
    b = np.array([per_year[last][1][r] for r in full])
    rank = float(np.corrcoef(np.argsort(np.argsort(a)),
                             np.argsort(np.argsort(b)))[0, 1])
    check(f"and regions keep their order from {first} to {last}",
          rank > 0.8, f"rank correlation {rank:+.2f}")

    ev = EVIDENCE.get("spillover_by_year") or {}
    if len(present) == len(_MRIO_YEARS) or not ev:
        want = {"median_min": round(min(medians), 1),
                "median_max": round(max(medians), 1),
                "region_range_median_pts": round(float(np.median(spans)), 1),
                "region_range_p90_pts": round(float(np.percentile(spans, 90)),
                                              1),
                "rank_2008_2018": round(rank, 2)}
        check("and the engine quotes these figures, not a rounded memory of "
              "them",
              all(abs(ev.get(k, -1) - v) < 1e-9 for k, v in want.items()),
              f"regionalise.EVIDENCE['spillover_by_year'] is "
              f"{ev or 'absent'}; measured {want}")
    else:
        print(f"    -- {len(present)} of {len(_MRIO_YEARS)} years are here; "
              f"the engine's figures are not re-derived from fewer")

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
