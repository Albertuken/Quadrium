"""
The employment leakage by year, 2008 to 2018.

WHY
-----
The report gives, for a region of the European MRIO with `mrio_employment`,
how much of its employment multipliers runs through other regions, and
compares it with the archive's median. Those medians were measured on 2018
(`run_employment_spillovers.py`, `run_demand_spillovers.py`), and the engine
loads any year from 2008 to 2018. For output, `run_spillover_years.py` showed
that the archive's median barely moves while a region's own figure does. This
asks the same of jobs, with Eurostat's regional employment for each year
(one file per year in `data/eurostat/`, fetched through `eurostat.fetch`).

WHAT IS MEASURED
------------------
For every year, the archive's full inverse weighted by jobs per unit of
output, exactly as `io_loader.mrio_jobs` does for one region:

- per unit, the share of the jobs a unit of its final demand creates that
  lands in other regions (the 12.1 % of 2018);
- per region, the same weighted by the final demand for its products, the
  five categories the loaded table carries (the 10.8 % of 2018);
- how far a region's weighted figure moves between its highest and lowest
  year, and whether regions keep their order from 2008 to 2018.

WHAT IT FOUND
---------------
Eurostat carries the same 230 regions in every year, and 2018 reproduces the
figures the other two validators record. The archive's medians barely move:
10.4 % to 11.5 % per unit, 9.7 % to 11.0 % weighted by demand. A region's
weighted figure moves as much as its output figure does -- a median 5.1 points
between its highest and lowest year, 12.1 at the 90th percentile -- and
regions keep their order less well than in output: +0.72 from 2008 to 2018
against +0.86.

**This is what the measurement looked like before the archive's labels were
corrected**: seven regions jumped by more than 20 points from one year to the
next, all Finnish or Greek, because Eurostat's employment was being attached
to the wrong region (`run_mrio_labels.py`). With the labels corrected one
region does.

**That one is a single cell of the archive.** EL61 (Thessalia) moves 36 points
between 2012 and 2013. Eurostat's employment for it is smooth -- 279 to 317
thousand across the deposit -- and what jumps is the archive's construction:
output 1,063 in 2012, 8,820 in 2013, 3,225 in 2014 and 710 in 2015, while its
construction value added stays between 411 and 454. Greek construction as a
whole rises 16 % in 2013, so the archive is not adding output to the country,
it is putting it in Thessalia. `run_mrio_scale.py` lists that unit among the
handful whose output exceeds ten times their own value added. A region's job
figure is the loaded year's, and the report says so.

Regions that trade with no other region, and units without employment, are
excluded as in the 2018 validators. Each year's results are cached beside its
files, keyed on the three files' and the employment file's sizes and times; the
cache is an optimisation and never a source of truth.

Run:
    python3 validators/run_employment_years.py
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
EMP = ROOT / "data" / "eurostat"
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
            MRIO / f"TAXSUB_VA_{year}.xlsx",
            EMP / f"nama_10r_3empers_ALL_{year}.json")


def measure(year):
    """Per-unit job shares, each region's demand-weighted job share, the
    region codes, and how many regions carry employment."""
    from quadrium.config import MRIO_EUROSTAT_CODE, MRIO_REDRAWN
    from quadrium.eurostat import _Cube
    from quadrium.io_loader import _MRIO_FD, _mrio_block, _mrio_side

    fs = files(year)
    key = np.array([[f.stat().st_size, f.stat().st_mtime_ns] for f in fs])
    # `_v2`: the labels changed when the archive's Greek and Finnish ones were
    # corrected, and employment is attached by label, so earlier caches are
    # not this measurement.
    cache = fs[0].with_name(f"_{fs[0].stem}_jobs_v2.npz")
    if cache.exists():
        d = np.load(cache, allow_pickle=False)
        if np.array_equal(d["key"], key):
            return (d["unit"], d["region"], [str(r) for r in d["regions"]],
                    int(d["counted"]))
    Z, lab = _mrio_block(fs[0])
    fh, FD = _mrio_side(fs[1], "rows")
    X = FD[:, fh.index("TOTAL")]
    regions = list(dict.fromkeys(l.split("-", 1)[0] for l in lab))
    sectors = list(dict.fromkeys(l.split("-", 1)[1] for l in lab))
    R = len(regions)

    cube = _Cube(json.loads(fs[3].read_text()))
    emp = np.full(R * S, np.nan)
    for ri, r in enumerate(regions):
        if r in MRIO_REDRAWN or r.startswith("UK"):
            continue
        g = MRIO_EUROSTAT_CODE.get(r, r)
        v = [cube.at(nace_r2=s, geo=g, time=str(year)) for s in sectors]
        if all(x is not None for x in v):
            emp[ri * S:(ri + 1) * S] = v
    full = np.array([np.isfinite(emp[r * S:(r + 1) * S]).all()
                     for r in range(R)])
    ck = np.where(np.isfinite(emp) & (X > 0),
                  emp / np.where(X > 0, X, 1.0), 0.0)

    A = Z / np.where(X > 0, X, np.inf)
    A[~np.isfinite(A)] = 0.0
    L = np.linalg.inv(np.eye(len(A)) - A)
    jobs = ck @ L
    island = np.array([
        (Z[r * S:(r + 1) * S].sum()
         - Z[r * S:(r + 1) * S, r * S:(r + 1) * S].sum()) < 1e-9
        and (Z[:, r * S:(r + 1) * S].sum()
             - Z[r * S:(r + 1) * S, r * S:(r + 1) * S].sum()) < 1e-9
        for r in range(R)])
    idx = [fh.index(c) for c, _ in _MRIO_FD]
    unit = np.full(R * S, np.nan)
    region = np.full(R, np.nan)
    for r in range(R):
        sl = slice(r * S, (r + 1) * S)
        if island[r] or not full[r] or X[sl].sum() <= 0:
            continue
        own = ck[sl] @ L[sl, sl]
        with np.errstate(invalid="ignore", divide="ignore"):
            unit[sl] = np.where((jobs[sl] > 0) & (X[sl] > 0),
                                (jobs[sl] - own) / jobs[sl], np.nan)
        jx = ck * (L[:, sl] @ FD[sl][:, idx].sum(1))
        if jx.sum() > 0:
            region[r] = 1 - jx[sl].sum() / jx.sum()
    np.savez_compressed(cache, key=key, unit=unit, region=region,
                        regions=np.array(regions), counted=int(full.sum()))
    return unit, region, regions, int(full.sum())


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    from quadrium.io_loader import _MRIO_YEARS
    from quadrium.regionalise import EVIDENCE

    present = [y for y in _MRIO_YEARS if all(f.exists() for f in files(y))]
    if len(present) < 2:
        print(f"    -- {len(present)} year(s) with both the archive and "
              f"Eurostat's employment; a change across years needs two.")
        print("\n" + "=" * 78)
        print("Nothing was checked: fewer than two years of the archive and "
              "its employment are in this tree.")
        return NOTHING_CHECKED

    per_year, names, counted = {}, None, {}
    print(f"\n    {'year':6}{'regions':>8}{'unit p10':>10}{'median':>8}"
          f"{'p90':>7}{'by demand':>11}")
    for y in present:
        unit, region, regions, n = measure(y)
        names = names or regions
        u = unit[np.isfinite(unit)]
        d = region[np.isfinite(region)]
        p10, p50, p90 = np.percentile(u, [10, 50, 90]) * 100
        per_year[y] = (round(float(p50), 1),
                       round(100 * float(np.median(d)), 1),
                       dict(zip(regions, region)))
        counted[y] = n
        print(f"    {y:<6}{n:>8}{p10:>9.1f}%{p50:>7.1f}%{p90:>6.1f}%"
              f"{100 * float(np.median(d)):>10.1f}%")
    print()

    check("Eurostat carries employment for the same 230 regions in every year",
          all(n == 230 for n in counted.values()),
          ", ".join(f"{y} {n}" for y, n in counted.items() if n != 230)
          or f"{len(present)} years, 230 each")
    if 2018 in per_year:
        e1 = EVIDENCE["employment_spillover_pct"]["median"]
        e2 = EVIDENCE["demand_spillover_pct"]["jobs_median"]
        check("and 2018 reproduces the figures the other two validators "
              "record", per_year[2018][:2] == (e1, e2),
              f"{per_year[2018][:2]} against {e1} and {e2}")

    units = [per_year[y][0] for y in present]
    demand = [per_year[y][1] for y in present]
    full = [r for r in names
            if all(np.isfinite(per_year[y][2].get(r, np.nan))
                   for y in present)]
    spans = np.array([100 * (max(per_year[y][2][r] for y in present)
                             - min(per_year[y][2][r] for y in present))
                      for r in full])
    first, last = present[0], present[-1]
    a = np.array([per_year[first][2][r] for r in full])
    b = np.array([per_year[last][2][r] for r in full])
    rank = float(np.corrcoef(np.argsort(np.argsort(a)),
                             np.argsort(np.argsort(b)))[0, 1])
    print(f"    medians per unit {min(units)} % to {max(units)} %; by demand "
          f"{min(demand)} % to {max(demand)} %")
    print(f"    {len(full)} regions in every year: a region's figure moves "
          f"{np.median(spans):.1f} points at the median, "
          f"{np.percentile(spans, 90):.1f} at the 90th percentile, "
          f"{spans.max():.1f} at most; rank {first}-{last} {rank:+.2f}\n")

    check("the archive's medians do not depend on the year",
          max(units) - min(units) < 3 and max(demand) - min(demand) < 3,
          f"per unit {min(units)} % to {max(units)} %, by demand "
          f"{min(demand)} % to {max(demand)} %")
    so = EVIDENCE["spillover_by_year"]
    check("while a region's own figure moves as much as its output figure "
          "does, and regions keep their order less well",
          abs(float(np.median(spans)) - so["region_range_median_pts"]) < 1.0
          and rank < so["rank_2008_2018"],
          f"{np.median(spans):.1f} points at the median against "
          f"{so['region_range_median_pts']} for output; rank {rank:+.2f} "
          f"against {so['rank_2008_2018']:+.2f}")
    jumps = {r: 100 * max(abs(per_year[b][2][r] - per_year[a][2][r])
                          for a, b in zip(present, present[1:]))
             for r in full}
    big = sorted(r for r, v in jumps.items() if v > 20)
    check("and one region alone jumps more than 20 points from one year to "
          "the next, where seven did before the archive's labels were "
          "corrected", len(big) == 1,
          f"{len(big)}: " + ", ".join(f"{r} {jumps[r]:.1f}" for r in big))

    ev = EVIDENCE.get("employment_by_year") or {}
    if len(present) == len(_MRIO_YEARS) or not ev:
        want = {"unit_median_min": min(units), "unit_median_max": max(units),
                "demand_median_min": min(demand),
                "demand_median_max": max(demand),
                "region_range_median_pts": round(float(np.median(spans)), 1),
                "region_range_p90_pts": round(float(np.percentile(spans, 90)),
                                              1),
                "rank_2008_2018": round(rank, 2)}
        check("and the engine quotes these figures, not a rounded memory of "
              "them",
              all(abs(ev.get(k, -1) - v) < 1e-9 for k, v in want.items()),
              f"regionalise.EVIDENCE['employment_by_year'] is "
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
