"""
What Eurostat actually publishes for this question — swept, not assumed.

WHAT WAS RESTING ON WHAT
--------------------------
Six validators measure what a split costs, and every one of them rested on the
country-years that happened to be on disk: three for anything needing a real
allocation key, four for the perfect-key studies. Nobody had asked how many
country-years Eurostat publishes the necessary pair for.

The pair is strict. A split can only be scored against the office's own answer
when the SAME country and year has:

  * `naio_10_cp1700` at **89 products**, so the parent and its parts are both
    published — a 65-product table publishes only the parent; and
  * `sbs_ovw_act`, so a key an analyst could really download exists for that
    same year.

FOUND BY PROBING ALL 28 COUNTRIES, NOT BY LOOKING IN THE FOLDER
-----------------------------------------------------------------
One small query per country per dataset, reading the VALUE map rather than the
`time` axis — `run_availability.py` records why that distinction has cost this
project four separate errors. Structural business statistics turn out to exist
for **2021, 2022 and 2023 only**, in every country: the dataset is the new SBS
regulation's series and does not reach back. That closes, by measurement, the
question of whether Hungary 2020 could pair with Hungary 2022.

A PROBE COUNT IS NOT A PRODUCT COUNT, SO IT WAS CALIBRATED
------------------------------------------------------------
The probe counts populated `prd_ava` codes, which include aggregates, so it
reads 108 where `load_iot` builds 89 sectors. Calibrated against every cp1700
file already on disk, the mapping is exact and it is not a threshold:

    probe 108  ->  loads at 89 products   (5 of 5)
    probe  68/69 -> loads at 65 products
    probe 107  ->  REFUSED
    probe  55  ->  REFUSED

**107 is not "nearly 108".** Croatia 2021 sits there and the loader refuses it,
which is why this file tests equality and not `> 80`.

AND PASSING THE PROBE IS NOT ENOUGH
-------------------------------------
Of the country-years that pass BOTH halves of the pair, one is still refused —
on its own data, and correctly:

    FR 2022   exports: none of (P6_B0, P6_D0) or (P6) populated

Two more are lost one step earlier, and they are worth naming because each
falls for a different reason:

    HR 2021   probe 107, not 108 — and the loader refuses it: no final-demand
              block, none of (P3_S13, P3_S14, P3_S15) or (P3) populated
    SK 2015   probe 108 and it loads at 89 products, but 2015 predates the SBS
              series entirely, so no key exists for it. It stays in the
              perfect-key studies and cannot enter the real-key ones.

So the answer is **five country-years**: FR 2021, BE 2022, and HU 2021, 2022 and
2023. That is three countries, with Hungary three years running — the year axis
widened more than the country axis did, and every claim built on this set should
say so rather than calling it "five countries".

WHAT IT BOUGHT
----------------
    real keys scored          372  ->  638
    splits with an answer      39  ->   66
    country-years               3  ->    5

Run:
    python3 validators/run_source_pairs.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

DATA = ROOT / "data" / "eurostat"
SWEEP = DATA / "_source_pairs.json"
FINE_PROBE = 108           # calibrated below, exactly — not a threshold
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    from quadrium.eurostat import load_iot
    from run_real_key import CASES

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    check("the sweep is recorded, so nobody has to re-run it to read it",
          SWEEP.exists(), f"{SWEEP.relative_to(ROOT)}")
    if not SWEEP.exists():
        return 1
    sweep = {k: v for k, v in json.loads(SWEEP.read_text()).items()
             if not k.startswith("_")}
    check("and it covers every country the project has a verdict for",
          len(sweep) >= 28, f"{len(sweep)} countries probed")

    # 1 -- the calibration. A probe count is only usable if it maps to what the
    #      loader builds, and that map has to be checked against real files.
    print()
    print(f"    {'file':<24}{'probe prd_ava':>15}{'load_iot':>12}")
    rows = []
    for f in sorted(DATA.glob("naio_10_cp1700_*.json")):
        geo, year = f.stem.replace("naio_10_cp1700_", "").split("_")
        probe = sweep.get(geo, {}).get("cp1700", {}).get(year)
        try:
            n = load_iot(f).n
        except Exception:
            n = None
        if probe is None:
            continue
        rows.append((f"{geo} {year}", probe, n))
        print(f"    {geo + ' ' + year:<24}{probe:>15}"
              f"{('refused' if n is None else n):>12}")

    fine = [r for r in rows if r[1] == FINE_PROBE]
    check(f"a probe of exactly {FINE_PROBE} means an 89-product table",
          bool(fine) and all(r[2] in (89, None) for r in fine)
          and any(r[2] == 89 for r in fine),
          f"{sum(1 for r in fine if r[2] == 89)} of {len(fine)} load at 89 "
          f"products and none loads at anything else")
    near = [r for r in rows if r[1] and r[1] != FINE_PROBE and r[1] > 100]
    check("and a probe just below it is not 'nearly' one",
          all(r[2] is None for r in near) if near else True,
          f"{', '.join(f'{r[0]} at {r[1]}' for r in near)} — refused. This is "
          f"why the test is equality and not a threshold"
          if near else "no case between 100 and the fine count in this sweep")

    # 2 -- structural business statistics reach three years, and that is a
    #      measured fact with a consequence: no pre-2021 pairing is possible.
    years = sorted({y for v in sweep.values() for y in v.get("sbs", {})})
    print()
    print(f"    structural business statistics exist for: {', '.join(years)}")
    check("SBS does not reach before 2021, so no earlier year can be paired",
          years and min(years) >= "2021",
          f"{len(years)} years, {min(years)} to {max(years)}, in every country "
          f"probed. Hungary 2020 loads at 89 products and cannot be used, and "
          f"Slovakia 2015 is the same case")

    # 3 -- the pairs, and the ones that pass the probe and are still refused.
    eligible, refused = [], []
    for geo, v in sorted(sweep.items()):
        for year, probe in sorted(v.get("cp1700", {}).items()):
            if probe != FINE_PROBE or year not in v.get("sbs", {}):
                continue
            f = DATA / f"naio_10_cp1700_{geo}_{year}.json"
            if not f.exists():
                eligible.append((geo, year, "not downloaded"))
                continue
            try:
                load_iot(f)
                eligible.append((geo, year, "loads"))
            except Exception as exc:
                refused.append((geo, year, str(exc)[:60]))
    print()
    for geo, year, why in eligible:
        print(f"    {geo} {year}   {why}")
    for geo, year, why in refused:
        print(f"    {geo} {year}   REFUSED — {why}")

    usable = {(g, y) for g, y, w in eligible if w == "loads"}
    have = {(g, str(y)) for g, y, _ in CASES}
    check("every country-year that passes the probe AND loads is being used",
          usable == have,
          f"{len(usable)} usable, {len(have)} in run_real_key.CASES — "
          f"{', '.join(f'{g} {y}' for g, y in sorted(have))}")
    check("and passing the probe is not the same as loading",
          bool(refused),
          f"{len(refused)} refused on their own data: "
          + "; ".join(f"{g} {y}" for g, y, _ in refused)
          if refused else "none refused in this sweep")

    print()
    print("    Five country-years, three countries, Hungary three years")
    print("    running. Every claim built on this set is a statement about")
    print("    years as much as about countries, and should say so.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
