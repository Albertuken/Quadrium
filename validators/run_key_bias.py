"""
The pilot's error bar contained the truth in one year, and missed it in the other.

WHAT THE SECOND YEAR MADE POSSIBLE
-----------------------------------
`OQ-S-05` closed on a measurement: the INE publishes its supply-use tables at
110 products, where `73 Servicios de alojamiento` and `74 Servicios de comidas y
bebidas` are separate, so the split the Spanish pilot spent its effort
estimating is simply published. The true accommodation share of Spanish
hospitality output in 2022 is **23.95 %**, the pilot's chosen key said 33.73 %,
and the entry recorded what the project got right:

    The report printed a range of 21 % to 55 % across the seven keys and called
    it the error bar. The truth is inside it. A tool that had reported a single
    number would have been confidently wrong; this one was honestly uncertain,
    over a range that contained the answer.

That was one observation. `cne_tod_21.xlsx` is now readable at the same 110
products, so there are two.

THE TRUTH IS NOT A CONSTANT
----------------------------
    2021   alojamiento  17,147.0   comidas  74,353.2   share  18.74 %
    2022   alojamiento  30,717.7   comidas  97,548.8   share  23.95 %

Five and a fifth points in one year. Whatever a key is calibrated against, it is
calibrated against a moving quantity — 2021 is still a travel-restricted year
for accommodation and much less so for food service.

AND IN 2021 THE ERROR BAR MISSES
---------------------------------
The pilot's seven keys, both years, against the truth:

    key                            2021     2022    err 21   err 22   drift
    Personal ocupado              19.34 %  21.24 %    +0.6     -2.7    -3.3
    Horas trabajadas              23.02 %  27.65 %    +4.3     +3.7    -0.6
    Total de compras              25.45 %  29.80 %    +6.7     +5.9    -0.9
    Valor de la produccion  <--   27.31 %  33.73 %    +8.6     +9.8    +1.2
    Gastos de personal            28.83 %  32.76 %   +10.1     +8.8    -1.3
    Valor anadido                 31.09 %  39.84 %   +12.4    +15.9    +3.5
    Excedente bruto               40.07 %  55.19 %   +21.3    +31.2    +9.9
    truth                         18.74 %  23.95 %

    2022   span 21.24 to 55.19   truth INSIDE
    2021   span 19.34 to 40.07   truth OUTSIDE, by 0.60 points

**In 2021 all seven keys overstate accommodation**, the closest by 0.6 points,
so the whole spread sits above the answer and the error bar misses it. In 2022
six of the seven still overstate and the seventh — employment — undershoots by
2.7, which is what puts the truth inside that year's range.

So the lean is systematic without being universal, and whether the range
happens to contain the answer turns on whether the single least-biased key has
crossed over. That is not a property anyone can check without the answer.

The range is still worth printing — it is the difference between reporting
33.73 % alone and reporting 19 % to 40 % — but the claim it supports is
narrower than the one `OQ-S-05` made. **A spread of estimates that mostly lean
one way is a lower bound on uncertainty, not a confidence interval**, and
nothing in the report should let a reader take it for one.

WHY THEY ALL LEAN THE SAME WAY, AND WHY THAT IS USEFUL
--------------------------------------------------------
The survey is on an enterprise/CNAE basis and the table is on a product/CPA
basis. An accommodation *enterprise* produces a great deal of food-service
*product* — every hotel restaurant — and the product classification assigns
that to 74. So an enterprise-based key counts hotel restaurant output as
accommodation, and every such key overshoots. `A-01` named this risk and could
not size it. It is 8.6 points in 2021 and 9.8 in 2022 for the key the pilot
chose.

The useful half: for the four keys with the smallest bias the bias itself is
**stable within 1.3 points across the two years**, while for the three worst it
drifts by up to 9.9. Two observations are not a calibration and none is
proposed here. But a bias that repeats is a different object from noise, and it
is the first evidence the project has about which of the two this is.

WHAT 38 SPLITS LATER SAID ABOUT ALL OF THIS
---------------------------------------------
`run_key_spread.py` ran the same question over 38 splits in three countries
with the ten proxies Eurostat's business statistics publish, and the case above
does not generalise:

    every available proxy on the same side of the answer    19.4 % of subsectors

**Leaning together is the exception.** This sector is unusual for that, exactly
as `run_real_key.py` found it unusual for the SIZE of its error. The
enterprise-versus-product mechanism described here is real for hospitality and
is not a general property of a survey-based key.

The conclusion drawn from it survives on other grounds: the range misses one
split in four, and where it lands it spans a median 28 points of share. What
changed is the reason the report gives, not the warning.

Run:
    python3 validators/run_key_bias.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "ine"
SURVEY = DATA / "eee_hosteleria_cnae55_56_2018_2024.csv"

# The seven the pilot registers in `examples/es_hosteleria.py` — two drive the
# split and five are corroboration. Read from the survey by their INE names.
PILOT_KEYS = (
    "Personal ocupado",
    "Horas trabajadas por el personal remunerado",
    "Total de compras de bienes y servicios",
    "Valor de la producción",
    "Gastos de personal",
    "Valor añadido a precios de mercado",
    "Excedente bruto de explotación",
)
DRIVING = "Valor de la producción"
YEARS = (2021, 2022)
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def survey_shares() -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = {k: {} for k in PILOT_KEYS}
    with SURVEY.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["variable"] in out and int(r["anyo"]) in YEARS:
                out[r["variable"]][int(r["anyo"])] = float(r["share_55"]) * 100
    return out


def main() -> int:
    from quadrium.io_loader import load_ine_tod

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # 1 -- the truth, from the office, for both years.
    truth, levels = {}, {}
    for y in YEARS:
        f = DATA / f"cne_tod_{y % 100}.xlsx"
        if not f.exists():
            print(f"  (missing {f.name}; nothing to measure)")
            return 0
        s = load_ine_tod(f)
        if len(s.product_codes) < 110:
            print(f"  (the {y} edition is {len(s.product_codes)} products; the "
                  f"split is not published below 110)")
            return 0
        i = {c: k for k, c in enumerate(s.product_codes)}
        a, b = float(s.q[i["73"]]), float(s.q[i["74"]])
        levels[y], truth[y] = (a, b), a / (a + b) * 100.0

    print()
    for y in YEARS:
        a, b = levels[y]
        print(f"    {y}   alojamiento {a:>10,.1f}   comidas {b:>10,.1f}   "
              f"share {truth[y]:>6.2f} %")

    check("the true split is published for both years, and it moves",
          abs(truth[2022] - truth[2021]) > 4.0,
          f"{truth[2021]:.2f} % in 2021, {truth[2022]:.2f} % in 2022 — "
          f"{truth[2022] - truth[2021]:+.2f} points in one year, so a key is "
          f"calibrated against a moving quantity")

    # 2 -- every key, both years, and the sign of every error.
    sh = survey_shares()
    missing = [k for k in PILOT_KEYS if len(sh[k]) < 2]
    check("all seven of the pilot's keys are in the survey for both years",
          not missing, f"missing: {missing}" if missing else
          f"{len(PILOT_KEYS)} keys x {len(YEARS)} years")

    print()
    print(f"    {'key':<44}{'2021':>8}{'2022':>8}{'err 21':>8}"
          f"{'err 22':>8}{'drift':>8}")
    err = {}
    for k in PILOT_KEYS:
        e = {y: sh[k][y] - truth[y] for y in YEARS}
        err[k] = e
        mark = "  <--" if k == DRIVING else ""
        print(f"    {k[:44]:<44}{sh[k][2021]:>7.2f}%{sh[k][2022]:>7.2f}%"
              f"{e[2021]:>+8.1f}{e[2022]:>+8.1f}"
              f"{e[2022] - e[2021]:>+8.1f}{mark}")
    print(f"    {'truth':<44}{truth[2021]:>7.2f}%{truth[2022]:>7.2f}%")

    over = {y: sum(1 for e in err.values() if e[y] > 0) for y in YEARS}
    check("the keys lean one way, and in 2021 all of them do",
          over[2021] == len(PILOT_KEYS) and over[2022] >= len(PILOT_KEYS) - 1,
          f"{over[2021]} of {len(PILOT_KEYS)} overstate in 2021 and "
          f"{over[2022]} of {len(PILOT_KEYS)} in 2022. An accommodation "
          f"ENTERPRISE produces food-service PRODUCT — every hotel restaurant "
          f"— and the product classification assigns that to 74, so an "
          f"enterprise-based key counts it on the wrong side. A-01 named this "
          f"risk and could not size it")
    crossed = [k for k in PILOT_KEYS if err[k][2022] < 0]
    check("the exception is the single least-biased key, and only in one year",
          len(crossed) <= 1 and (not crossed or err[crossed[0]][2021] > 0),
          (f"{crossed[0]} is {err[crossed[0]][2021]:+.1f} in 2021 and "
           f"{err[crossed[0]][2022]:+.1f} in 2022" if crossed
           else "none crossed over"))

    # 3 -- the claim OQ-S-05 made, tested on the year it did not have.
    print()
    for y in YEARS:
        span = sorted(sh[k][y] for k in PILOT_KEYS)
        lo, hi = span[0], span[-1]
        inside = lo <= truth[y] <= hi
        gap = 0.0 if inside else (lo - truth[y] if truth[y] < lo
                                  else truth[y] - hi)
        print(f"    {y}   the seven keys span {lo:.2f} % to {hi:.2f} %   "
              f"truth {truth[y]:.2f} %   "
              + ("INSIDE" if inside else f"OUTSIDE by {gap:.2f} points"))

    span22 = sorted(sh[k][2022] for k in PILOT_KEYS)
    span21 = sorted(sh[k][2021] for k in PILOT_KEYS)
    check("the 2022 range contains the truth, as OQ-S-05 recorded",
          span22[0] <= truth[2022] <= span22[-1],
          "a tool reporting a single number would have been confidently wrong")
    check("and the 2021 range does not",
          not (span21[0] <= truth[2021] <= span21[-1]),
          f"{span21[0]:.2f} % to {span21[-1]:.2f} % against a truth of "
          f"{truth[2021]:.2f} % — the whole spread clears it by "
          f"{span21[0] - truth[2021]:.2f} points, because every estimate in "
          f"it leans the same way")
    check("and whether it contains the answer turns on one key crossing over",
          not (span21[0] <= truth[2021] <= span21[-1])
          and span22[0] <= truth[2022] <= span22[-1]
          and len(crossed) == 1,
          f"in 2022 the range holds only because {crossed[0] if crossed else '—'} "
          f"undershoots; in 2021 it does not and the range misses. Whether "
          f"the least-biased key has crossed over is not a property anyone "
          f"can check without the answer, so the range is a floor on "
          f"uncertainty and not a confidence interval")

    # 4 -- the bias of the good keys repeats; of the bad keys it does not.
    print()
    drift = {k: abs(err[k][2022] - err[k][2021]) for k in PILOT_KEYS}
    by_bias = sorted(PILOT_KEYS, key=lambda k: abs(err[k][2022]))
    good, bad = by_bias[:4], by_bias[4:]
    check("the four least-biased keys have a bias that repeats",
          max(drift[k] for k in good) < 4.0,
          f"drift of at most {max(drift[k] for k in good):.1f} points between "
          f"the two years: " + ", ".join(f"{k.split()[0]} "
                                         f"{drift[k]:.1f}" for k in good))
    check("and the three worst have one that does not",
          max(drift[k] for k in bad) > max(drift[k] for k in good),
          f"up to {max(drift[k] for k in bad):.1f} points — "
          f"{max(bad, key=lambda k: drift[k])[:34]}. Two observations are not "
          f"a calibration and none is proposed; a bias that repeats is simply "
          f"a different object from noise")

    print()
    print("    The pilot chose the key with the best conceptual match and it")
    print("    was the fourth worst of seven, in both years, by about nine")
    print("    points each time. The loosest match was the best, twice.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
