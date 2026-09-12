"""
What a one-region table leaves out, in jobs: a median 12.1 % of them.

WHY
-----
`run_mrio_spillovers.py` measures what a single-region table omits of the
OUTPUT multiplier: the part of an impulse that travels to other regions and
comes back. `mrio_employment` attaches Eurostat's employment to a region of
the European MRIO, and the question a reader of an employment multiplier asks
is the same one in jobs. Eurostat publishes employment for 230 of the archive's
268 regions with data (`run_mrio_eurostat_codes.py`, and `run_mrio_labels.py`
for the nineteen labels the archive gets wrong), so the whole system can be
weighted by jobs.

THE MEASUREMENT
-----------------
For each unit j, the jobs its final demand creates are `c L[:, j]`, where `c`
is employment over output for every unit that has both. Split into the rows of
j's own region and the rest, exactly as the output version splits the column
sum. On the 2,210 units of the 221 regions that have employment and trade with
anyone (2018):

    jobs that land in other regions    p10  3.0 %   median 11.4 %   p90 45.0 %
    output, on the same units          p10  4.7 %   median 13.6 %   p90 42.8 %

**The count is nearly complete.** The regions without employment -- the United
Kingdom's, and five that were redrawn -- hold a median 0.2 % of a unit's output
multiplier, 1.5 % at the ninetieth percentile. What is missing from the job
count is small, and it is measured rather than assumed.

**Jobs leak a little less than output at the median, and the sectors differ
more than the medians do.** Real estate's jobs leak twice as far as its output
(27.5 % against 14.4 %); public services and leisure half as far (5.1 against
9.6 %; 5.7 against 11.9 %). An employment multiplier from a one-region table
is short by a different amount in each sector, and not by the output figure.

**At the surveys' level of domestic trade** (`run_spillover_sensitivity.py`,
the same factor, from `EVIDENCE`) the median is 20.7 %, against 24.6 % for
output on the same units. The archive's own figure is a floor here for the
reason it is one for output.

These are per unit of final demand in each sector. Weighted by the final
demand a region actually has, region by region: `run_demand_spillovers.py`.

The figures live in `EVIDENCE['employment_spillover_pct']`, which the report
quotes; this file fails if the two disagree. It also computes Catalonia's
share by sector on its own and requires the engine's `io_loader.mrio_jobs`,
which the report uses, to give the same numbers.

Run:
    python3 validators/run_employment_spillovers.py
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
    from quadrium.io_loader import _mrio_move_to_country, _mrio_relabel
    from quadrium.regionalise import EVIDENCE

    ev = EVIDENCE.get("employment_spillover_pct")
    check("the report's reference figures are recorded", ev is not None,
          "EVIDENCE['employment_spillover_pct']")
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
    check("230 regions carry employment for all ten sectors",
          int(full.sum()) == 230, f"{int(full.sum())} of {R}")

    island = np.array([
        (Z[r * S:(r + 1) * S, :].sum()
         - Z[r * S:(r + 1) * S, r * S:(r + 1) * S].sum()) < 1e-9
        and (Z[:, r * S:(r + 1) * S].sum()
             - Z[r * S:(r + 1) * S, r * S:(r + 1) * S].sum()) < 1e-9
        for r in range(R)])
    with np.errstate(invalid="ignore", divide="ignore"):
        c = np.where(X > 0, emp / X, np.nan)
    known = np.isfinite(c)
    ck = np.where(known, c, 0.0)
    cat = regions.index("ES51")
    cs = slice(cat * S, (cat + 1) * S)

    def measure(Zm):
        A = Zm / np.where(X > 0, X, np.inf)
        A[~np.isfinite(A)] = 0.0
        L = np.linalg.inv(np.eye(len(A)) - A)
        jobs = ck @ L
        m = L.sum(0)
        own_jobs, own_out = np.empty(R * S), np.empty(R * S)
        for r in range(R):
            sl = slice(r * S, (r + 1) * S)
            own_jobs[sl] = ck[sl] @ L[sl, sl]
            own_out[sl] = L[sl, sl].sum(0)
        keep = np.repeat(~island & full, S) & (X > 0) & (jobs > 0)
        js = (jobs - own_jobs)[keep] / jobs[keep]
        os_ = (m - own_out)[keep] / m[keep]
        unmeasured = L[~known, :].sum(0)[keep] / m[keep]
        per_cat = (jobs[cs] - own_jobs[cs]) / jobs[cs]
        sec = np.array([l.split("-", 1)[1] for l in labels])[keep]
        return js, os_, unmeasured, sec, int(keep.sum()), per_cat

    js, os_, unmeasured, sec, n, per_cat = measure(Z)
    p10, p50, p90 = (100 * np.percentile(js, [10, 50, 90])).round(1)
    o50 = round(100 * float(np.median(os_)), 1)
    u50, u90 = (100 * np.percentile(unmeasured, [50, 90])).round(1)
    check("the regions without employment hold little of any multiplier, so "
          "the job count is nearly complete",
          (u50, u90) == (ev["unmeasured_median_pct"], ev["unmeasured_p90_pct"])
          and u90 < 5,
          f"median {u50} %, p90 {u90} % of a unit's output multiplier falls "
          f"in them")
    check("a one-region table omits a median 11.4 % of the jobs, as EVIDENCE "
          "records", (n, p10, p50, p90) == (ev["units"], ev["p10"],
                                             ev["median"], ev["p90"]),
          f"{n} units: p10 {p10} %, median {p50} %, p90 {p90} %")
    check("against 13.6 % of the output on the same units: jobs leak a little "
          "less at the median",
          o50 == ev["output_median_same_units"] and p50 < o50,
          f"output median {o50} %; jobs higher in "
          f"{int((js > os_).sum())} of {n}")

    def med(k, v):
        return round(100 * float(np.median(v[sec == k])), 1)
    check("and the sectors differ more than the medians: real estate's jobs "
          "leak twice as far as its output, public services' half as far",
          med("L", js) > 1.5 * med("L", os_)
          and med("O-Q", js) < 0.7 * med("O-Q", os_)
          and med("R-U", js) < 0.7 * med("R-U", os_),
          f"L {med('L', js)} against {med('L', os_)}; O-Q {med('O-Q', js)} "
          f"against {med('O-Q', os_)}; R-U {med('R-U', js)} against "
          f"{med('R-U', os_)}")
    f = EVIDENCE["spillover_share_pct_survey"]["factor"]
    live = [r for r in range(R)
            if not island[r] and X[r * S:(r + 1) * S].sum() > 0]
    js4, os4, _, _, _, per_cat4 = measure(
        _mrio_move_to_country(Z, regions, {r: f for r in live}, S))
    q50 = round(100 * float(np.median(js4)), 1)
    check("at the surveys' level of domestic trade, 20.7 % of the jobs",
          q50 == ev["median_if_surveyed"],
          f"factor {f:g}: jobs {q50} %, output "
          f"{round(100 * float(np.median(os4)), 1)} %")

    # ---- the engine gives the report the same numbers
    try:
        from quadrium.io_loader import mrio_jobs
        eng = mrio_jobs(MRIO, "ES51", 2018, employment_of)
        a = np.array(eng["share_by_sector"])
        b = np.array(eng["share_by_sector_if_surveyed"])
        gap = max(float(np.abs(a - per_cat).max()),
                  float(np.abs(b - per_cat4).max()))
        ok, detail = gap < 1e-9, (
            f"largest difference {gap:.1e} over Catalonia's ten sectors, both "
            f"as the archive stands and at the surveys' level; "
            f"{eng['regions_counted']} of {eng['regions']} regions counted")
    except Exception as exc:                              # noqa: BLE001
        ok, detail = False, f"{type(exc).__name__}: {str(exc)[:120]}"
    check("and the engine's `mrio_jobs`, which the report quotes, gives the "
          "same shares for Catalonia, sector by sector", ok, detail)

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
