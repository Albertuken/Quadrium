"""
What it costs to use a proxy from the wrong year, measured instead of assumed.

The engine stored `AllocationKey.source_year` from the first version, printed it,
exported it — and compared it with `table.year` nowhere. A 2019 proxy driving a
2022 table warned nobody.

Fixing the silence needed a decision about what the warning should SAY, and the
honest answer was not available from the manuals: none of the loaded sources
states how stale a proxy may be. So it was measured, on the one series where the
project holds seven consecutive years of the same proxy for the same two
subsectors — the INE's structural business survey for CNAE 55 and 56.

The result decided the design, and it is printed below:

  * In an ordinary year a share barely moves. Employment moved 0.1 points
    between 2018 and 2019 and the output share 0.6 points, which is the pair
    the report prints beside a stale key.
  * Across 2020 it moves by up to 21 points, and output by 11.9.
  * So the cost of a one-year gap is NOT a function of the gap. It depends on
    whether a break falls inside it, which the engine cannot see and the analyst
    can. The check therefore reports the gap and the measured volatility, and
    refuses to convert either into a verdict.
  * And it is why `key_from_series` interpolates but never extrapolates.

Reads `data/ine/eee_hosteleria_cnae55_56_2018_2024.csv`, so the claims here and
the file's own provenance cannot drift apart.

Run:
    python3 validators/run_key_vintage.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quadrium.models import (AllocationKey, ProxyStrength,  # noqa: E402
                              key_from_series)

DATA = ROOT / "data" / "ine" / "eee_hosteleria_cnae55_56_2018_2024.csv"
CODES = ["36A", "36B"]
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def series(variable: str) -> dict[int, list[float]]:
    out = {}
    with DATA.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["variable"] == variable:
                out[int(r["anyo"])] = [float(r["cnae_55"]), float(r["cnae_56"])]
    if not out:
        raise SystemExit(f"variable {variable!r} not in {DATA.name}")
    return out


VARIABLES = [
    ("Valor de la producción", "output"),
    ("Valor añadido a precios de mercado", "value added"),
    ("Personal ocupado", "employment"),
    ("Gastos de personal", "compensation"),
]


def main() -> int:
    if not DATA.exists():
        print(f"fixture absent: {DATA}")
        return 0

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 72)
    print("1. HOW MUCH THE SHARE ACTUALLY MOVES")
    print("=" * 72)
    print("Share of CNAE 55 (accommodation) in hospitality, per cent.\n")
    all_years = sorted(series(VARIABLES[0][0]))
    print(f"  {'proxy':<22}" + "".join(f"{y:>8}" for y in all_years)
          + f"{'worst move':>13}")
    volatility = {}
    for var, label in VARIABLES:
        s = series(var)
        sh = {y: v[0] / sum(v) for y, v in s.items()}
        moves = [abs(sh[b] - sh[a]) * 100 for a, b in zip(all_years, all_years[1:])]
        volatility[label] = max(moves)
        print(f"  {label:<22}"
              + "".join(f"{sh[y] * 100:>7.1f}%" if y in sh else f"{'—':>8}"
                        for y in all_years)
              + f"{max(moves):>10.1f} pp")

    # Printed, not just tested: the report quotes both of these year-on-year
    # moves at the reader, and `run_report_claims.py` can only see a figure a
    # validator actually states.
    emp_move = abs(
        series("Personal ocupado")[2019][0] / sum(series("Personal ocupado")[2019])
        - series("Personal ocupado")[2018][0] / sum(series("Personal ocupado")[2018])
    ) * 100
    out_move = abs(
        series("Valor de la producción")[2019][0] / sum(series("Valor de la producción")[2019])
        - series("Valor de la producción")[2018][0] / sum(series("Valor de la producción")[2018])
    ) * 100
    check("an ordinary year moves the share very little",
          emp_move < 0.5,
          f"employment 2018 -> 2019 moved {emp_move:.1f} pp, and the output "
          f"share {out_move:.1f} pp over the same year — which is the pair the "
          f"report prints beside a stale key")
    check("a break moves it by more than ten points",
          volatility["output"] > 10.0,
          f"output, worst year-on-year move {volatility['output']:.1f} pp")
    check("and how much depends on WHICH proxy, not only on the gap",
          volatility["value added"] > 10 * volatility["employment"],
          f"value added {volatility['value added']:.1f} pp against employment "
          f"{volatility['employment']:.1f} pp, same years, same subsectors")

    print("\n" + "=" * 72)
    print("2. INTERPOLATION HELPS ACROSS A BREAK, AND DOES NOT SAVE YOU")
    print("=" * 72)
    s = series("Valor de la producción")
    truth = s[2020][0] / sum(s[2020])
    without_2020 = {y: v for y, v in s.items() if y != 2020}
    interp = key_from_series("k", "output", CODES, without_2020, 2020,
                             "INE EEE", ProxyStrength.MEDIUM)
    stale = key_from_series("k", "output", CODES, {2019: s[2019]}, 2020,
                            "INE EEE", ProxyStrength.MEDIUM)
    e_i = abs(interp.w[0] - truth) * 100
    e_s = abs(stale.w[0] - truth) * 100
    print(f"  true 2020 share of accommodation      {truth * 100:>6.1f} %")
    print(f"  interpolated from 2019 and 2021       {interp.w[0] * 100:>6.1f} %"
          f"   error {e_i:>5.1f} pp")
    print(f"  the 2019 figure used as it stands     {stale.w[0] * 100:>6.1f} %"
          f"   error {e_s:>5.1f} pp")
    check("interpolation beats using the stale year", e_i < e_s,
          f"{e_i:.1f} pp against {e_s:.1f} pp")
    check("and is still badly wrong, which is the point", e_i > 5.0,
          f"{e_i:.1f} pp is not a rounding error — no method recovers a break "
          f"from the years either side of it")
    check("the interpolated key records what it did",
          interp.vintage["method"] == "interpolated"
          and interp.vintage["years_used"] == [2019, 2021],
          str(interp.vintage))

    print("\n" + "=" * 72)
    print("3. OUTSIDE THE RANGE, NO TREND IS EXTRAPOLATED")
    print("=" * 72)
    out = key_from_series("k", "output", CODES,
                          {y: s[y] for y in (2018, 2019)}, 2024,
                          "INE EEE", ProxyStrength.MEDIUM)
    print(f"  asked for 2024 from a series ending 2019 -> used "
          f"{out.source_year}, method {out.vintage['method']!r}")
    print(f"  true 2024 share {s[2024][0] / sum(s[2024]) * 100:.1f} % · "
          f"returned {out.w[0] * 100:.1f} %")
    check("the nearest year is used, not a fitted trend",
          out.vintage["method"] == "nearest_year" and out.source_year == 2019)
    check("and source_year keeps the real year so the vintage check still fires",
          out.vintage_gap(2024) == -5, f"gap {out.vintage_gap(2024)}")

    print("\n" + "=" * 72)
    print("4. A SHARE OF SOMETHING THAT CHANGES SIGN IS NOT A SHARE")
    print("=" * 72)
    ebe = series("Excedente bruto de explotación")
    print(f"  EEE 2020, gross operating surplus, thousand EUR: "
          f"55 = {ebe[2020][0]:,.0f}, 56 = {ebe[2020][1]:,.0f}")
    for label, vals in (("the real 2020 pair (sums negative)", ebe[2020]),
                        ("signs flipped (sums POSITIVE, one part negative)",
                         [-ebe[2020][0], -ebe[2020][1]])):
        try:
            AllocationKey(key_id="k", applies_to="output",
                          new_sector_codes=CODES, raw_values=list(vals),
                          source="INE EEE", source_year=2020,
                          strength=ProxyStrength.MEDIUM)
            check(f"refused: {label}", False, "it was ACCEPTED")
        except ValueError as exc:
            check(f"refused: {label}", True, str(exc).split(". ")[0][-72:])
    try:
        key_from_series("k", "output", CODES, ebe, 2020, "INE EEE",
                        ProxyStrength.MEDIUM)
        check("a series containing such a year is refused too", False,
              "it was ACCEPTED")
    except ValueError:
        check("a series containing such a year is refused too", True)

    print("\n" + "=" * 72)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
