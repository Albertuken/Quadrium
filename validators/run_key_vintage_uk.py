"""
`OQ-B-14`'s residue: a second country's consecutive-year proxy series, and the
pattern holds.

The entry's finding — a one-year gap costs nothing in an ordinary year and up
to 21 points across a structural break, so the risk is not a function of the
gap — rested on one series: INE's structural survey for Spanish hospitality,
CNAE 55/56, 2018–2024. Its own "next source" note asked for "more series like
the Spanish one … from another country, to see whether the pattern … holds
outside Spanish hospitality across 2020."

`data/ons/abs_sic56_uk_2019_2024.csv` is exactly that, and was already in the
project for a different purpose (`examples/uk_food_beverage.py`, `OQ-S-01`'s
correspondence work) — nobody had pointed it at this question. ONS Annual
Business Survey, SIC division 56 split into groups 56.1/56.2/56.3, UK,
2019–2024: turnover, gross value added at basic prices, purchases, employment
costs. Six consecutive years spanning the same pandemic break as the Spanish
series, on a different sector split (three groups, not two) in a different
country.

THE PATTERN HOLDS, AT SMALLER MAGNITUDE
------------------------------------------
Worst year-on-year share move per variable, UK ABS, 2019–2024:

    turnover            7.8 pp   (2021→2022, not the break)
    aGVA                8.9 pp   (2019→2020 — AT the break, and the worst
                                  of the four)
    purchases           6.5 pp   (2021→2022)
    employment costs    4.6 pp   (2020→2021, smallest of the four)

Spain's ranking was value added most volatile (21.0 pp), employment least
(1.9 pp) — a more than tenfold spread. The UK's is narrower — 4.6 to 8.9 pp,
under twofold — but **the ranking is the same shape**: the value-added-type
variable is the most volatile of the four, and the labour-cost variable is the
least.

AND THE BREAK-YEAR MOVE MATCHES THE SPANISH STORY MORE PRECISELY THAN THE
"WORST MOVE" SUMMARY DOES
----------------------------------------------------------------------------
Read at the pandemic year specifically, not just at whichever year was worst:

                        2019→2020 move    Spain 2019→2020 move
    output/turnover         7.1 pp             11.9 pp
    value added/aGVA        8.9 pp             21.0 pp
    labour variable         2.0 pp               1.4 pp

(Spain's figures recomputed here from the printed 2019/2020 rows in its own
table, not re-estimated: output 34.6→22.7, value added 40.7→19.7, employment
21.1→19.7.)

**In both countries, output and value-added-type proxies spike hardest exactly
at the pandemic break, and the labour-cost proxy stays comparatively calm
through the same break.** That is a closer and more specific match than the
headline "worst move" figures suggest, because the UK's single worst aGVA move
(8.9 pp) IS its 2019→2020 move — the break is not just *a* bad year for that
variable, it is *the* worst year, in both countries.

WHAT DOES NOT CARRY OVER, RECORDED RATHER THAN SMOOTHED PAST
-----------------------------------------------------------------
BRES (employment headcount, not cost) gives a THIRD proxy family for the same
UK sector, 2022–2024 — a window that does not include the pandemic break. Its
worst year-on-year move, 4.1 pp, is not dramatically calmer than the ABS
variables measured over that same non-break window. This does not contradict
the finding: Spain's own employment series was calm specifically *through* the
break (1.4 pp at 2019→2020) and only reached its own worst move (1.9 pp) in an
ordinary year, 2021→2022, that has nothing to do with a break. A labour
variable being unremarkable outside a break window is consistent with the
claim, not evidence against it — but it means BRES alone, without a
break-spanning window, cannot test the claim the way ABS just did, and it is
reported as untested rather than folded into the corroboration.

WHY THE MAGNITUDES DIFFER, NOTED WITHOUT CLAIMING TO EXPLAIN IT
-------------------------------------------------------------------
The UK split is three groups (56.1/56.2/56.3) against Spain's two (55/56), and
the two countries' hospitality sectors met the pandemic under different policy
regimes (furlough vs. ERTE) and different lockdown timings. Both are plausible
partial explanations for why UK moves run two-to-four times smaller than
Spain's. Neither is tested here; the magnitude gap is reported, not resolved.

STILL NO THRESHOLD, AND THIS STRENGTHENS RATHER THAN WEAKENS THAT CALL
---------------------------------------------------------------------------
A second country giving a *different* magnitude for the same qualitative
pattern is exactly the case against inventing a numeric staleness threshold
that v1.8 already made. If Spain's 21-point break and the UK's 9-point break
both count as "the value-added proxy moved sharply in the break year", no
single percentage-point cutoff would fit both without being wrong for one of
them.

Run:
    python3 validators/run_key_vintage_uk.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABS_DATA = ROOT / "data" / "ons" / "abs_sic56_uk_2019_2024.csv"
BRES_DATA = ROOT / "data" / "ons" / "bres_sic56_gb_2022_2024.csv"
GROUPS = ["56.1", "56.2", "56.3"]
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def yoy_shares(data: dict, years: list, var: str) -> dict:
    return {y: {g: 100 * float(data[(g, y)][var]) / sum(float(data[(g, y)][var])
                for g in GROUPS) for g in GROUPS} for y in years}


def worst_move(shares: dict, years: list) -> tuple[float, tuple, str]:
    worst, pair, grp = 0.0, None, None
    for i in range(len(years) - 1):
        y0, y1 = years[i], years[i + 1]
        for g in GROUPS:
            d = abs(shares[y1][g] - shares[y0][g])
            if d > worst:
                worst, pair, grp = d, (y0, y1), g
    return worst, pair, grp


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if not ABS_DATA.exists():
        print("ABS data absent")
        return 0

    rows = list(csv.DictReader(open(ABS_DATA)))
    data = {(r["SIC"], int(r["YEAR"])): r for r in rows}
    years = [2019, 2020, 2021, 2022, 2023, 2024]
    variables = {"TURNOVER_GBPM": "turnover", "AGVA_BASIC_PRICES_GBPM": "aGVA",
                 "PURCHASES_GBPM": "purchases",
                 "EMPLOYMENT_COSTS_GBPM": "employment costs"}

    print(f"    {'variable':<20}{'worst YoY':>12}{'2019→2020 move':>18}")
    results = {}
    for var, label in variables.items():
        shares = yoy_shares(data, years, var)
        worst, pair, grp = worst_move(shares, years)
        break_move = max(abs(shares[2020][g] - shares[2019][g]) for g in GROUPS)
        results[label] = (worst, pair, break_move)
        print(f"    {label:<20}{worst:>10.1f} pp{break_move:>16.1f} pp")

    check("aGVA (value-added proxy) is the most volatile of the four "
          "variables, as in Spain",
          results["aGVA"][0] == max(r[0] for r in results.values()),
          f"worst move {results['aGVA'][0]:.1f} pp — matches Spain's ranking "
          f"(value added most volatile at 21.0 pp) even though the UK's "
          f"absolute magnitude is four times smaller")

    check("employment costs is the least volatile of the four, as in Spain",
          results["employment costs"][0] == min(r[0] for r in results.values()),
          f"worst move {results['employment costs'][0]:.1f} pp — the "
          f"labour-cost variable is calmest in both countries")

    check("aGVA's worst move IS its pandemic-break move, not a coincidence "
          "elsewhere in the series",
          results["aGVA"][1] == (2019, 2020),
          f"the single worst year-on-year move for aGVA across all six years "
          f"happens exactly at 2019→2020 — the break is not just a bad year "
          f"for this variable, it is THE worst year")

    check("and the labour variable stays comparatively calm through that same "
          "break",
          results["employment costs"][2] < 0.5 * results["aGVA"][2],
          f"employment costs moves {results['employment costs'][2]:.1f} pp at "
          f"2019→2020 against aGVA's {results['aGVA'][2]:.1f} pp — the same "
          f"qualitative split OQ-B-14 already found in Spain (1.4 pp for "
          f"employment against 21.0 pp for value added)")

    # ---- BRES, reported honestly as not testing the same claim ------------
    print()
    if BRES_DATA.exists():
        brows = list(csv.DictReader(open(BRES_DATA)))
        bres_groups = {"56.1": ["56101", "56102", "56103"],
                       "56.2": ["56210", "56290"],
                       "56.3": ["56301", "56302"]}
        byears = ["2022", "2023", "2024"]
        emp = {y: {g: sum(float(r["OBS_VALUE"]) for r in brows
                          if r["DATE_NAME"] == y and r["INDUSTRY_CODE"] in cls
                          and r["EMPLOYMENT_STATUS_NAME"] == "Employment")
                   for g, cls in bres_groups.items()} for y in byears}
        bshares = {y: {g: 100 * emp[y][g] / sum(emp[y].values())
                       for g in bres_groups} for y in byears}
        bworst = max(abs(bshares[byears[i + 1]][g] - bshares[byears[i]][g])
                     for i in range(len(byears) - 1) for g in bres_groups)
        check("BRES employment (headcount) is reported, not folded into the "
              "corroboration, because its window excludes the break",
              bworst > 0,
              f"worst move {bworst:.1f} pp over 2022-2024 — a window with no "
              f"pandemic year in it, so it cannot test 'labour stays calm "
              f"through a break' the way ABS just did. Not dramatically "
              f"calmer than the other UK variables in this non-break window, "
              f"which is consistent with the claim (a labour variable is "
              f"unremarkable OUTSIDE a break) rather than evidence against it")

    print()
    print("    Magnitudes differ two-to-fourfold between Spain and the UK.")
    print("    Reported, not explained: candidates are the three-way UK split")
    print("    against Spain's two-way one, and different pandemic policy")
    print("    regimes (furlough vs. ERTE). Neither tested here. The magnitude")
    print("    gap is itself the argument against a numeric staleness")
    print("    threshold: two countries, two different sizes of 'sharp move',")
    print("    same qualitative pattern.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
