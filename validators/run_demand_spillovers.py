"""
Weighted by final demand, a region's leakage is a median 10.5 % of its output
and 10.8 % of its jobs.

WHY
-----
The report's headline figure for a region of the European MRIO is the sum of
its sectors' multipliers, each for one unit of final demand: what a unit of
demand in each sector sets off, counted alike. A reader asks something else --
of everything the final demand for this region's products sets off, how much
happens elsewhere -- and that needs the demand as weights. Unweighted,
Catalonia's farm sector, 60.5 % of whose jobs multiplier runs through other
regions, counts as much as its trade and hospitality, at 3.0 %.

THE MEASUREMENT
-----------------
For each region, `x = L[:, region] y`, where `y` is the final demand for the
region's own products in the five categories the loaded table carries --
households, government, investment, inventories and exports. NPISH is left
out because the archive's column duplicates government consumption. The
share of `x` outside the region is the output figure; weighting `x` by jobs
per unit of output (Eurostat, `run_employment_spillovers.py`) gives the jobs
figure. 2018:

                         regions   p10      median    p90
    output                 259     3.4 %    10.5 %    20.6 %
    jobs                   221     5.2 %    10.4 %    20.0 %
    at the surveys' level          output 19.8 %, jobs 19.4 % (medians)

**Catalonia**: 9.6 % of the output and 9.7 % of the jobs are elsewhere (18.4 %
and 18.8 % at the surveys' level), against 16.4 % and 14.7 % unweighted.

**Exports are in, and they lower it.** Without them the output median is
12.1 % and Catalonia's 10.7 %: final demand from outside the archive is spent
more on the region's own output than domestic demand is. Both are in the
record; the engine uses the five categories because they are the loaded
table's own final demand.

**The guard that found the labels.** Employment over output, region by region,
against the median region's: on 2026-09-11 three regions stood at 25 to 40
times it while the next was at 5.1, which read as an archive that had shrunk
them. It was not: the archive's own labels name other regions, and
`run_mrio_labels.py` settled it against the archive's side files and
Eurostat's regional GDP. With the labels corrected the largest is 5.1 times
the median and the engine's guard (ten times) names nobody. It stays, and this
file checks that it stays quiet.

The figures live in `EVIDENCE['demand_spillover_pct']` and
`EVIDENCE['implausible_output']`, which the report quotes, and this file fails
if they disagree. It also requires the
engine's figures for Catalonia -- `load_eu_mrio` for output, `mrio_jobs` for
jobs -- to match its own.

Run:
    python3 validators/run_demand_spillovers.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MRIO = ROOT / "data" / "mrio"
CUBE = ROOT / "data" / "eurostat" / "nama_10r_3empers_ALL_2018.json"
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


def pct(v, q):
    return round(100 * float(np.percentile(v, q)), 1)


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if not ((MRIO / "_mrio2018_cache.npz").exists()
            or (MRIO / "MRIO_2018_272regions.xlsx").exists()) \
            or not CUBE.exists():
        print("    -- the 2018 archive or Eurostat's employment for every "
              "region is absent.")
        print("\n" + "=" * 78)
        print("Nothing was checked: the archive or the employment file is not "
              "in this tree.")
        return NOTHING_CHECKED

    from quadrium.config import MRIO_EUROSTAT_CODE, MRIO_REDRAWN
    from quadrium.eurostat import _Cube
    from quadrium.io_loader import (_MRIO_FD, _mrio_move_to_country,
                                    _mrio_relabel)
    from quadrium.regionalise import EVIDENCE

    ev = EVIDENCE.get("demand_spillover_pct")
    check("the report's reference figures are recorded", ev is not None,
          "EVIDENCE['demand_spillover_pct']")
    if ev is None:
        print(f"\n{len(FAIL)} check(s) FAILED.")
        return 1

    spec = importlib.util.spec_from_file_location(
        "axis", ROOT / "validators" / "run_mrio_axis_scale.py")
    axis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(axis)
    # `load_Z` returns the block's own labels; Greece's and Finland's do not
    # describe their rows, and employment is attached by label.
    Z, labels = axis.load_Z()
    labels = _mrio_relabel(labels)
    _, fd_head, FD = axis.load_side(axis.FD, "rows")
    X = FD[:, fd_head.index("TOTAL")]
    regions = list(dict.fromkeys(l.split("-", 1)[0] for l in labels))
    sectors = list(dict.fromkeys(l.split("-", 1)[1] for l in labels))
    R, S = len(regions), len(sectors)

    cube = _Cube(json.loads(CUBE.read_text()))

    def employment_of(r):
        if r in MRIO_REDRAWN or r.startswith("UK"):
            return None
        g = MRIO_EUROSTAT_CODE.get(r, r)
        v = [cube.at(nace_r2=s, geo=g, time="2018") for s in sectors]
        return None if any(x is None for x in v) else v

    emp = np.full(R * S, np.nan)
    for ri, r in enumerate(regions):
        v = employment_of(r)
        if v is not None:
            emp[ri * S:(ri + 1) * S] = v
    full = np.array([np.isfinite(emp[r * S:(r + 1) * S]).all()
                     for r in range(R)])
    with np.errstate(invalid="ignore", divide="ignore"):
        ck = np.where(X > 0, emp / X, np.nan)
    ck = np.where(np.isfinite(ck), ck, 0.0)
    island = np.array([
        (Z[r * S:(r + 1) * S, :].sum()
         - Z[r * S:(r + 1) * S, r * S:(r + 1) * S].sum()) < 1e-9
        and (Z[:, r * S:(r + 1) * S].sum()
             - Z[r * S:(r + 1) * S, r * S:(r + 1) * S].sum()) < 1e-9
        for r in range(R)])
    live = [r for r in range(R)
            if not island[r] and X[r * S:(r + 1) * S].sum() > 0]
    five = [code for code, _ in _MRIO_FD]
    four = [h for h in five if h != "EX"]
    cat = regions.index("ES51")

    # THE GUARD, AND WHAT IT FINDS NOW. A region's jobs per unit of output
    # over the median region's: the engine names any region above ten times it
    # (`io_loader._implausible_output`) and warns. Three regions stood at 25 to
    # 40 times on 2026-09-11; that was the archive's labels naming other
    # regions, and with them corrected (`run_mrio_labels.py`) nothing passes.
    per_region = {regions[r]: float(np.nansum(emp[r * S:(r + 1) * S])
                                    / X[r * S:(r + 1) * S].sum())
                  for r in range(R)
                  if full[r] and X[r * S:(r + 1) * S].sum() > 0}
    med_r = float(np.median(list(per_region.values())))
    times = {k: v / med_r for k, v in per_region.items()}
    flagged = sorted(k for k, v in times.items() if v > 10)
    largest = max(times, key=times.get)

    def measure(Zm, cols):
        A = Zm / np.where(X > 0, X, np.inf)
        A[~np.isfinite(A)] = 0.0
        L = np.linalg.inv(np.eye(len(A)) - A)
        idx = [fd_head.index(h) for h in cols]
        out, jobs, es, dem = [], [], None, {}
        for r in live:
            sl = slice(r * S, (r + 1) * S)
            x = L[:, sl] @ FD[sl][:, idx].sum(1)
            o = 1 - x[sl].sum() / x.sum()
            jx = ck * x
            j = 1 - jx[sl].sum() / jx.sum() if full[r] else np.nan
            out.append(o)
            jobs.append(j)
            dem[regions[r]] = (o, j)
            if r == cat:
                es = (o, j)
        out, jobs = np.array(out), np.array(jobs)
        return out, jobs[np.isfinite(jobs)], es, dem

    out, jobs, es, dem = measure(Z, five)
    ev_imp = EVIDENCE.get("implausible_output") or {}
    check("no region's jobs per unit of output is more than ten times the "
          "median region's, so the engine's guard names none",
          flagged == ev_imp.get("regions")
          and round(times[largest], 1) == ev_imp.get("largest_times_median"),
          f"the largest is {largest} at {times[largest]:.1f} times the median "
          f"region's, under the guard's ten; before the archive's labels were "
          f"corrected, three stood at 25 to 40")
    check("weighted by the final demand for its products, a region's output "
          "leaks a median 10.5 %, as EVIDENCE records",
          (len(out), pct(out, 10), pct(out, 50), pct(out, 90))
          == (ev["output_regions"], ev["output_p10"], ev["output_median"],
              ev["output_p90"]),
          f"{len(out)} regions: p10 {pct(out, 10)} %, median {pct(out, 50)} %, "
          f"p90 {pct(out, 90)} %")
    check("and its jobs a median 10.4 %",
          (len(jobs), pct(jobs, 10), pct(jobs, 50), pct(jobs, 90))
          == (ev["jobs_regions"], ev["jobs_p10"], ev["jobs_median"],
              ev["jobs_p90"]),
          f"{len(jobs)} regions: p10 {pct(jobs, 10)} %, median "
          f"{pct(jobs, 50)} %, p90 {pct(jobs, 90)} %")
    check("Catalonia: 9.6 % of the output and 9.7 % of the jobs are elsewhere",
          (round(100 * es[0], 1), round(100 * es[1], 1)) == (9.6, 9.7),
          f"output {100 * es[0]:.1f} %, jobs {100 * es[1]:.1f} %, against "
          f"16.4 % and 14.7 % unweighted")

    f = EVIDENCE["spillover_share_pct_survey"]["factor"]
    Z4 = _mrio_move_to_country(Z, regions, {r: f for r in live}, S)
    out4, jobs4, es4, dem4 = measure(Z4, five)
    check("at the surveys' level of domestic trade, 19.8 % and 19.4 %",
          (pct(out4, 50), pct(jobs4, 50))
          == (ev["output_median_if_surveyed"], ev["jobs_median_if_surveyed"])
          and (round(100 * es4[0], 1), round(100 * es4[1], 1))
          == (18.4, 18.8),
          f"factor {f:g}: medians {pct(out4, 50)} % and {pct(jobs4, 50)} %; "
          f"Catalonia {100 * es4[0]:.1f} % and {100 * es4[1]:.1f} %")

    out_nx, _, es_nx, _dem_nx = measure(Z, four)
    check("without exports the figures rise, which is why the record says "
          "which demand it weights by",
          pct(out_nx, 50) == ev["output_median_without_exports"]
          and pct(out_nx, 50) > pct(out, 50) and es_nx[0] > es[0],
          f"output median {pct(out_nx, 50)} % against {pct(out, 50)} %; "
          f"Catalonia {100 * es_nx[0]:.1f} % against {100 * es[0]:.1f} %")

    # ---- the engine gives the report the same numbers
    try:
        from quadrium.io_loader import load_eu_mrio, mrio_jobs
        ir = load_eu_mrio(MRIO, "ES51", 2018).interregional
        jb = mrio_jobs(MRIO, "ES51", 2018, employment_of)
        got = [ir["share_of_demand"], ir["share_of_demand_if_surveyed"],
               jb["share_of_demand"], jb["share_of_demand_if_surveyed"]]
        gap = float(np.max(np.abs(np.array(got)
                                  - np.array([es[0], es4[0], es[1], es4[1]]))))
        # And a region whose label the archive gets wrong: Attiki, which the
        # archive prints as EL11. Asking the engine for EL30 must give the
        # figures measured here for those rows.
        at = load_eu_mrio(MRIO, "EL30", 2018).interregional
        aj = mrio_jobs(MRIO, "EL30", 2018, employment_of)
        gap = max(gap, abs(at["share_of_demand"] - dem["EL30"][0]),
                  abs(aj["share_of_demand"] - dem["EL30"][1]),
                  abs(at["share_of_demand_if_surveyed"] - dem4["EL30"][0]))
        ok = gap < 1e-9 and not aj["implausible"]
        detail = (f"largest difference {gap:.1e}, over Catalonia and Attiki, "
                  f"whose rows the archive labels EL11")
    except Exception as exc:                              # noqa: BLE001
        ok, detail = False, f"{type(exc).__name__}: {str(exc)[:120]}"
    check("and the engine's figures for Catalonia, which the report quotes, "
          "are the same, for output and jobs, as the archive stands and at "
          "the surveys' level", ok, detail)

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED:")
        for x in FAIL:
            print(f"  - {x}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
