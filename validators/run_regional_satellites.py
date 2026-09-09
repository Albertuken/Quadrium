"""
What a satellite account does when the table is regionalised, and what cannot come.

THE CHAIN NOBODY HAD WALKED
-----------------------------
Satellite accounts shipped on 2026-09-08 and were made to survive a split and a
file on 2026-09-09. The third thing the engine does to a table is regionalise
it, and `Regionalisation.to_table()` built a fresh `IOTable` from the
coefficients and the output vector -- so a national employment account went in
and **nothing came out**, silently, for the same reason the export did.

Three features in three days and the failure was the same one each time: the
new thing does not compose with the old thing, and nothing says so.

WHY THIS ONE SCALES RATHER THAN DROPS
---------------------------------------
Dropping is safe and silent, and silence is the failure. Carrying the account
unchanged is worse -- it hands the region the whole country's employment. So it
is scaled by the region's share of national output, which is the same bargain a
split makes one level down: **the region is assumed to have the country's
intensity.**

Every value comes out `estimated` and the caveat travels in the lineage, where
`--regionalise` already prints what the method is known to get wrong.

AND THE ASSUMPTION HAS A TRACK RECORD
---------------------------------------
Not for employment; nothing here measured that, and this file does not pretend
otherwise. But `run_charm_heterogeneity.py` measured one intensity transported
from a nation to one of its regions and it went the wrong way: Spain against
Catalonia, rank correlation **0.886** -- the ordering carries -- while
Catalonia's mean is **1.40x** Spain's and the national value under-predicts in
**47 of 63** products.

WHAT CANNOT COME, AND IS SAID RATHER THAN DROPPED
---------------------------------------------------
The type II closure. Its two settings name a value-added ROW and a final-demand
COLUMN of the national table; a regionalised table has one of each and both are
residuals, because the quotient says nothing about how a region's value added
splits between labour and capital. There is no wages row to close on. A table
that arrives type I where the user configured type II shows multipliers a third
smaller with nothing explaining why, so the run says it.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "examples"))

FAIL = []
NOTHING_CHECKED = 3


def check(label, ok, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    if detail:
        print(f"         {detail}")
    if not ok:
        FAIL.append(label)


def main():
    ine = ROOT / "data" / "ine" / "cne_tio_22.xlsx"
    if not ine.exists():
        print(f"    -- {ine.name} is absent.")
        print("\n" + "=" * 78)
        print("Nothing checked here.")
        return NOTHING_CHECKED

    import es_hosteleria as ex
    from quadrium.io_loader import load_ine_tio
    from quadrium.models import Satellite
    from quadrium.regionalise import regionalise

    nat = load_ine_tio(ine, "interior", "residual_column")
    nat.satellites = {"employment": Satellite(
        name="employment", unit="persons",
        values=[float(x) * 12.0 for x in nat.X],
        source="synthetic, to exercise the chain", source_year=2022)}
    nat.type_ii = {"income_rows": ["Remuneración de los asalariados"],
                   "household": "Gasto en consumo final de los hogares"}

    A = nat.Z / np.where(nat.X == 0, 1.0, nat.X)
    SHARE = 0.20
    reg_X = nat.X * SHARE
    res = regionalise(A, reg_X, nat.X, method="SLQ", X_region=reg_X)
    t = res.to_table(sector_codes=nat.sector_codes, country="ES — region",
                     year=2022, unit=nat.unit,
                     classification=nat.classification, national=nat)

    # 1 -- it arrives at all, which is what failed.
    check("the account survives the regionalisation",
          "employment" in t.satellites,
          "before 2026-09-09 the regional table was built from scratch and "
          "the account went in and did not come out")

    # 2 -- scaled, and to the share the region actually is.
    a = np.array(nat.satellites["employment"].values)
    b = np.array(t.satellites["employment"].values)
    ratio = b.sum() / a.sum()
    check("and it is SCALED, not carried whole",
          abs(ratio - SHARE) < 1e-9,
          f"{ratio:.4f} of the national total for a region that is "
          f"{SHARE:.0%} of national output — carrying it unchanged would hand "
          f"the region the whole country's employment")
    worst = np.abs(np.where(a > 0, b / np.where(a == 0, 1, a), SHARE)
                   - SHARE).max()
    check("sector by sector, not only in total",
          worst < 1e-9,
          f"worst deviation {worst:.2e} — a total that matches while the "
          f"sectors do not would be a different account with the right sum")

    # 3 -- and every value says it is an estimate.
    check("every regional value is marked estimated",
          set(t.satellites["employment"].origin) == {"estimated"},
          "none of it was measured for this region; it is the national "
          "account divided by a share")
    check("and the account carries why, on itself",
          "country's intensity" in (t.satellites["employment"].notes or ""),
          "a reader who opens the file without the report still meets the "
          "assumption")

    # 4 -- the caveat reaches the run's own record.
    lineage = " ".join(t.lineage)
    check("the assumption is in the lineage, beside what the method gets wrong",
          "assumes the region has the country's intensity" in lineage
          and "if you hold the quantity FOR THIS REGION" in lineage,
          "--regionalise already prints its costs unasked; this joins them")

    # 5 -- what cannot come is SAID.
    check("the type II closure is refused with its reason, not dropped",
          "type II closure did NOT come" in lineage
          and "no" not in t.type_ii,
          "there is no wages row in a regionalised table to close on, and a "
          "silent downgrade to type I looks like smaller multipliers with no "
          "explanation")
    check("and the regional table really is type I",
          not t.type_ii,
          "saying it and then carrying it would be worse than either")

    # 6 -- a national table with no accounts produces a region with none.
    plain = load_ine_tio(ine, "interior", "residual_column")
    t2 = res.to_table(sector_codes=plain.sector_codes, country="x", year=2022,
                      unit=plain.unit, classification=plain.classification,
                      national=plain)
    check("a table with no accounts gives a region with none, and no caveat",
          t2.satellites == {}
          and not any("satellite account(s)" in c for c in t2.lineage),
          "a warning about accounts nobody registered is noise")

    print()
    print("    Three features in three days, and the failure was the same one")
    print("    each time: the new thing does not compose with the old thing,")
    print("    and nothing says so.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
