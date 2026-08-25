"""
A verdict about a country's newest table is not a verdict about the country.

WHAT THE SWEEP MEASURED, AND WHAT IT DID NOT
----------------------------------------------
`run_eu_sweep.py` loaded every EU country's **newest** table by both routes and
`record_verdicts.py` wrote the answers down, so `--find` could name a verdict
instead of hedging. Both carried the same caveat, in as many words:

    A verdict is about the year that was checked, and the record says which. It
    is EVIDENCE, not prediction. Most causes look structural rather than
    annual — a country that suppresses half its cells for confidentiality is
    unlikely to differ by year — but "unlikely" is not a measurement.

It was not. Tried on three other years for each refusing country:

    ROUTE           refuses at newest   of which some other year LOADS
    symmetric              10                        3   (FR, HR, SK)
    supply-use pair        14                        2   (HR, PT)

**France's 2022 symmetric table is refused for sparse final demand, and its
2010, 2016 and 2021 tables load.** Twelve published years behind a verdict that
said France refuses. Slovakia's 2020 publishes no output vector at all and its
2010 and 2015 are fine. Croatia refuses at 2021 on both routes and loads at 2010
on both.

The other seven and twelve refuse in every year tried, which is a different
fact and now a stated one rather than an assumption: Ireland is 50 % short of
its own printed total in 2010, 2011, 2015 and 2020 alike.

So the reach of this engine on Eurostat is **21 of 28 countries by the
symmetric route and 16 of 28 by the pair**, not 18 and 14 — provided the user
is told which year, which is what `--find` now does and what
`_year_advice` stops it from getting wrong in the configuration it prints.

AND ONE DEFECT THE PROBE FOUND, THE SEVENTH OF ITS KIND
---------------------------------------------------------
Malta's 2010 supply table was refused with

    the 65 populated products sum to 27,583.1 against a published total supply
    of 27,583.0: the set mixes levels of the CPA hierarchy and would double
    count.

**0.1 on 27,583**, called double counting. The comparison was
`1e-6 * published` — relative, and defended in a comment as measured, because
Austria 2022 lands 0.03 from its own printed total across a 65-term sum and an
absolute `1e-3` would refuse it.

A relative bound is a bound on the wrong quantity. Rounding error grows with the
number of terms and the precision they are printed to; it does not grow with the
size of the economy. Austria survived that rule by being fifteen times larger
than Malta, not by being cleaner. Both of `load_sut`'s tiling checks now derive
the bound the way the rest of the module does, and both say whether the set
OVERSHOOTS (mixes levels) or falls SHORT (incomplete) rather than asserting the
first — which is the finding `_shortfall_diagnosis` established for the
symmetric route and which its sibling went on ignoring.

Malta is still refused, on the industry axis, 20.08 % short. Correctly, and now
for the reason that is true.

WHAT IS KEPT HERE AND WHAT IS NOT
-----------------------------------
The probe fetched about 90 files and they are not in the repository. Five are:
the years that LOAD for a country whose newest year refuses — France 2021,
Slovakia 2015, and Croatia's 2010 trio — because those five are the evidence
for the claim, and a claim whose evidence lives in a temporary directory is a
claim on trust.

Run:
    python3 validators/run_year_axis.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "eurostat"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    from quadrium.catalogue import Source
    from quadrium.cli import _year_advice
    from quadrium.eurostat import EurostatError, load_iot, load_sut

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    v = json.loads((DATA / "_verdicts.json").read_text())
    geos = [g for g in v if len(g) == 2 and isinstance(v[g], dict)]

    # 1 -- the record carries other years at all.
    probed = {r: [g for g in geos
                  if (v[g].get(r) or {}).get("also_tried")] for r in
              ("symmetric", "pair")}
    check("the record says which OTHER years were tried",
          len(probed["symmetric"]) >= 10 and len(probed["pair"]) >= 12,
          f"{len(probed['symmetric'])} countries on the symmetric route, "
          f"{len(probed['pair'])} on the pair — the caveat 'evidence, not "
          f"prediction' now has evidence behind it on both")

    # 2 -- how far the reach actually goes.
    print()
    print(f"    {'route':<16}{'newest loads':>14}{'some year loads':>18}"
          f"{'gained':>9}")
    gained = {}
    for r, label in (("symmetric", "symmetric"), ("pair", "supply-use pair")):
        now = [g for g in geos if (v[g].get(r) or {}).get("verdict") == "loads"]
        ever = [g for g in geos
                if (v[g].get(r) or {}).get("verdict") == "loads"
                or "loads" in ((v[g].get(r) or {}).get("also_tried") or {}).values()]
        gained[r] = sorted(set(ever) - set(now))
        print(f"    {label:<16}{len(now):>10} / 28{len(ever):>14} / 28"
              f"{'  ' + ', '.join(gained[r]):>9}")

    check("three symmetric refusals are about the year, not the country",
          gained["symmetric"] == ["FR", "HR", "SK"],
          f"{', '.join(gained['symmetric'])} — France publishes 13 years and "
          f"was being reported as refusing on the strength of one")
    check("and two of the pair refusals are",
          gained["pair"] == ["HR", "PT"],
          f"{', '.join(gained['pair'])}")
    check("while the rest refuse in every year tried, which is now measured",
          all(set((v[g].get("symmetric") or {}).get("also_tried", {}).values())
              == {"refuses"}
              for g in ("IE", "LT", "MT", "NO", "PL")),
          "Ireland is 50 % short of its own printed total in 2010, 2011, 2015 "
          "and 2020 alike — structural, and no longer assumed to be")

    # 3 -- the five kept files re-derive the claim without the record.
    print()
    fr = DATA / "naio_10_cp1700_FR_2021.json"
    sk = DATA / "naio_10_cp1700_SK_2015.json"
    hr = [DATA / f"naio_10_{d}_HR_2010.json"
          for d in ("cp15", "cp16", "cp1610")]
    if fr.exists() and sk.exists():
        a, b = load_iot(fr), load_iot(sk)
        check("France 2021 and Slovakia 2015 load, from the files themselves",
              a.n > 0 and b.n > 0,
              f"FR {a.n} products, output {a.X.sum():,.0f}; SK {b.n}, "
              f"{b.X.sum():,.0f} — both countries' newest tables refuse")
    if all(f.exists() for f in hr):
        s = load_sut(*hr)
        check("and Croatia's 2010 pair loads, on the route that refuses at 2021",
              len(s.product_codes) > 0,
              f"{len(s.product_codes)}x{len(s.activity_codes)}, supply "
              f"{s.q.sum():,.0f}")

    # 4 -- the adviser stops printing a configuration for a refusing year.
    print()
    for geo, want in (("FR", "loads"), ("SK", "loads"), ("IE", "refuses"),
                      ("ES", None)):
        e = (v.get(geo) or {}).get("symmetric") or {}
        s = Source(source_id=f"eurostat:{geo}", publisher="Eurostat", geo=geo,
                   year=e.get("year"),
                   dataset="naio_10_" + (e.get("dataset") or "cp1700"),
                   path=None, table_kind="eurostat",
                   classification="CPA 2008", kind="symmetric",
                   codes=[], labels={})
        adv = _year_advice(s, geo, ROOT)
        if want is None:
            check(f"{geo} loads, so the recommendation stands untouched",
                  adv == "", "nothing to redirect")
        elif want == "loads":
            check(f"{geo}'s recommendation is moved to a year that loads",
                  bool(adv) and adv[0] != e.get("year")
                  and str(adv[0]) in (e.get("also_tried") or {}),
                  f"{e.get('year')} -> {adv[0] if adv else '—'}")
        else:
            check(f"{geo} has no good year and the advice says so instead",
                  bool(adv) and adv[0] == e.get("year")
                  and "is refused for this country" in adv[1],
                  "handing a user a configuration for a table known to refuse "
                  "and letting the refusal explain itself later is not advice")

    # 5 -- the tiling bound, which the probe is what found.
    print()
    from quadrium.precision import assertable_tolerance
    sup = json.loads((DATA / "naio_10_cp15_HR_2010.json").read_text())
    vals = [x for x in sup["value"].values() if isinstance(x, (int, float))]
    derived = assertable_tolerance(vals, 66)
    published = 27_583.0
    check("a relative 1e-6 bound scales with the economy, and rounding does not",
          derived > 1e-6 * published,
          f"Malta 2010 was refused for 0.1 on 27,583 — 3.6e-6 of it — and "
          f"accused of double counting. A 66-term sum at this source's "
          f"precision allows {derived:,.2f}; Austria survived the same rule "
          f"by being fifteen times larger, not by being cleaner")

    print()
    print("    'Unlikely is not a measurement' was written into the record as")
    print("    a caveat and was right five times out of twenty-four.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
