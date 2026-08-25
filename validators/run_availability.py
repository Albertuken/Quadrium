"""
What exists that is not on disk — and the trap it fell into, for the third time.

WHAT WAS INCOMPLETE
--------------------
`scan()` answers "what can I load", and on a fresh install the answer is
"whatever shipped". So the first question a new user asks — about their own
country — got `no table for DE is on disk`, which is true and useless. What
they need next is which years exist, and that is one small query per dataset.

THE TRAP, IN A THIRD PLACE
---------------------------
The obvious source is the response's `time` dimension. It lists the years the
DATASET spans, not the years a country populates. Read directly it reported 35
years to 2024 for Germany, so `--find` printed a configuration naming 2024 —
and that configuration fails, because Eurostat answers 200 with an empty result
for a year a country does not publish. **Advice you have not run is not
advice.**

The years now come from the VALUE map, exactly as the product codes do. It is
the same trap as `CPA_I55` and `CPA_I56` being listed in Spain's symmetric table
and populated in neither, met for the third time in this module.

AND THE SAME TRAP A FOURTH TIME, IN THE FIX ITSELF
----------------------------------------------------
The filter that keeps each probe small has to name a category that EXISTS on
the axis it names. For `naio_10_cp1700` this asked `prd_use=CPA_TOTAL` — but
`CPA_TOTAL` is the total on the AVAILABLE axis, and the use axis's total is
`TU`. `load_iot` reads that same file with `prd_use="TU"`, three files away.

Eurostat answers 200 with an empty result for a category that does not exist,
exactly as it does for a year a country does not publish. So the probe reported
that NO country publishes a symmetric product-by-product table, and this file
asserted, in those words, that **Germany has no route to a symmetric table
through Eurostat at all**. Germany publishes THIRTEEN YEARS of one, and the
2022 file loads here in 65 sectors.

The claim was wrong and it was committed. An empty answer meaning "you asked
the wrong question" is indistinguishable from one meaning "there is nothing
there", and what separates them is a control that is known to be populated.

WHAT IT SHOWS ONCE THE PROBE ASKS PROPERLY
--------------------------------------------
Twenty-eight countries, every one of which publishes supply and use. What
differs is the symmetric table and the basic-price use table:

    DE     pxp 13 years   ixi none      cp1610 NONE   -> pair not transformable
    ES     pxp  9 years   ixi none      cp1610 13
    DK     pxp none       ixi 18 years  cp1610 18
    BG     pxp  1 year    ixi none      cp1610 1

Germany is still the one country whose supply-use pair cannot be transformed —
it publishes no use table at basic prices, so the domestic/imported split would
have to be assumed — but its symmetric table is reachable, and saying otherwise
was a bug here.

Run:
    python3 validators/run_availability.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "eurostat"
FAIL: list[str] = []
SKIPPED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def skip(name: str, why: str) -> None:
    print(f"  --   {name} — SKIPPED: {why}")
    SKIPPED.append(name)


def main() -> int:
    from quadrium.catalogue import _YEAR_PROBE, available_years

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    check("every dataset the probe asks about has a filter of its own",
          set(_YEAR_PROBE) == {"product_by_product", "industry_by_industry",
                               "supply", "use_purchasers", "use_basic"}
          and all(len(v) == 2 for v in _YEAR_PROBE.values()),
          "cp1700 indexes `prd_use`, cp15 `prd_amo`, the use tables `prd_ava` "
          "and cp1750 industries — asking for one total keeps each response "
          "near 24 KB instead of megabytes")

    # The cached answers, if a session has taken them. This validator must run
    # offline, so a missing cache is a skip and not a failure.
    cached = sorted(DATA.glob("_availability_*.json"))
    if not cached:
        skip("the cached availability answers are read back",
             "no `_availability_*.json` beside the data; run "
             "`quadrium --find CODE --geo XX` once with a network")
    else:
        for f in cached:
            geo = f.stem.split("_")[-1]
            d = json.loads(f.read_text())
            years = {k: v for k, v in d.items() if not k.startswith("_")}
            check(f"{geo}'s availability is cached with the date it was taken",
                  "_taken" in d and all(isinstance(v, list) and v
                                        for v in years.values()),
                  ", ".join(f"{k} {v[0]}–{v[-1]}"
                            for k, v in sorted(years.items())) or "nothing")

    de = DATA / "_availability_DE.json"
    if not de.exists():
        skip("Germany publishes a symmetric table",
             "DE has not been asked about in this checkout")
    else:
        d = json.loads(de.read_text())
        check("Germany publishes a symmetric table, and the probe sees it",
              bool(d.get("product_by_product")) and not d.get("use_basic"),
              f"product-by-product for "
              f"{d['product_by_product'][0]}–{d['product_by_product'][-1]}, "
              f"and no use at basic prices — the SYMMETRIC table is reachable "
              f"and the PAIR is not transformable. This file asserted the "
              f"opposite until 2026-08-25, because the probe named "
              f"`prd_use=CPA_TOTAL` on an axis whose total is `TU`")

    es = DATA / "_availability_ES.json"
    if es.exists():
        d = json.loads(es.read_text())
        check("and the control country has what Germany does not",
              bool(d.get("product_by_product")) and bool(d.get("use_basic")),
              "Spain carries the symmetric table and the basic-price use "
              "table; a probe that returned nothing everywhere would look the "
              "same as one that worked")

    # ---- and what happened when each was loaded --------------------------
    #
    # "Eurostat carries this, which is not a promise it loads" was a fair
    # caveat while nothing better was known. After the sweep it was a hedge:
    # every country's newest table had been loaded by both routes and the
    # result thrown away. `_verdicts.json` keeps it, and `--find` names it.
    print()
    v = DATA / "_verdicts.json"
    if not v.exists():
        skip("the sweep's verdicts are recorded and readable",
             "`_verdicts.json` is not in this checkout; "
             "`library/tools/record_verdicts.py` writes it")
    else:
        d = json.loads(v.read_text())
        rows = {k: r for k, r in d.items() if not k.startswith("_")}
        check("every country the sweep touched has a verdict with its year",
              len(rows) >= 25 and all(
                  e.get("year") or e.get("verdict") == "not published"
                  for r in rows.values() for e in r.values()),
              f"{len(rows)} countries; each entry names the year it was "
              f"checked, because a verdict is evidence about that year and "
              f"not a prediction about the others")

        loads = sum(1 for r in rows.values()
                    if r.get("symmetric", {}).get("verdict") == "loads")
        pairs = sum(1 for r in rows.values()
                    if r.get("pair", {}).get("verdict") == "loads")
        check("and the counts match what the sweep measured",
              loads >= 17 and pairs >= 12,
              f"{loads} symmetric tables and {pairs} pairs load — the same "
              f"figures `run_eu_sweep.py` reports, from the same run")

        ie = rows.get("IE", {}).get("symmetric", {})
        se = rows.get("SE", {}).get("symmetric", {})
        de = rows.get("DE", {}).get("pair", {})
        check("a refusal is recorded with a cause a reader can act on",
              ie.get("cause") == "incomplete"
              and se.get("cause") == "files disagree"
              and de.get("verdict") == "not published",
              f"IE {ie.get('year')} incomplete; SE {se.get('year')} its own "
              f"figures disagree; DE has no basic-price use table at all — "
              f"three different answers where the adviser used to give one "
              f"warning")

    print()
    print("    The `time` dimension of a response is a fact about the dataset.")
    print("    Which years a country populates is a fact about the country,")
    print("    and only the value map knows it.")

    print("\n" + "=" * 78)
    if SKIPPED:
        print(f"{len(SKIPPED)} check(s) SKIPPED for want of a cached answer: "
              f"{', '.join(SKIPPED)}")
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
