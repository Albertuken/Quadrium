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

WHAT IT SHOWS, WITH A CONTROL
-------------------------------
    geo    cp1700      cp1750      cp15        cp16        cp1610
    DE     none        none        2010-2022   2010-2022   none
    BE     none        2010-2022   2010-2022   2010-2022   2010-2022
    ES     1990-2023   -           1990-2024   1990-2024   populated

**Germany has no route to a symmetric table through Eurostat at all**: no
symmetric table, and no use at basic prices, so the pair it does publish cannot
be transformed either — the domestic/imported split would have to be assumed,
and this engine will not assume it. Saying that plainly is worth more than a
configuration that would have failed.

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
        skip("Germany has no route to a symmetric table",
             "DE has not been asked about in this checkout")
    else:
        d = json.loads(de.read_text())
        check("Germany has no route to a symmetric table through Eurostat",
              not d.get("product_by_product")
              and not d.get("industry_by_industry")
              and not d.get("use_basic")
              and d.get("supply"),
              f"supply and use for {d['supply'][0]}–{d['supply'][-1]} and "
              f"nothing else — no symmetric table, and no use at basic prices, "
              f"so the pair cannot be transformed either. The answer is that "
              f"there is no route, not that we failed to look")

    es = DATA / "_availability_ES.json"
    if es.exists():
        d = json.loads(es.read_text())
        check("and the control country has what Germany does not",
              bool(d.get("product_by_product")) and bool(d.get("use_basic")),
              "Spain carries the symmetric table and the basic-price use "
              "table; a probe that returned nothing everywhere would look the "
              "same as one that worked")

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
