"""
The identities the project could not exercise, run on the UK — for 27 years.

WHAT WAS BLOCKED, AND FOR HOW LONG
------------------------------------
`run_uk_iot.py` reports **5 of 14** identities and says the rest "cannot be
exercised until the project has a real supply-use pair as a second test
fixture". `OQ-D-03` has said the same since v1.1: an analytical IOT at basic
prices has had its margins reallocated and its valuation columns absorbed, so
the identities that are *about* those columns have nothing to run on.

`NSO_UK_04` — the ONS's own supply and use tables, Blue Book 2025 — arrived on
2026-08-13 while closing `OQ-D-02`. It carries **1997 to 2023**, so the second
fixture came with twenty-six second years.

WHAT RUNS NOW, AND WHAT STILL DOES NOT
----------------------------------------
Six identities run here that could not run on the analytical table, every one of
them for every published year:

    ID-01  product balance: output + imports + margins + taxes = intermediate
           + final demand, per product, on the source's own valuation columns
    ID-02  industry identity: intermediate consumption + GVA = output
    ID-03  value added decomposes into taxes, compensation and surplus
    ID-06  GDP from production and from expenditure agree
    ID-08  the margin column sums to zero across the economy
    ID-14  the use matrix sums to the published intermediate consumption

And `ID-13` becomes testable for the first time in the way it is meant to be —
**across two tables rather than inside one**: value added in the supply-use
table against value added in the analytical IOT built from it, same office,
same year.

**Three of the six `OQ-D-03` named are still NOT APPLICABLE, and the reason is
the source rather than the project.** `ID-07` needs the supply matrix `V`;
`ID-09` needs margins by industry; `ID-10` needs the CIF/FOB adjustment rows.
**The ONS publishes none of the three.** Its supply table gives each product's
total domestic output beside its imports, margins and taxes — who made what is
not published, and neither is the margin matrix. That is a fact about the UK's
publication, not a gap in this validator, and it is why `load_ons_sut` returns
its own object rather than a `SupplyUseTables`: that class promises a `V`, and
inventing one is the failure this project exists to prevent.

THE TOLERANCE IS THE DERIVED FLOOR, NOT A CONSTANT
----------------------------------------------------
The ONS publishes whole £ million, so an `n`-term identity cannot be checked
more tightly than `0.5·n` (`precision.assertable_tolerance`, `OQ-B-02`). Every
comparison below uses it. It turns out not to matter: **every identity holds
exactly, at 0.00, in every year** — the office balances its rounded figures, as
Spain does and Italy does not (`OQ-B-02` v1.10).

Run:
    python3 validators/run_uk_sut_identities.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

from quadrium.io_loader import load_ons_sut  # noqa: E402
from quadrium.precision import assertable_tolerance  # noqa: E402

BOOK = ROOT / "data" / "ons" / "NSO_UK_04_ONS_supply_use_tables_BB25.xlsx"
IOAT = ROOT / "UK_IOAT_2023_domestic_ixi.xlsx"

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def years_in(path: Path) -> list[int]:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    return sorted({int(s.rsplit(" ", 1)[1]) for s in wb.sheetnames
                   if s.startswith("Table 2 - Int Con ")})


def identities(s) -> dict[str, tuple[float, float]]:
    """{identity: (worst deviation, the floor it is allowed)} for one year."""
    scale = np.concatenate([s.U.ravel(), s.Y.ravel(), s.output_basic,
                            s.imports, s.margins, s.taxes_on_products,
                            s.gva, s.output_by_industry])
    n_p, n_i = len(s.product_codes), len(s.industry_codes)
    floor = lambda n: assertable_tolerance(scale, n)   # noqa: E731

    intermediate, final = s.U.sum(1), s.Y.sum(1)
    out = {}
    out["ID-01 product balance"] = (
        float(np.abs((s.output_basic + s.imports + s.margins
                      + s.taxes_on_products) - (intermediate + final)).max()),
        floor(4 + n_i + s.Y.shape[1]))
    out["ID-01 vs published total supply"] = (
        float(np.abs(s.output_basic + s.imports + s.margins
                     + s.taxes_on_products - s.total_supply).max()), floor(4))
    out["ID-02 industry identity"] = (
        float(np.abs(s.ic_by_industry + s.gva - s.output_by_industry).max()),
        floor(n_p + 4))
    out["ID-03 value-added decomposition"] = (
        float(np.abs(s.taxes_on_production + s.compensation + s.gos_mixed
                     - s.gva).max()), floor(3))
    gdp_p = float(s.gva.sum() + s.taxes_on_products.sum())
    gdp_e = float(final.sum() - s.imports.sum())
    out["ID-06 GDP two ways"] = (abs(gdp_p - gdp_e), floor(n_p + n_i))
    out["ID-08 margins sum to zero"] = (abs(float(s.margins.sum())), floor(n_p))
    out["ID-14 intermediate totals"] = (
        abs(float(s.U.sum() - s.ic_by_industry.sum())), floor(n_p * n_i))
    return out


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if not BOOK.exists():
        print(f"\n    {BOOK.name} is not in data/ons — nothing to do.")
        return 0

    years = years_in(BOOK)
    print(f"\n    ONS supply and use tables, {min(years)}–{max(years)} "
          f"({len(years)} years), £ million, whole numbers\n")

    worst: dict[str, tuple[float, float, int]] = {}
    for year in years:
        s = load_ons_sut(BOOK, year)
        for name, (dev, floor) in identities(s).items():
            if name not in worst or dev > worst[name][0]:
                worst[name] = (dev, floor, year)

    print(f"    {'identity':<34}{'worst dev':>12}{'floor':>10}{'year':>7}")
    for name, (dev, floor, year) in worst.items():
        print(f"    {name:<34}{dev:>12,.2f}{floor:>10,.1f}{year:>7}")

    for name, (dev, floor, year) in worst.items():
        check(f"{name}, all {len(years)} years", dev <= floor,
              f"worst {dev:,.2f} against a floor of {floor:,.1f} "
              f"({'exact' if dev == 0 else f'in {year}'})")

    # ---- ID-13 across two tables, which is what it is actually for --------
    if IOAT.exists():
        import run_uk_iot as uk
        t = uk.load_iot(IOAT)
        s = load_ons_sut(BOOK, 2023)
        iot_codes = [str(c).strip() for c in t["codes"]]
        gva_iot = (np.asarray(t["compensation"], float)
                   + np.asarray(t["gos_mi"], float)
                   + np.asarray(t["other_taxes"], float))
        by_code = dict(zip(iot_codes, gva_iot))
        aligned = np.array([by_code[c] for c in s.industry_codes], float)

        check("ID-13 value added is preserved from the SUT into the "
              "analytical IOT",
              float(np.abs(aligned - s.gva).max()) <= 0.5 and
              abs(float(aligned.sum() - s.gva.sum())) <= 0.5,
              f"104 industries, worst {np.abs(aligned - s.gva).max():,.2f}, "
              f"totals {s.gva.sum():,.0f} both — the transformation moves "
              f"value added nowhere, which is what ID-13 asserts and what no "
              f"single table could show")

        # The trap, kept because it is the kind that produces a finding.
        positional = float(np.abs(gva_iot - s.gva).max())
        i = int(np.argmax(np.abs(gva_iot - s.gva)))
        check("and matching by POSITION instead of by code invents a "
              "discrepancy",
              positional > 1000 and s.industry_codes[i] != iot_codes[i],
              f"{positional:,.0f} at position {i} — `{s.industry_codes[i]}` in "
              f"the SUT against `{iot_codes[i]}` in the IOAT. The two tables "
              f"order the real-estate industries differently, and the "
              f"spurious gap lands next door to the cell OQ-D-02 was about")

    print()
    print("    Still NOT APPLICABLE, and the source is why:")
    print("      ID-07  needs the supply matrix V — the ONS publishes each")
    print("             product's total domestic output, not who made it")
    print("      ID-09  needs margins by industry — one combined margin")
    print("             column is published, by product only")
    print("      ID-10  needs the CIF/FOB adjustment rows — not published")
    print("    That is a fact about the UK's publication, not a gap here, and")
    print("    it is why `load_ons_sut` refuses to return a SupplyUseTables.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
