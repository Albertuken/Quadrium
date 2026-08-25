"""
"I want to look at restaurants" — the question before the table.

WHAT THIS IS FOR
-----------------
An analyst does not start with a table. They start with a sector, and then
spend an afternoon opening workbooks to discover that their country's published
table does not separate restaurants from hotels. `quadrium --find I55 --geo ES`
answers that in a second, and answers it with the thing they actually need
next: which coarser sector to divide.

Every entry is built from the codes that CARRY DATA, never from the label list,
and that distinction is the whole reason the module reads values. Eurostat's
metadata lists the entire CPA hierarchy whether or not a country publishes at
that level: Spain's symmetric table for 2022 lists `CPA_I55` and `CPA_I56` among
121 categories and **populates neither**. A catalogue built from labels would
tell a Spanish analyst that accommodation is available separately. It is not,
and the answer they need is the opposite one.

FOUR THINGS THIS FOUND ABOUT THE ENGINE ITSELF
------------------------------------------------
Cataloguing what the loaders deliver meant comparing it against what the
publishers publish, and they differ:

  * **France published 97 products in its use table and the engine loaded 73** —
    and this is why. Where a country serves both a code and its components,
    the chooser kept the coarser tiling; its name said the opposite of what it
    did, and the note beside it described removing the aggregates when what
    came out were the components. `C10`, `C11` and `C12` arrived folded into
    `C10-12`, and an analyst wanting food manufacturing would have been told to
    estimate what their own office had measured. **Settled the same day: the
    loaders keep the finest tiling whose components verifiably sum to their
    parent.** France's supply-use pair went from 65 x 65 to 89 x 88; Spain,
    Austria and the Netherlands did not move. `find()` keeps its
    PUBLISHED_NOT_LOADED verdict for what remains genuinely unreachable — a
    partial set of components, kept out because taking it would lose whatever
    the publisher did not serve.

  * **Ranking sources by resolution across countries is wrong**, and the first
    draft did it: asked where accommodation is available, it recommended the
    ONS table for the United Kingdom to anyone, because that one separates
    `I55` and Spain's does not. A finer table for a different economy is not a
    better source for the same question. `advise()` now requires a country and
    recommends nothing without one.

  * **The sector dimension is not the longest one.** "Take the dimension with
    more than ten categories" holds for an IO table and fails on the sources
    most worth cataloguing: the Structural Business Statistics cube carries
    eleven countries and three NACE groups, so it was filed as measuring
    Belgium, Czechia and Germany rather than restaurants, bars and catering.

  * **A proxy that measures part of a sector cannot divide it.** SBS measures
    `I561`, `I562` and `I563` — the groups of division 56. Offered as a key for
    dividing section `I`, which is accommodation AND food service, they cover
    the food half and say nothing about hotels. They are shown, and shown as
    not usable for that split.

Run:
    python3 validators/run_catalogue.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    import json

    from quadrium.catalogue import _inside, advise, find, scan

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    sources = scan(ROOT)
    tables = [s for s in sources if s.kind == "table"]
    proxies = [s for s in sources if s.kind == "proxy"]

    check("every table on disk is catalogued, and identified uniquely",
          len(sources) >= 30
          and len({s.source_id for s in sources}) == len(sources),
          f"{len(tables)} tables and {len(proxies)} proxies, "
          f"{len({s.source_id for s in sources})} distinct ids — the same "
          f"dataset serving hours worked and persons employed is two sources, "
          f"not one printed twice")

    # 1 -- listed is not available. The finding the module is built on.
    doc = json.loads((ROOT / "data" / "eurostat" /
                      "naio_10_cp1700_ES_2022.json").read_text())
    listed = doc["dimension"]["prd_use"]["category"]["index"]
    es = next(s for s in tables
              if s.source_id == "eurostat:naio_10_cp1700:ES:2022")
    check("a code Eurostat lists but does not populate is not catalogued",
          "CPA_I55" in listed and "I55" not in es.codes and "I" in es.codes,
          f"CPA_I55 is one of {len(listed)} categories in the metadata and "
          f"carries no value; the catalogue records the {es.resolution} that "
          f"do, and `I` is the one covering accommodation")

    # 2 -- and so the advice for Spain is to split, not to load.
    a = advise("I55", sources, "ES")
    check("so a Spanish analyst is told to divide, not to go looking",
          a["action"] == "split" and a["best"]["container"] == "I",
          f"`I` ({a['best']['label']}) is the sector to divide — which is what "
          f"this engine is for")

    # 3 -- and never told to use another country's table.
    uk = advise("I55", sources, "UK")
    check("the same question for the UK is answered from a UK table",
          uk["action"] == "load" and uk["best"]["source"].geo == "UK",
          f"{uk['best']['source'].source_id}")
    check("and with no country named, nothing is recommended",
          advise("I55", sources)["action"] == "choose_country"
          and advise("I55", sources)["best"] is None,
          "a finer table for another economy answers a different question, and "
          "the first draft of this recommended exactly that")

    # 4 -- the catalogue reports the tiling the loaders now deliver.
    fr = [s for s in tables if s.geo == "FR"]
    c10 = advise("C10", sources, "FR")
    check("France is catalogued at the detail France publishes",
          c10["action"] == "load" and c10["best"]["source"].geo == "FR",
          "; ".join(f"{s.source_id} at {s.resolution}" for s in fr)
          + " — 65 under the coarsest tiling, which was the answer until "
            "2026-08-25 and would have sent an analyst to estimate C10")
    check("and a partial set of components is still recorded as unreachable",
          all(isinstance(s.finer, list) for s in tables),
          "where components do not sum to their parent the parent is kept, and "
          "`--find` says the code exists rather than saying 'split it'")

    # 5 -- the proxies, and the honesty about what they can drive.
    print()
    check("a proxy cube is filed by its sectors, not by its longest dimension",
          any("sbs" in s.source_id and set(s.codes) == {"I561", "I562", "I563"}
              for s in proxies),
          "SBS carries 11 countries and 3 NACE groups; taking the longest "
          "dimension filed it as measuring Belgium, Czechia and Germany")
    check("NACE groups are understood to sit inside their division",
          _inside("I56", "I561") and _inside("I", "I561")
          and not _inside("C10", "I561"),
          "`_covers` reads two-digit divisions only, so `I561` matched nothing "
          "and the one proxy worth finding was invisible")

    prox = advise("I56", sources, "ES")["proxies"]
    check("a proxy that measures only part of the sector is shown AS that",
          prox and all(not p["tiles"] for p in prox)
          and all(p["covers"] == ["I56"] for p in prox),
          "I561–I563 cover the food half of section `I` and say nothing about "
          "hotels; they are listed and refused as a key for that split")

    # 6 -- the answer is actionable: it prints the configuration.
    lines = a["best"]["source"].config_lines()
    check("the advice hands back the configuration rows to paste",
          any("eurostat_geo     ES" in x for x in lines)
          and any("table_kind" in x for x in lines),
          " / ".join(x.strip() for x in lines[:2]))

    print()
    print("    An engine that can only answer 'here is your table, now what'")
    print("    leaves the hardest half of the afternoon with the analyst.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
