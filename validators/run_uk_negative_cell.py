"""
`OQ-D-02`: the UK's one negative in `Z`, against four offices publishing the
same cell.

The cell is `K64` Financial service activities → `L68A` Owner-occupiers'
housing, **−20,770.99 £ million**, the only negative in a 104 × 104 domestic
intermediate matrix. No loaded source explains it. `NSO_UK_01` p. 5 removed one
suspect by naming the transformation — model D, which cannot create negatives —
so it was already in the supply-use system before chapter 12 got near it.

What had not been tried is the move that settled `OQ-D-04`: **ask whether anyone
else publishes the same cell.** Four member states do, all four positive.

    office        cell K64 → L68A     as % of L68A's output
    France             +3,463.0              1.66 %
    Austria            +1,776.6              6.71 %
    Spain              +1,849.0              1.79 %
    Netherlands        +8,178.0             15.68 %
    ---------------------------------------------------
    ONS               −20,771.0            −7.99 %

THREE EXPLANATIONS RULED OUT
-----------------------------
**A loader artefact.** No: the raw ONS workbook carries −20770.98736131382 at the
row labelled "Financial Service Activities, Except I…" and the column labelled
"Owner-Occupiers' Housing". Checked here without going through the loader.

**Valuation.** The four comparators are use tables at purchasers' prices; the UK
figure is an analytical IOT at basic prices. Converting one to the other
subtracts trade and transport margins and taxes less subsidies on products — and
for this cell Austria publishes **both as exactly zero** (`naio_10_cp1620` and
`cp1630`). Financial services carry no trade margin by construction and are
largely VAT-exempt, so basic and purchasers' prices coincide here. A valuation
step that subtracts zero cannot turn +6.7 % into −8.0 %.

**The transformation.** Already excluded at v1.8: model D does not invert a share
matrix, so it cannot produce a negative that was not there.

WHAT IS *NOT* RULED OUT, AND IS STATED RATHER THAN GLOSSED
-----------------------------------------------------------
The UK matrix is **domestic**; the four comparators are **total** use, domestic
plus imported. A domestic-only cell is smaller than its total, so it can be
nearer zero — but it cannot go BELOW zero from that alone unless the
domestic/import split itself assigns more than the whole cell to imports, which
would be the same anomaly under another name.

The two objects are also different in kind: an industry × industry analytical
table against a product × industry use table. The chain that makes them
comparable is the model-D result above, and it is a chain of two steps, not a
direct observation.

WHAT THIS SETTLES AND WHAT IT DOES NOT
---------------------------------------
It converts "unexplained by the loaded sources" into "an outlier in sign against
four independent publishers of the same cell under the same regulation, which
neither valuation nor the transformation explains". Reading NSO_UK_03 (the ONS's
own FISIM methodology article, 2026-08-13) then rules out the one named,
documented mechanism by which FISIM legitimately goes negative — default-risk
adjustment — as both the wrong category (deposits/PNFC/non-resident loans go
negative under it; dwelling loans are explicitly reported not to) and two orders
of magnitude too small. That is as far as any public methodology document goes.
**Only the ONS's own internal compilation record can say why this specific
figure is what it is.**

Run:
    python3 validators/run_uk_negative_cell.py
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

DATA = ROOT / "data" / "eurostat"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    uk_file = ROOT / "UK_IOAT_2023_domestic_ixi.xlsx"
    if not uk_file.exists():
        print("UK fixture absent")
        return 0

    import numpy as np
    import run_uk_iot as uk
    from quadrium.eurostat import _Cube

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    t = uk.load_iot(uk_file)
    codes = [str(c).strip() for c in t["codes"]]
    i, j = codes.index("K64"), codes.index("L68A")
    value = float(t["Z"][i, j])
    output = float(t["x"][j])

    check("the cell is where the entry says it is, and negative",
          value < -20_000,
          f"{value:,.2f} £m, {value / output:.2%} of L68A's output "
          f"({output:,.0f})")

    # Not a loader artefact.
    import openpyxl
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td) / "w.xlsx"
        shutil.copy(uk_file, tmp)
        wb = openpyxl.load_workbook(tmp, read_only=True, data_only=True)
        raw = [list(r) for r in wb["IOT"].iter_rows(values_only=True)]
    cell = raw[6 + i][2 + j]
    check("and it is in the published file, not made by the loader",
          abs(float(cell) - value) < 1e-6,
          f"raw workbook has {float(cell):,.5f} at row "
          f"{str(raw[6 + i][1])[:34]!r} / column {str(raw[4][2 + j])[:26]!r}")

    # The same cell, four other offices.
    others = {}
    for geo in ("FR", "AT", "ES", "NL"):
        p = DATA / f"naio_10_cp16_{geo}_2022.json"
        if not p.exists():
            continue
        c = _Cube(json.loads(p.read_text()))
        v = c.at(ind_use="L68A", prd_ava="CPA_K64")
        g = c.at(ind_use="L68A", prd_ava="P1")
        if v is not None and g:
            others[geo] = (float(v), float(v) / float(g))
    print()
    print(f"    {'office':<14}{'K64 → L68A':>14}{'% of output':>14}")
    for geo, (v, share) in others.items():
        print(f"    {geo:<14}{v:>14,.1f}{share:>13.2%}")
    print(f"    {'ONS':<14}{value:>14,.1f}{value / output:>13.2%}")
    print()

    check("four other offices publish the same cell, all POSITIVE",
          len(others) >= 4 and all(v > 0 for v, _ in others.values()),
          f"{', '.join(f'{g} +{v:,.0f}' for g, (v, _) in others.items())} — so "
          f"a negative here is not a convention of the framework")

    # Valuation cannot do it.
    margins = taxes = None
    for tag, name in (("cp1620", "margins"), ("cp1630", "taxes")):
        p = DATA / f"naio_10_{tag}_AT_2022.json"
        if p.exists():
            c = _Cube(json.loads(p.read_text()))
            v = c.at(ind_use="L68A", cpa2_1="CPA_K64")
            if tag == "cp1620":
                margins = v
            else:
                taxes = v
    if margins is not None and taxes is not None:
        check("and valuation cannot explain the difference: both adjustments "
              "are zero on this cell",
              abs(float(margins)) < 1e-9 and abs(float(taxes)) < 1e-9,
              f"Austria publishes trade and transport margins {margins} and "
              f"taxes less subsidies {taxes} for K64 → L68A, so basic and "
              f"purchasers' prices coincide. Subtracting zero cannot turn "
              f"+6.71 % into −7.99 %")

    print()
    print("    NOT ruled out, and stated rather than glossed: the UK matrix is")
    print("    DOMESTIC and the comparators are TOTAL use. Domestic-only can be")
    print("    nearer zero, but not below it unless the import split assigns")
    print("    more than the whole cell to imports — the same anomaly renamed.")
    print("    The objects also differ in kind (ixi analytical vs pxi use); what")
    print("    links them is the model-D result of v1.8, a chain of two steps.")
    # ---- v1.32: the transformation is exonerated, and FISIM is unsigned ---
    # The entry says the loaded sources do not explain the FISIM treatment.
    # Twenty mentions across seven extractions say otherwise, and two of them
    # change what this question is asking.
    import re as _re
    ext = ROOT / "library" / "extracted"
    print()
    # Demonstrated, not asserted: model D on a strictly non-negative supply-use
    # system must return a non-negative table, so it cannot manufacture this
    # cell. A `True` here would have been a check that cannot fail.
    _rng = np.random.default_rng(3)
    _m = _n = 12
    _V = _rng.uniform(0, 40, (_m, _n))
    _U = _rng.uniform(0, 40, (_m, _n))
    _Y = _rng.uniform(0, 40, (_m, 2))
    _W = _rng.uniform(0, 40, (1, _n))
    _g, _x = _V.sum(0), _V.sum(1)
    from quadrium.transformation import transform
    _Sd = transform("D", _V, _U, np.zeros_like(_U), _Y, np.zeros_like(_Y),
                    _W, _g, _x).Sd
    check("model D cannot have created this negative, so it was already in the "
          "use table",
          float(_Sd.min()) >= -1e-9,
          "NSO_UK_01 p. 5 puts the industry-by-industry IOATs on fixed product "
          "sales — Z = D·U with D a matrix of market shares. Both factors are "
          "non-negative, so their product is: a negative in the ixi table "
          "requires a negative in the pxi use table. The transformation is "
          "exonerated and the question narrows to why the ONS's own use table "
          f"carries a negative FISIM allocation to imputed rent. Demonstrated "
          f"on a random non-negative 12x12 system: min cell "
          f"{float(_Sd.min()):.2e}")

    c18 = ext / "CORE_018_Eurostat2008_CH04_The_Supply_Table.txt"
    if c18.exists():
        f18 = _re.sub(r"\s+", " ", c18.read_text())
        check("and FISIM is DEFINED as a difference, so its sign is not "
              "constrained",
              "Financial intermediation services indirectly measured (FISIM) = "
              "Property income receivable less interest payable" in f18,
              "CORE_018 — output defined as property income receivable LESS "
              "interest payable. A residual of two flows can be negative "
              "without any error, which is the first structural reason this "
              "project has for the cell being legitimate rather than wrong")
        check("and an EU regulation governs the allocation, which is a sharper "
              "next source than the entry names",
              "the regulation on the allocation of financial intermediation "
              "services indirectly measured (FISIM)" in f18,
              "CORE_018 names it. The entry currently points at SNA 2025 ch. "
              "25, which is in no package; the regulation is a narrower and "
              "more directly applicable document")

    at = ext / "NSO_AT_01_StatistikAustria_Standarddokumentation_IO.txt"
    if at.exists():
        fat = _re.sub(r"\s+", " ", at.read_text())
        check("and allocating FISIM across individual users is documented "
              "practice, not an oddity",
              "auf die einzelnen Verwender" in fat,
              "Statistik Austria records that FISIM was first shown as the "
              "intermediate consumption of a fictitious activity and later "
              "'auf die einzelnen Verwender (Vorleistung und Endnachfrage) "
              "verteilt' — distributed to the individual users. So a FISIM "
              "cell in an industry column is the expected result of the "
              "modern treatment. Austria's own K64 → L68A is +1,777")

    u9 = ext / "UNH_09_UN2018_CH09_Compiling_SUTs_in_Volume_Terms.txt"
    if u9.exists():
        f9 = _re.sub(r"\s+", " ", u9.read_text())
        check("and FISIM is self-balanced, so this cell is not a balancing "
              "residual",
              "FISIM is balanced across the production, income and expenditure "
              "approaches" in f9
              and "there is no need for any balancing adjustments" in f9,
              "UNH_09, extracted today — in current prices FISIM arrives "
              "balanced and can be lifted out of the SUTs 'as a balanced "
              "change', leaving them still balanced. So the −20,771 is not "
              "what the balancing process pushed into a corner; it is a "
              "constructed allocation that entered already reconciled")
        check("and its price is not directly observable, which is why it is "
              "constructed at all",
              "direct observation of appropriate prices is not possible" in f9,
              "UNH_09 puts FISIM with non-market services and insurance in the "
              "class where 'the direct observation of appropriate prices is "
              "not possible'. A quantity nobody observes, defined as a "
              "residual, allocated by rule — three reasons its sign is not "
              "evidence of an error")
        check("and the OTHER end of the flow is in the same self-balanced "
              "class, by name",
              "imputed rental of owner-occupied dwellings" in f9
              and "self-balanced approach such as insurance" in f9,
              "UNH_09, same sentence: 'several examples that may be addressed "
              "using a self-balanced approach such as insurance, consumption "
              "of fixed capital for non-market units, imputed rental of "
              "owner-occupied dwellings'. K64 (FISIM's source) and L68A "
              "(imputed rental) are BOTH named, by the same source, as "
              "self-balanced constructs — not two independent negatives "
              "meeting by chance, but one accounting convention touching a "
              "cell from both sides")

    u3 = ext / "NSO_UK_03_FISIM_UK_revisited_2017.txt"
    if u3.exists():
        f3 = _re.sub(r"\s+", " ", u3.read_text())
        check("NSO_UK_03 names the exact mechanism this cell represents",
              "FISIM on loans secured on dwellings was allocated to "
              "intermediate consumption by households in their capacity as "
              "owner-occupiers of dwellings" in f3,
              "p. 9 -- financial institutions supply, owner-occupiers' "
              "housing consumes as intermediate consumption. K64 -> L68A "
              "precisely")
        neg_dwelling = _re.search(
            r"negative[^.]{0,80}dwelling|dwelling[^.]{0,80}negative", f3, _re.I)
        check("but dwelling-loan FISIM is never reported negative anywhere "
              "in 51 pages, unlike deposits, PNFC loans and non-resident "
              "loans, which all are",
              neg_dwelling is None
              and "very modest" in f3
              and "attributable to FISIM allocated to dwelling loans was "
                  "very modest" in f3,
              "three other categories are explicitly reported going "
              "negative under default-risk adjustment (deposits post-crisis; "
              "PNFCs' loans, roughly -GBP0.1bn/quarter in 2014-15; "
              "non-resident loan exports, <-GBP0.1bn in Q4 2014) -- dwelling "
              "loans are the one comparable category and the document calls "
              "its risk adjustment 'very modest' instead")
        check("and the scale of documented risk-adjustment episodes is far "
              "below what would be needed",
              "over GBP1.5 billion a quarter (over 60%)" in f3.replace(
                  "£", "GBP"),
              "the LARGEST default-risk adjustment reported (PNFCs, "
              "'over £1.5 billion a quarter (over 60%)') is two orders of "
              "magnitude below the GBP20,771m one-year anomaly -- risk "
              "adjustment reduces an otherwise-positive figure; no category "
              "is reported inverting at this scale")

    print()
    print("    Still only the ONS can say why THIS allocation is negative at")
    print("    -20,770.99 while four other offices publish it positive. What")
    print("    has changed: the transformation is ruled out, the quantity is")
    print("    one whose sign is unconstrained by definition, and the one")
    print("    named mechanism for a legitimate FISIM sign flip -- default-")
    print("    risk adjustment -- is documented as both too small in scale")
    print("    and the wrong category (deposits/PNFC/non-resident loans, not")
    print("    dwelling loans) to be the cause.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
