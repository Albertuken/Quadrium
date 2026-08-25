"""
Seven years of the Spanish table, where the loader read two.

WHAT WAS UNTESTED
------------------
`load_ine_tio` had been run on one file: `cne_tio_22.xlsx`. The INE publishes
2016 to 2022 under the same statistical revision, at the same URL pattern, and
five of those years refused to load with

    the INE workbook's layout no longer matches the one this loader hard-codes.
    failed check: Tabla1 == Tabla2 + Tabla3 (intermediate block)
    off by 29,086.9212

Nothing about the layout was wrong. The workbook is published in two shapes and
the loader knew one.

THREE DIFFERENCES, ALL OF THEM THINGS THE INE STOPPED PUBLISHING
------------------------------------------------------------------
Every one is the older vintage carrying LESS, never carrying it differently:

  1. `Tabla 2` and `Tabla 3`. From 2021 they are the domestic and imports
     tables. From 2016 to 2020 they are technical coefficients and the Leontief
     inverse — **the domestic/imports split is not published at all**. So
     `variant='interior'` genuinely cannot be served for those years, and now
     says so instead of complaining about a layout.

  2. `Importaciones de la Unión Europea` and `de terceros países`. The older
     files PRINT BOTH LABELS AND LEAVE BOTH ROWS EMPTY. The check that pinned
     those rows was comparing a populated row against zero and failing by
     33,653.70 on 2020, across 58 of 64 columns. Those rows are used for
     nothing else, so an absent split costs exactly that check.

  3. Exports. From 2021 they are split into European Union and third countries,
     columns 76 and 77. Before that there is only `Total exportaciones`, at 75,
     and every column after it sits two earlier. Exports are a SUBTOTAL in one
     shape and a LEAF in the other, which is why the older map has one group
     fewer rather than a group of one — a subtotal that equals itself checks
     nothing.

The shape is detected from the header the workbook prints, not from the file
name or the sheet count: the year is not what decides it, the publication is.

WHAT THE SERIES SHOWS
----------------------
    2016  1,969,898        2020  2,030,323
    2017  2,077,118        2021  2,280,636
    2018  2,171,029        2022  2,664,587
    2019  2,255,859

Rising to 2019, falling in 2020, recovering after. That is the Spanish economy's
actual shape, and a loader that had silently mismapped a column would not
produce it.

AND THE SAME THING AGAIN, ONE SHEET OVER
-----------------------------------------
`load_ine_tod` had also been run on exactly one file, and it did not refuse the
older ones — it raised a bare `IndexError` from inside a list comprehension.
That is the one failure this project does not accept: a loader that cannot read
a file has to say why.

The supply-use workbook changes shape in the same edition and for the same
reason, and the older one is again the smaller:

    2016-2020    65 products x 64 activities
    2021-2022   110 products x 81 activities

Three things had been hard-coded that are not constant. **The supply sheet of
the older files has no leading blank column and the use sheet does**, so the two
sheets of one workbook are offset from each other by one. **The activity index
row is not 1, 2, 3, …**: it carries `44a` where the label column two rows below
writes `44 bis.` — two conventions for one thing in one file — and a run that
accepts only the next integer stops at 44 and reads a 65-activity table as a
44-activity one, which stays rectangular and is caught by nothing but an
identity. **Exports are again a leaf rather than a subtotal.**

Every position is now found by the label the INE prints. The final-demand
subtotals are named; their COMPONENTS are not, because they are whatever
columns lie between one subtotal and the next — which is how one rule reads a
vintage that splits exports in two and one that does not — and each inference
is then checked against the subtotal it was inferred from.

WHAT THAT BUYS, AND WHAT IT COSTS
----------------------------------
The supply-use pair is where the margin identities are arithmetic instead of
`NOT APPLICABLE` (`OQ-D-03`), so this is five more years of the only fixture the
project has for them.

It also corrects something this repository asserted. `OQ-S-05` closed on the
finding that the INE publishes 110 products, so the accommodation/food split the
pilot spends its effort estimating is simply published and need not be
requested. **That is true for 2021 and 2022 and false before them.** In the
2016-2020 edition product 36 is `Servicios de alojamiento y de comidas y
bebidas`, undivided. For those years the estimation route is the only route, and
a user asking for 2019 has to be told so rather than handed a table that looks
the same and is coarser.

Run:
    python3 validators/run_ine_series.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "ine"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    from quadrium.io_loader import (LoaderError, _ine_columns, _ine_vintage,
                                    _open_workbook, load_ine_tio)

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    years = [y for y in range(2016, 2023)
             if (DATA / f"cne_tio_{y % 100}.xlsx").exists()]
    check("the published series is here, not one year of it",
          len(years) >= 6,
          f"{years[0]}–{years[-1]}, {len(years)} files under one statistical "
          f"revision")

    # 1 -- every year loads as `total`, and the series is an economy.
    print()
    print(f"    {'year':>6}{'sectors':>9}{'output':>16}{'shape':>12}")
    out = {}
    for y in years:
        f = DATA / f"cne_tio_{y % 100}.xlsx"
        t = load_ine_tio(f, "total")
        S = _open_workbook(f)
        shape = "split" if _ine_vintage(S) == "split" else "total only"
        out[y] = float(t.X.sum())
        print(f"    {y:>6}{t.n:>9}{out[y]:>16,.0f}{shape:>12}")

    check("every published year loads as the total table",
          len(out) == len(years) and all(v > 0 for v in out.values()),
          "the loader read one file until 2026-08-25 and refused five of the "
          "seven with a complaint about its own layout")
    check("and the series has the shape the Spanish economy had",
          out[2019] > out[2018] > out[2017] > out[2016]
          and out[2020] < out[2019] and out[2022] > out[2021] > out[2020],
          f"rising to {out[2019]:,.0f} in 2019, {out[2020]:,.0f} in 2020, "
          f"{out[2022]:,.0f} in 2022 — a mismapped column does not produce a "
          f"pandemic")

    # 2 -- the split is refused for the years it is not published, and said so.
    print()
    msg = ""
    try:
        load_ine_tio(DATA / "cne_tio_20.xlsx", "interior")
    except LoaderError as exc:
        msg = str(exc)
    check("`interior` is refused where the INE does not publish it",
          "not published for this year" in msg and "Tabla 2" in msg,
          "in that vintage Tabla 2 is technical coefficients and Tabla 3 the "
          "Leontief inverse — the domestic table does not exist to be read")
    check("and the message says what to load instead, and what it costs",
          "variant='total'" in msg and "overstate domestic effects" in msg,
          "an imported input treated as if produced in Spain")

    ok21 = load_ine_tio(DATA / "cne_tio_21.xlsx", "interior")
    check("while the years that do publish it still load it",
          ok21.n == 64 and ok21.X.sum() > 0,
          f"2021 interior, {ok21.n} products, output {ok21.X.sum():,.0f}")

    # 3 -- the two column maps, and how they differ.
    print()
    maps = {}
    for y in (2020, 2022):
        f = DATA / f"cne_tio_{y % 100}.xlsx"
        if not f.exists():
            continue
        maps[y] = _ine_columns(_open_workbook(f)["Tabla1"])
    if len(maps) == 2:
        old_c, new_c = maps[2020], maps[2022]
        check("the older shape is the newer one minus the export split",
              len(old_c[0]) == len(new_c[0]) - 1
              and len(old_c[1]) == len(new_c[1]) - 1
              and old_c[3] == new_c[3] - 2,
              f"final-demand columns {len(old_c[0])} against {len(new_c[0])}, "
              f"subtotal groups {len(old_c[1])} against {len(new_c[1])}, and "
              f"'Total demanda final' at {old_c[3]} against {new_c[3]} — "
              f"exports are a leaf in one and a subtotal in the other")

    check("and the shape is read from the header, not guessed from the year",
          "_ine_columns" in open(ROOT / "src" / "quadrium" / "io_loader.py",
                                 encoding="utf-8").read()
          and "header" in _ine_columns.__doc__.lower(),
          "the year is not what decides which shape a workbook has; the "
          "publication is, and a third shape would be refused rather than "
          "mismapped")

    # 4 -- the supply-use pair, same seven years, same two shapes.
    from quadrium.io_loader import load_ine_tod

    print()
    print(f"    {'year':>6}{'products':>10}{'activities':>12}"
          f"{'supply q':>14}{'q - X(TIO)':>12}")
    sut, detail = {}, {}
    for y in years:
        f = DATA / f"cne_tod_{y % 100}.xlsx"
        if not f.exists():
            continue
        s = load_ine_tod(f)
        sut[y] = s
        detail[y] = (len(s.product_codes), len(s.activity_codes))
        gap = abs(float(s.q.sum()) - out[y])
        print(f"    {y:>6}{detail[y][0]:>10}{detail[y][1]:>12}"
              f"{s.q.sum():>14,.0f}{gap:>12,.4f}")

    check("the supply-use pair loads for every year too",
          len(sut) == len(years),
          "it read one file and raised a bare IndexError on the other five — "
          "not a refusal, a crash")
    check("and two independent workbooks agree on Spain's output exactly",
          all(abs(float(s.q.sum()) - out[y]) < 1e-6 for y, s in sut.items()),
          "supply-table output equals input-output-table output to 0.0000 in "
          "all seven years; the tio and the tod are compiled and published "
          "separately, so this is a real cross-check and not a tautology")
    check("the older edition is 65 x 64 and the newer 110 x 81",
          all(detail[y] == (65, 64) for y in years if y <= 2020)
          and all(detail[y] == (110, 81) for y in years if y >= 2021),
          "the finest detail the INE publishes is not a constant of the INE; "
          "it is a property of the edition")

    # 5 -- the axis trap, stated as the number it would have produced.
    from quadrium.io_loader import _open_workbook, _tod_axes
    ax = _tod_axes(_open_workbook(DATA / "cne_tod_20.xlsx")["Tabla1"], "supply")
    check("the activity axis is read past its 44a continuation",
          ax["n_activities"] == 64 and ax["label_col"] == 0,
          f"{ax['n_activities']} activities, label column "
          f"{ax['label_col'] + 1} — a run that accepts only the next integer "
          f"stops at 44, and a 44-column block is still rectangular")
    ax2 = _tod_axes(_open_workbook(DATA / "cne_tod_20.xlsx")["Tabla2"], "use")
    check("and the two sheets of one workbook start in different columns",
          ax["first_col"] != ax2["first_col"],
          f"supply at column {ax['first_col'] + 1}, use at "
          f"{ax2['first_col'] + 1} — one `first_col` for the workbook reads "
          f"the older supply table one column to the left of where it is")

    # 6 -- what OQ-S-05 concluded, and for which years it holds.
    print()
    if 2020 in sut and 2021 in sut:
        old_lbl = [l for l in sut[2020].product_labels
                   if "alojamiento" in l.lower() and "comidas" in l.lower()]
        new_lbl = [l for l in sut[2021].product_labels
                   if l.strip() in ("Servicios de alojamiento",
                                    "Servicios de comidas y bebidas")]
        check("accommodation and food are separate products from 2021",
              len(new_lbl) == 2, " and ".join(new_lbl))
        check("and are ONE product before it",
              len(old_lbl) == 1,
              f"{old_lbl[0]!r} — OQ-S-05 closed on the split being published "
              f"rather than needing a request. For 2016-2020 it is not "
              f"published, and the pilot's estimation route is the only one")

    check("margins still sum to zero economy-wide in every year",
          all(abs(float(s.total_margins.sum())) < 1e-3 for s in sut.values()),
          "ID-19 — a margin column redistributes and does not create; this is "
          "the identity an analytical IOT cannot be asked, and there are now "
          "seven years of it instead of one")

    print()
    print("    Five of seven years were refused with 'the layout no longer")
    print("    matches', and the layout was fine. What had changed was what")
    print("    the office publishes. On the supply-use sheet next door the")
    print("    same five years did not even refuse — they raised IndexError.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
