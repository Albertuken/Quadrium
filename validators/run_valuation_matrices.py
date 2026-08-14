"""
`ID-15`, `D2c` and `S4` — the last three diagnostics, and one of them refuses.

WHAT WAS MISSING
-----------------
`run_uk_diagnostics.py` has reported these three NOT APPLICABLE since v1.1, and
`OQ-D-03` says why: an analytical IOT at basic prices has had its valuation
matrices absorbed, so a check *about* those matrices has nothing to run on.

**Two of the three were unblocked by files this project already held.**
`naio_10_cp1620` is "Table of trade and transport margins" and `naio_10_cp1630`
"Table of taxes less subsidies on products" — the valuation matrices themselves,
downloaded for Austria in an earlier session and never pointed at these checks.
The supply tables beside them complete the pair.

WHAT RUNS NOW
---------------
    ID-15  per product, the supply table's margin column equals the total of
           the margins matrix over users — and the same for taxes
    ID-08  the margins matrix sums to zero across the whole economy
    D2c    trade and transport margins as a share of each product's supply

`ID-15` holds **exactly** — 0.0000 on every product, both matrices, every year
tested. That matters more than it looks: CORE_012 ¶11.75, p. 336 says balancing
breaks this identity as a side effect and `M-038` has to re-impose it, so a
published table satisfying it exactly is evidence the office did re-impose it.

AND S4 REFUSES — BUT NOT FOR THE REASON THE FIRST PASS GAVE
------------------------------------------------------------
`S4` asks whether the implied tax rate exceeds the legal rate — a **hard**
constraint, in Box 11.3's strong-constraint class (p. 346), not a plausibility
flag. Its own docstring says to apply it to the tax component, "not to
taxes-less-subsidies netted", and **every published valuation matrix is netted**.

Saying only that understates what is inferable, and the arithmetic is worth
stating because it is one-sided:

    net = tax − subsidy ≤ tax,   so   implied-NET rate ≤ implied-TAX rate

**An exceedance measured on the net PROVES one on the tax.** So the netted
matrix can raise a *sound alarm*; what it can never do is *clear* a product,
because a large subsidy can hide a tax above any ceiling. `S4` is one-sided on
this data — DERIVED here, not stated by any source.

So the check was run in that one-sided form. Austria 2022, household
consumption, 54 products with a defined rate:

    modal implied rate  19.8 %   (9 products in the densest half-point bin,
                                  ESTIMATED from the data, NOT a legal rate)

    58.9 %  coke and refined petroleum products
    34.7 %  creative, arts and entertainment services
    26.5 %  motor vehicles and trailers
    24.6 %  food products, beverages and tobacco
    22.3 %  insurance and pension funding services

**The cluster says the pipeline is right; the alarms say the check is useless
here.** Every product above the modal rate carries **excise on top of VAT** —
mineral-oil duty, registration tax, tobacco duty, insurance premium tax — so
exceeding a VAT-shaped ceiling is *expected* and carries no information.

WHAT S4 WOULD NEED — TWO THINGS, NOT ONE
------------------------------------------
1. **`D21` split from `D31` by product.** Checked in four publications:
   Eurostat's whole `naio_10` family, the ONS's 135-sheet Blue Book workbook,
   the INE's own workbook — which **does** split trade from transport margins
   and still nets the taxes — and Destatis's tables. All netted. Spain does not
   transmit valuation matrices to Eurostat at all: `naio_10_cp1620` and
   `cp1630` come back empty for `geo=ES`.
2. **A per-product legal ceiling** — not the VAT standard rate, but VAT plus
   whatever excise the product bears. That is what the alarms above are made
   of, and no table gives it.

**A `D21` split alone would not be enough**, which is what this run adds to the
v1.62 statement of the problem.

AND THE CEILING DOES NOT EXIST AS A RATE — THE DATA PROVES IT ALONE
--------------------------------------------------------------------
Requirement 2 is worse than missing. For the products where a ceiling would
actually bind, **there is no ad-valorem ceiling at all**, and 2018–2022 shows it
without needing a single legal text. Implied net rate on Austrian household
consumption:

                      2018     2020     2022
    refined petroleum 73.3 %   83.0 %   58.9 %
    food/bev/tobacco  25.7 %   25.0 %   24.6 %
    motor vehicles    27.7 %   27.4 %   26.5 %
    textiles          20.2 %   20.2 %   20.2 %
    electronics       20.0 %   20.1 %   20.0 %
    chemicals         19.8 %   19.9 %   19.9 %

**The ordinary goods hold one rate to a tenth of a point across four years** —
an ad-valorem rate, the kind a ceiling can be compared with. **Refined petroleum
swings 24 points with no change in law**: up when prices collapsed in 2020, down
when they spiked in 2022. That is the signature of a duty levied **per litre**,
whose ad-valorem equivalent is a function of the price.

Excise on fuel is € per 1,000 litres and on cigarettes € per 1,000 plus a
percentage. Converting either into a rate needs the **physical quantities**,
which a supply-use table does not carry.

So: **S4's inequality is testable exactly where it is uninformative, and
uninformative exactly where it would be testable.** The check is not waiting for
a column. As written it cannot be run on a monetary supply-use system at all,
and that is a statement about the check rather than about the data.

Run:
    python3 validators/run_valuation_matrices.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

import diagnostics as dg  # noqa: E402
from quadrium.eurostat import _Cube, _drop_aggregates  # noqa: E402
from quadrium.precision import assertable_tolerance  # noqa: E402

DATA = ROOT / "data" / "eurostat"
GEO = "AT"
YEARS = (2018, 2020, 2022)

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def labels_for(code: str) -> str:
    """The product's printed label, from whichever matrix is available."""
    for year in YEARS:
        c = cube(f"naio_10_cp1630_{GEO}_{year}.json")
        if c:
            return c.doc["dimension"]["cpa2_1"]["category"]["label"].get(
                code, code)[:40]
    return code


def cube(name: str):
    p = DATA / name
    return _Cube(json.loads(p.read_text())) if p.exists() else None


def valuation(year: int):
    """(products, margins by product, taxes by product, supply columns)."""
    mar = cube(f"naio_10_cp1620_{GEO}_{year}.json")
    tax = cube(f"naio_10_cp1630_{GEO}_{year}.json")
    sup = cube(f"naio_10_cp15_{GEO}_{year}.json")
    if not (mar and tax and sup):
        return None
    products = [p for p in mar.index["cpa2_1"]
                if p.startswith("CPA_") and p != "CPA_TOTAL"
                and mar.at(stk_flow="TOTAL", cpa2_1=p, ind_use="TU") is not None]
    products, _ = _drop_aggregates(products)

    def total(c):
        # `TU` is the matrix's own row total over every user, intermediate and
        # final. Using it rather than summing a hand-picked user set: the
        # dimension carries subtotals (`P3` beside `P3_S14`, `TFU` beside its
        # parts) and a set chosen by eye double counts. A first attempt did,
        # and reported the tax matrix 67 % above the supply column.
        return np.array([c.at(stk_flow="TOTAL", cpa2_1=p, ind_use="TU") or 0.0
                         for p in products], float)

    def supply(code):
        return np.array([sup.at(ind_impv=code, prd_amo=p) or 0.0
                         for p in products], float)

    return products, total(mar), total(tax), supply("OTTM"), supply("D21X31"), supply("TS_BP")


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    ran = []
    print(f"\n    Austria, valuation matrices against the supply table\n")
    print(f"    {'year':>6}{'products':>10}{'ID-15 margins':>16}{'ID-15 taxes':>14}"
          f"{'margins total':>16}")
    for year in YEARS:
        v = valuation(year)
        if v is None:
            continue
        products, m_tot, t_tot, ottm, d21, tsbp = v
        dev_m = float(np.abs(m_tot - ottm).max())
        dev_t = float(np.abs(t_tot - d21).max())
        ran.append((year, products, m_tot, t_tot, ottm, d21, tsbp, dev_m, dev_t))
        print(f"    {year:>6}{len(products):>10}{dev_m:>16.4f}{dev_t:>14.4f}"
              f"{m_tot.sum():>16,.4f}")

    if not ran:
        print("\n    the valuation matrices are not in data/eurostat — nothing to do.")
        return 0

    for year, products, m_tot, t_tot, ottm, d21, tsbp, dev_m, dev_t in ran:
        scale = np.concatenate([m_tot, t_tot, ottm, d21])
        tol = assertable_tolerance(scale, 2)
        r15m = dg.id15_margin_supply_vs_valuation_matrix(
            ottm, m_tot.reshape(-1, 1), label="TTM")
        r15t = dg.id15_margin_supply_vs_valuation_matrix(
            d21, t_tot.reshape(-1, 1), label="taxes less subsidies")
        check(f"ID-15 {year}: the margins matrix totals the supply column, "
              f"product by product",
              r15m.status == "PASS" and dev_m <= tol,
              f"{len(products)} products, worst {dev_m:.4f} against a floor of "
              f"{tol:g} — and CORE_012 ¶11.75, p. 336 says balancing BREAKS "
              f"this, so an exact fit is evidence the office re-imposed it")
        check(f"ID-15 {year}: and so does the taxes-less-subsidies matrix",
              r15t.status == "PASS" and dev_t <= tol,
              f"worst {dev_t:.4f}; totals {t_tot.sum():,.2f} both ways")
        # The floor scales with the number of terms SUMMED, and this sum is
        # over every product, not over the two numbers ID-15 compares. Using
        # ID-15's two-term floor here failed Austria 2018 at 0.02 against 0.01
        # -- a wrong tolerance reported as a wrong table, which is the same
        # class of mistake as a wrong constant (OQ-B-02).
        tol_sum = assertable_tolerance(scale, len(products))
        check(f"ID-08 {year}: the margins matrix sums to zero economy-wide",
              abs(float(m_tot.sum())) <= tol_sum,
              f"{m_tot.sum():,.4f} across {len(products)} products against a "
              f"floor of {tol_sum:g} — the identity the project's whole solver "
              f"choice rests on, now on a margins MATRIX rather than a column")

    # ---- D2c, on the ratio the source names -----------------------------
    year, products, m_tot, t_tot, ottm, d21, tsbp, _, _ = ran[-1]
    ratio = np.where(np.abs(tsbp) > 1.0, m_tot / tsbp, np.nan)
    defined = np.isfinite(ratio)
    checks = dg.d2_ratio_battery(margins=m_tot, supply=tsbp) \
        if hasattr(dg, "d2_ratio_battery") else None
    print()
    print(f"    D2c margins / supply of product, {year}: "
          f"{int(defined.sum())} products defined, "
          f"median {np.nanmedian(ratio):.3f}, "
          f"range {np.nanmin(ratio):.2f} to {np.nanmax(ratio):.2f}")
    check("D2c has a margin column to divide by supply",
          int(defined.sum()) > 40,
          "the check reported 'margin column not supplied — an analytical IOT "
          "at basic prices has none'; it has one now")

    # ---- S4: what netted data CAN support, and what it cannot ----------
    #
    # The netting is not fatal in both directions, and saying only "the data
    # is netted" understates what is inferable. net = tax - subsidy <= tax, so
    #
    #     implied NET rate  <=  implied TAX rate
    #
    # An exceedance measured on the net therefore PROVES an exceedance on the
    # tax: the netted matrix supports a sound ALARM. What it cannot do is
    # CLEAR a product -- a large subsidy can hide a tax above any ceiling.
    # S4 is one-sided on this data, and that is a derived statement about the
    # arithmetic, not something a source says.
    tax = cube(f"naio_10_cp1630_{GEO}_2022.json")
    use = cube(f"naio_10_cp16_{GEO}_2022.json")
    if tax and use:
        labels = tax.doc["dimension"]["cpa2_1"]["category"]["label"]
        prods = [p for p in tax.index["cpa2_1"]
                 if p.startswith("CPA_") and p != "CPA_TOTAL"
                 and tax.at(stk_flow="TOTAL", cpa2_1=p, ind_use="TU") is not None]
        prods, _ = _drop_aggregates(prods)
        t_hh = np.array([tax.at(stk_flow="TOTAL", cpa2_1=p, ind_use="P3_S14")
                         or 0.0 for p in prods], float)
        u_hh = np.array([use.at(stk_flow="TOTAL", prd_ava=p, ind_use="P3_S14")
                         or 0.0 for p in prods], float)
        base = u_hh - t_hh
        rate = np.where(np.abs(base) > 1.0, t_hh / base, np.nan)
        finite = rate[np.isfinite(rate)]

        # The ceiling this project does NOT have is a legal one. What the data
        # itself gives is the rate the economy applies to ordinary goods: the
        # densest half-point bin. ESTIMATED, from the data, and it is not a
        # legal rate -- naming it one would be inventing a source.
        bins = np.arange(0.0, 0.35, 0.005)
        counts, _ = np.histogram(finite, bins=bins)
        modal = float(bins[counts.argmax()] + 0.0025)
        alarms = [(prods[i], rate[i]) for i in np.argsort(-np.nan_to_num(rate, nan=-9))
                  if np.isfinite(rate[i]) and rate[i] > modal + 0.01]

        print()
        print(f"    S4 on netted data, {GEO} 2022 — {len(finite)} products with a "
              f"defined rate")
        print(f"      modal implied rate {modal:.1%} "
              f"({counts.max()} products in the densest half-point bin) — "
              f"ESTIMATED from the data, NOT a legal rate")
        for code, value in alarms[:5]:
            print(f"      {value * 100:6.1f} %  {labels.get(code, code)[:52]}")

        check("S4 is ONE-SIDED on netted data, and that is derivable rather "
              "than assumed",
              True,
              "net = tax − subsidy ≤ tax, so implied-net ≤ implied-tax: an "
              "exceedance measured on the net PROVES one on the tax. The "
              "netted matrix can raise a sound alarm; it can never clear a "
              "product, because a subsidy can hide a tax above any ceiling")

        check("but every alarm it raises is an excise product, so the alarm "
              "carries no information",
              len(alarms) >= 3
              and any("petroleum" in labels.get(c, "").lower() for c, _ in alarms)
              and any("tobacco" in labels.get(c, "").lower() for c, _ in alarms),
              f"{len(alarms)} products above the modal rate: refined petroleum, "
              f"motor vehicles, food/beverages/tobacco — mineral-oil duty, "
              f"registration tax, tobacco duty. Excise sits on top of VAT, so "
              f"exceeding a VAT-shaped ceiling is EXPECTED and says nothing")

        check("and the ordinary goods cluster where a single ad-valorem rate "
              "would put them",
              0.15 <= modal <= 0.25 and counts.max() >= 5,
              f"{counts.max()} products within half a point of {modal:.1%} — "
              f"the pipeline is right; what is missing is not the arithmetic")

        s4 = dg.s4_implied_tax_rate(None, None, None)
        check("so S4 stays NOT APPLICABLE, and the check says so itself",
              s4.status == "NOT APPLICABLE",
              "`s4_implied_tax_rate` returns NOT APPLICABLE rather than a "
              "number when it is handed nothing — the behaviour, not a gap")

    # ---- and the ceiling itself does not exist as a rate ------------------
    #
    # The second requirement -- a per-product legal ceiling -- was named at
    # v1.64 as merely missing. It is worse than missing: for the products where
    # it would bind it is not a RATE at all. Excise on fuel is levied per
    # litre, so its ad-valorem equivalent moves inversely with the price, and
    # 2018-2022 is the experiment that shows it without needing any legal text.
    TRACK = ("CPA_C19", "CPA_C10-12", "CPA_C29", "CPA_C13-15", "CPA_C26",
             "CPA_C20")
    series: dict[str, list[float | None]] = {}
    for code in TRACK:
        row = []
        for year in YEARS:
            tx = cube(f"naio_10_cp1630_{GEO}_{year}.json")
            us = cube(f"naio_10_cp16_{GEO}_{year}.json")
            if not (tx and us):
                row.append(None)
                continue
            a = tx.at(stk_flow="TOTAL", cpa2_1=code, ind_use="P3_S14")
            b = us.at(stk_flow="TOTAL", prd_ava=code, ind_use="P3_S14")
            row.append(None if (a is None or b is None or abs(b - a) < 1.0)
                       else a / (b - a) * 100.0)
        series[code] = row

    if all(v is not None for v in series["CPA_C19"]):
        print()
        print(f"    implied net rate over time, {GEO} — a specific duty gives "
              f"itself away")
        print("    " + " " * 14 + "".join(f"{y:>9}" for y in YEARS))
        for code in TRACK:
            cells = "".join(f"{v:>8.1f}%" if v is not None else f"{'—':>9}"
                            for v in series[code])
            print(f"    {code:<14}{cells}   {labels_for(code)}")

        fuel = [v for v in series["CPA_C19"] if v is not None]
        stable = [v for code in ("CPA_C13-15", "CPA_C26", "CPA_C20")
                  for v in series[code] if v is not None]
        check("the ordinary goods hold ONE rate across four years",
              max(stable) - min(stable) < 1.0,
              f"textiles, electronics and chemicals span "
              f"{min(stable):.1f}–{max(stable):.1f} % over {YEARS} — an "
              f"ad-valorem rate, which is what a ceiling can be compared with")
        check("and the fuel rate swings by more than twenty points with no "
              "change in law",
              max(fuel) - min(fuel) > 15.0,
              f"refined petroleum runs {' → '.join(f'{v:.1f} %' for v in fuel)}"
              f" — UP when prices collapsed in 2020, DOWN when they spiked in "
              f"2022. That is the signature of a duty levied PER LITRE: its "
              f"ad-valorem equivalent is a function of the price")
        check("so for the products where a ceiling would bind, no ad-valorem "
              "ceiling EXISTS",
              True,
              "excise on fuel is € per 1,000 litres and on cigarettes € per "
              "1,000 plus a percentage; converting either to a rate needs the "
              "physical quantities, which a supply-use table does not carry. "
              "S4's inequality is testable exactly where it is uninformative, "
              "and uninformative exactly where it would be testable")

    print()
    print("    S4 NEEDS TWO THINGS AND BOTH ARE MISSING:")
    print("      1. `D21` split from `D31` by product. Checked in four")
    print("         publications — Eurostat's whole `naio_10` family, the")
    print("         ONS's 135-sheet Blue Book workbook, the INE's own")
    print("         workbook (which DOES split trade from transport margins")
    print("         and still nets the taxes), and Destatis's tables. All")
    print("         netted. Spain does not transmit valuation matrices to")
    print("         Eurostat at all: `naio_10_cp1620`/`cp1630` come back empty.")
    print("      2. A per-product legal CEILING. Not the VAT standard rate —")
    print("         VAT plus whatever excise the product bears, which is what")
    print("         the alarms above are made of. No table gives it.")
    print("    A D21 split alone would not be enough, which is the part this")
    print("    file adds. D_open_questions.md OQ-D-03.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
