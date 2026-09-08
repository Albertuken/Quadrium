"""
Employment and emissions per sector, and the assumption a split makes about them.

WHAT THIS IS FOR
-----------------
The owner asked on 2026-09-08 for satellite accounts, after proposing to borrow
a fisheries employment multiplier from countries that publish one and being told
the engine had nowhere to put it. It had no employment and no environmental
extension at all.

The method needed nothing new. `UNH_20` ¶20.94 eq. (46) — `Z = B(I - A)^-1`,
with `B` the vector of coefficients — is already extracted and already
normative, with the chapter naming wages as the case in point; `M-067` carried
the general form. Employment in persons and emissions in tonnes are that
arithmetic with a different numerator, which is what makes a satellite account
an account rather than a method.

THE ASSUMPTION, WHICH IS THE REASON THIS FILE IS LONGER THAN THE FEATURE
-------------------------------------------------------------------------
A satellite total has to be divided when its sector is split, and unless the
analyst measured the quantity BY SUBSECTOR the only thing available is the key
that split the output. Using it says the subsectors have the same intensity as
each other: the same jobs per euro, the same tonnes per euro.

For hotels against restaurants that is false and known to be false. So the run
produces two subsectors with **identical** coefficients by construction, and the
one thing that must never happen is a reader taking that for a finding. Every
value produced this way is marked `estimated`, and the report says it in the
paragraph under the numbers.

TOTALS, NOT COEFFICIENTS, AND AN ABSENT SECTOR IS NOT A ZERO
--------------------------------------------------------------
Accounts are held as totals because that is what a split divides and what an
office publishes; the coefficient is one division away. And a sector the sheet
does not mention is refused rather than taken as zero: "this industry emits
nothing" and "nobody wrote down what this industry emits" are different
statements, only one is in the data, and every multiplier below would inherit
the substitution. Writing an explicit `0` is how you say you mean zero.
"""
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FAIL = []


def check(label, ok, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    if detail:
        print(f"         {detail}")
    if not ok:
        FAIL.append(label)


def main():
    from quadrium.config import ConfigError, build_satellites
    from quadrium.diagnostics import compute, satellite_effects
    from quadrium.models import IOTable, Satellite, Scenario, SplitSpec
    from quadrium.scenarios import run_scenario

    # ---- the arithmetic, on a table small enough to check by hand --------
    Z = np.array([[10.0, 5.0], [4.0, 6.0]])
    X = np.array([50.0, 50.0])
    d = compute(Z, X)
    eff = satellite_effects([500.0, 100.0], X, d["L"])
    check("the direct coefficient is the quantity over the output",
          abs(eff["direct"][0] - 10.0) < 1e-12
          and abs(eff["direct"][1] - 2.0) < 1e-12,
          f"{eff['direct'].round(4).tolist()} — 500/50 and 100/50")
    check("and the total is larger, because it counts the suppliers too",
          eff["total"][0] > eff["direct"][0]
          and eff["total"][1] > eff["direct"][1],
          f"total {eff['total'].round(4).tolist()} against direct "
          f"{eff['direct'].round(4).tolist()}")
    hand = np.array([10.0, 2.0]) @ d["L"]
    check("and it is e' L exactly — UNH_20 eq. (46), not an approximation",
          np.allclose(eff["total"], hand, rtol=0, atol=1e-12),
          f"max difference {np.abs(eff['total'] - hand).max():.2e}")

    # ---- a sector with no output has no intensity, and it is not zero ----
    eff0 = satellite_effects([500.0, 100.0], np.array([50.0, 0.0]), d["L"])
    check("a sector with zero output gets NaN, not zero",
          np.isnan(eff0["direct"][1]) and eff0["undefined"] == 1,
          "calling it zero says the sector is perfectly clean, or perfectly "
          "jobless, and the data says neither")
    check("and it contributes nothing to the totals rather than poisoning them",
          np.isfinite(eff0["total"]).all(),
          "a sector that produced nothing supplies nothing to anybody, which "
          "is the one reading that is safe")

    # ---- loading: coverage, units, duplicates ---------------------------
    table = IOTable(table_id="t", country="XX", year=2022, unit="M", 
                    classification="test", sector_codes=["A", "B"],
                    sector_labels=["a", "b"], Z=Z, Y=np.array([[35.0], [40.0]]),
                    VA=np.array([[36.0, 39.0]]), X=X, source="test",
                    Y_labels=["HH"], VA_labels=["VA"])
    rows = [{"name": "employment", "unit": "persons", "sector_code": "A",
             "value": 500, "source": "s", "source_year": 2022}]
    try:
        build_satellites(rows, table)
        check("a sheet that misses a sector is refused", False, "it loaded")
    except ConfigError as exc:
        check("a sheet that misses a sector is refused",
              "not taken as zero" in str(exc) and "B" in str(exc),
              "zero is a measurement; an absent row says only that nobody "
              "wrote it down")

    rows.append({"name": "employment", "unit": "persons", "sector_code": "B",
                 "value": 100, "source": "s", "source_year": 2022})
    got = build_satellites(rows, table)
    check("and once it covers them it loads, aligned to the table's order",
          got["employment"].values == [500.0, 100.0],
          str(got["employment"].values))

    rows.append({"name": "employment", "unit": "persons", "sector_code": "B",
                 "value": 7, "source": "s", "source_year": 2022})
    try:
        build_satellites(rows, table)
        check("two figures for one sector are refused", False, "it loaded")
    except ConfigError as exc:
        check("two figures for one sector are refused",
              "twice" in str(exc), str(exc)[:80])

    try:
        build_satellites([dict(r, unit="") for r in rows[:2]], table)
        check("an account with no unit is refused", False, "it loaded")
    except ConfigError as exc:
        check("an account with no unit is refused",
              "unit" in str(exc),
              "a multiplier of 1.4 means nothing without one")

    try:
        Satellite(name="co2", unit="t", values=[1.0, -3.0], source="s",
                  source_year=2022)
        check("a negative quantity is refused", False, "it was accepted")
    except ValueError as exc:
        check("a negative quantity is refused",
              "sign error upstream" in str(exc), str(exc)[:80])

    # ---- the split: sums preserved, intensity assumed, both said --------
    ine = ROOT / "data" / "ine" / "cne_tio_22.xlsx"
    if not ine.exists():
        print("  the Spanish table is absent; the split half needs it.")
        print("\n" + "=" * 78)
        print(f"{len(FAIL)} check(s) FAILED" if FAIL else "All checks passed.")
        return 1 if FAIL else 0

    sys.path.insert(0, str(ROOT / "examples"))
    import es_hosteleria as ex
    from quadrium.io_loader import load_ine_tio

    tab = load_ine_tio(ine, "interior", "residual_column")
    tab.satellites = {"employment": Satellite(
        name="employment", unit="persons",
        values=[float(x) * 12.0 for x in tab.X],
        source="synthetic, to exercise the mechanics", source_year=2022)}
    before = sum(tab.satellites["employment"].values)
    res = run_scenario(
        tab, [SplitSpec("36", ex.NEW, ex.LBL,
                        keys_by_block={"output": "k_tod_produccion"})],
        Scenario(scenario_id="S1", label="size only", description="base"),
        ex.build_keys())
    after = res.table.satellites["employment"]

    check("the parts add to the parent exactly",
          abs(sum(after.values) - before) < 1e-6,
          f"{before:,.1f} before, {sum(after.values):,.1f} after")
    idx = [res.table.index_of(c) for c in ("36A", "36B")]
    check("and every value the split produced is marked estimated",
          all(after.origin[i] == "estimated" for i in idx)
          and after.origin[0] == "observed",
          "an estimate presented as an observation is the failure this whole "
          "engine is built against")

    s = res.diagnostics["satellites"]["employment"]
    check("the subsectors come out with IDENTICAL intensity",
          abs(s["direct"][idx[0]] - s["direct"][idx[1]]) < 1e-12,
          f"{s['direct'][idx[0]]:.4f} both — that is what dividing by the "
          f"output key means, and it is an assumption and not a finding")
    check("and the run records that assumption by name",
          any(a["satellite"] == "employment" and a["sector_code"] == "36"
              for a in res.diagnostics["equal_intensity_assumed"]),
          str(res.diagnostics["equal_intensity_assumed"]))

    from quadrium.reporting import scenario_section
    md = scenario_section(res)
    check("and the report says it where the numbers are",
          "SAME intensity as each other" in md
          and "assumption rather than" in md,
          "identical columns with no sentence under them read as a finding")
    check("and names the case where it is known to be false",
          "restaurant employs far more people per euro" in md)

    print()
    print("    The account divides in proportion to money, so it reports two")
    print("    subsectors as equally labour-intensive by construction. The")
    print("    arithmetic is exact; the economics is an assumption, and the")
    print("    report is where the difference has to be visible.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
