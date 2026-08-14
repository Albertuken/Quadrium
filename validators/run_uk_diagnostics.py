"""
Run the CORE_012 balancing diagnostics against the project's real table:
    <project root>/UK_IOAT_2023_domestic_ixi.xlsx

WHAT THIS FIXTURE CAN AND CANNOT EXERCISE.

The file is an XLSX workbook (despite the extension) for reference year 2023,
Blue Book 2025 vintage: an Input-Output ANALYTICAL table, domestic use, basic
prices, industry by industry, GBP million, 104 x 104. See D_open_questions.md
OQ-D-01.

Consequences for CORE_012's diagnostic battery:

  runnable     D2a  GVA / output by industry
               D2b  taxes less subsidies on products / output by industry
               T1   handover triage on the ID-11 residuals
               NEG  negative triage
               ID-17 income-approach GVA, minimum form -- but see the note the
                     check itself prints: on this file the components are the
                     table's own rows, so the test is CIRCULAR and proves nothing
                     (CORE_006 par. 9.17, p. 279; CORE_012 A11.5, p. 351)

  NOT APPLICABLE
               ID-15 needs a supply table and its valuation matrices
               ID-16 needs the six-pack: three price-period values per cell
               D2c  needs a margin column
               D2d  needs t-1
               D3   needs volume indices
               D4   needs labour input
               D5   needs price indices by user
               S4   needs a separated VAT row and a legal-rate table

Every NOT APPLICABLE is reported, never silently skipped.

Usage:
    python3 run_uk_diagnostics.py [path-to-workbook]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import diagnostics as DG        # noqa: E402
import quadrium.identities as ID         # noqa: E402
from run_uk_iot import DEFAULT, load_iot  # noqa: E402


def main(path: Path) -> int:
    d = load_iot(path)
    Z, x = d["Z"], d["x"]
    F = d["FD"]
    fd_used = ["P3 S1", "P51G", "P52", "P53", "P61EU", "P61RW", "P62"]
    y = sum(F[k] for k in fd_used)

    print("=" * 78)
    print("CORE_012 balancing diagnostics -- UN Handbook 2018 ch. 11, pp. 319-368")
    print("=" * 78)
    print(f"file      : {path.name}")
    for m in d["menu"]:
        print(f"menu      : {m}")
    print(f"sheet     : {d['title']}")
    print(f"dimensions: Z is {Z.shape[0]} x {Z.shape[1]} industries")
    print()

    checks: list[DG.Check] = []

    # ---- identities added to A.6 from CORE_012 ---------------------------
    checks.append(DG.not_applicable(
        "ID-15", "margin supply column = valuation-matrix totals",
        "CORE_012 par. 11.16, p. 323",
        "this is an analytical IOT at basic prices: margins are already "
        "reallocated, there is no supply table and no valuation matrix"))

    checks.append(DG.not_applicable(
        "ID-16", "value index = price index x volume index / 100",
        "CORE_012 par. 11.17, p. 323",
        "single reference year, current prices only -- the six-pack needs "
        "v[t,p_t], v[t,p_t-1] and v[t-1,p_t-1] per cell (par. 11.29, p. 325)"))

    checks.append(DG.id17_income_approach_gva(
        gva_production=d["gva"],
        gross_operating_surplus=d["gos_mi"],
        compensation_of_employees=d["compensation"],
        other_taxes_on_production=d["other_taxes"],
        components_independently_sourced=False))

    # ---- M-030 battery ---------------------------------------------------
    # Column-side "supply" of an industry in this table = total output at basic
    # prices. Taxes less subsidies on products sit in the column, outside Z.
    checks.extend(DG.d2_credibility_ratios(
        gva=d["gva"], output=x,
        taxes_on_products=d["taxes_products"], supply=x,
        margins=None, prior=None))

    checks.append(DG.d3_volume_change_coherence([], []))
    checks.append(DG.d4_labour_productivity(None, None))
    checks.append(DG.d5_price_dispersion([]))

    # ---- M-038 -----------------------------------------------------------
    checks.append(DG.s4_implied_tax_rate(None, None, None))

    # ---- M-039 handover triage on the ID-11 residuals --------------------
    row = Z.sum(1) + y
    col = Z.sum(0) + d["imports"] + d["taxes_products"] + d["gva"]
    resid = row - col
    scale = np.abs(Z).sum(1) + np.abs(y)

    # Diagnostic profile: an industry is "firing" if D2a flagged its GVA/output
    # ratio. This is the par. 11.105 clause that size alone is not sufficient.
    d2a = next(c for c in checks if c.check_id == "D2a")
    firing = d2a.info.get("flagged")
    checks.append(DG.discrepancy_triage(resid, scale, firing))

    # ---- M-037 negative triage ------------------------------------------
    blocks = {
        "Z_domestic_intermediate": Z,
        "taxes_less_subsidies_on_products": d["taxes_products"],
        "other_taxes_less_subsidies_on_production": d["other_taxes"],
        "gross_operating_surplus_and_mixed_income": d["gos_mi"],
        "imports_of_intermediate_products": d["imports"],
    }
    block_map = {}
    for code, arr in F.items():
        if code == "P3 S1":
            continue                      # would double count S13+S14+S15
        name = f"FD_{code}"
        blocks[name] = arr
        if code == "P52":
            block_map[name] = "changes_in_inventories"
        elif code == "P53":
            block_map[name] = "acquisitions_less_disposals_of_valuables"
        elif code == "P51G":
            block_map[name] = "gross_capital_formation"
    checks.append(DG.negative_triage(blocks, block_map))

    for c in checks:
        print(c)
        print()

    # ---- the negative triage table, in full ------------------------------
    neg = checks[-1]
    print("-" * 78)
    print("NEGATIVE TRIAGE  (M-037 / A_core_accounting_spec.md A.8.1)")
    print("-" * 78)
    print(f"{'block':<44}{'class':<19}{'n':>4} {'min':>15}")
    for r in neg.info["rows"]:
        print(f"{r['block']:<44}{r['classification']:<19}{r['n_negative']:>4} "
              f"{r['min']:>15,.2f}")
        print(f"{'':<44}{r['citation']}")
    print()

    i, j = np.unravel_index(np.argmin(Z), Z.shape)
    print(f"  The one UNCLASSIFIED cell in Z: {Z[i, j]:,.2f}")
    print(f"     row {d['codes'][i]}  {str(d['names'][i]).strip()}")
    print(f"     col {d['codes'][j]}  {str(d['names'][j]).strip()}")
    print("     -> escalate per M-031; tracked as D_open_questions.md OQ-D-02.")
    print("     -> NOT zeroed. No loaded source authorises that.")
    print()

    # ---- summary ---------------------------------------------------------
    print("-" * 78)
    n = {s: sum(1 for c in checks if c.status == s)
         for s in (DG.PASS, DG.FLAG, DG.FAIL, DG.NA)}
    print(f"PASS {n[DG.PASS]}   FLAG {n[DG.FLAG]}   FAIL {n[DG.FAIL]}   "
          f"NOT APPLICABLE {n[DG.NA]}   of {len(checks)} checks")
    print()
    print("Every threshold used above is a PROJECT CHOICE. CORE_012 states no")
    print("numerical tolerance, no convergence criterion and no definition of")
    print("'small' or 'large' (D_open_questions.md OQ-B-02).")
    print("A FLAG is advisory: 'further investigation is advisable'")
    print("(CORE_012 par. 11.19, p. 323). It never authorises a correction.")
    print("Solver convergence is NECESSARY BUT NOT SUFFICIENT for statistical")
    print("validity (CORE_006 par. 9.51, p. 288; CORE_012 par. 11.111, p. 344).")
    return 1 if n[DG.FAIL] else 0


if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    if not p.exists():
        sys.exit(f"not found: {p}")
    sys.exit(main(p))
