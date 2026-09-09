"""
A satellite account written to a file and read back — which it was not, for a day.

WHAT THIS FOUND
-----------------
Satellite accounts shipped on 2026-09-08. On 2026-09-09, asked whether they
survive the chain a user actually walks — split, export, read the result back to
split something else — the answer was no. An employment account came out of a
disaggregation carrying **368,612 persons for subsector 36A** and came back from
its own file **gone**. No error and no warning: `_write_interchange_sheets` had
no column for it and the loader had nothing to look for.

**That is the identical failure v1.86 recorded for `--regionalise`**, where a
table written with 4,096 cells labelled ESTIMATED came back with all of them
OBSERVED, and `IOTable.provenance`'s docstring calls it the one thing an audit
trail may not do. Made again, by the next feature, one day later.

The lesson is not "remember the round trip". It is that a feature and its round
trip belong in the same commit, because the gap between them is exactly one day
long and nobody is watching it.

WHAT IS CHECKED, AND WHY THE ORIGIN MATTERS MORE THAN THE NUMBER
------------------------------------------------------------------
A value the engine estimated by dividing a parent, read back as `observed`, is
worse than a value that is missing — missing is visible. So the `Satellites`
sheet carries `origin` beside every figure, and this checks that a split's
estimates come back estimates and an untouched sector comes back observed.

The type II closure travels too, in `metadata`, for a smaller but similar
reason: a table exported and read back would otherwise become type I silently,
showing multipliers a third smaller with nothing saying why.

**Exactness is to machine precision, not to the bit.** Excel serialises a float
as decimal text, so 1,755,572.4000000001 returns as 1,755,572.4 — a relative
difference of 2.1e-16, which is the file format and not the engine. The check is
written at that tolerance and says so, rather than at zero where it would fail
for a reason that is nobody's defect.
"""
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "examples"))

FAIL = []
NOTHING_CHECKED = 3


def check(label, ok, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    if detail:
        print(f"         {detail}")
    if not ok:
        FAIL.append(label)


def main():
    ine = ROOT / "data" / "ine" / "cne_tio_22.xlsx"
    if not ine.exists():
        print(f"    -- {ine.name} is absent.")
        print("\n" + "=" * 78)
        print("Nothing checked here.")
        return NOTHING_CHECKED

    import es_hosteleria as ex
    from quadrium.export import write_interchange_xlsx
    from quadrium.io_loader import LoaderError, load_ine_tio, load_io_table
    from quadrium.models import Satellite, Scenario, SplitSpec
    from quadrium.scenarios import run_scenario

    t = load_ine_tio(ine, "interior", "residual_column")
    t.satellites = {"employment": Satellite(
        name="employment", unit="persons",
        values=[float(x) * 12.0 for x in t.X],
        source="synthetic, to exercise the round trip", source_year=2022)}
    t.type_ii = {"income_rows": ["Remuneración de los asalariados"],
                 "household": "Gasto en consumo final de los hogares"}

    res = run_scenario(
        t, [SplitSpec("36", ex.NEW, ex.LBL,
                      keys_by_block={"output": "k_tod_produccion"})],
        Scenario(scenario_id="S1", label="size only", description="base"),
        ex.build_keys())

    with tempfile.TemporaryDirectory() as td:
        path = write_interchange_xlsx(res.table, Path(td) / "t.xlsx",
                                      derived_from="round trip check")
        if path is None:
            print("    -- openpyxl is absent, so nothing can be written.")
            return NOTHING_CHECKED
        back = load_io_table(path)

        # 1 -- it comes back at all. This is what failed.
        check("the account survives being written and read",
              "employment" in back.satellites,
              "on 2026-09-08 it did not, and nothing said so")

        a = np.array(res.table.satellites["employment"].values)
        b = np.array(back.satellites["employment"].values)
        rel = (np.abs(a - b) / np.where(a == 0, 1.0, np.abs(a))).max()
        check("and its values to machine precision",
              rel < 1e-12,
              f"worst relative difference {rel:.2e} — Excel writes a float as "
              f"decimal text, so the last bit moves and that is the format")
        check("and its unit and source, which the numbers are meaningless "
              "without",
              back.satellites["employment"].unit == "persons"
              and "synthetic" in back.satellites["employment"].source)

        # 2 -- the origin, which matters more than the number.
        i = back.index_of("36A")
        check("a value the split ESTIMATED comes back estimated",
              back.satellites["employment"].origin[i] == "estimated",
              f"{back.satellites['employment'].values[i]:,.0f} persons, and "
              f"an estimate read back as an observation is worse than one "
              f"that is missing, because missing is visible")
        untouched = next(k for k, c in enumerate(back.sector_codes)
                         if c not in ("36A", "36B"))
        check("and a sector the split never touched comes back observed",
              back.satellites["employment"].origin[untouched] == "observed",
              "labelling everything estimated would be the same failure in "
              "the other direction")

        # 3 -- the type II closure travels too.
        check("the type II closure survives the file",
              back.type_ii.get("household") ==
              "Gasto en consumo final de los hogares"
              and back.type_ii.get("income_rows") ==
              ["Remuneración de los asalariados"],
              "without it the table comes back type I, showing multipliers a "
              "third smaller with nothing saying why")

        # 4 -- a partial account is refused rather than filled with zeros.
        import openpyxl
        wb = openpyxl.load_workbook(path)
        ws = next(s for s in wb.worksheets if s.title.lower() == "satellites")
        ws.delete_rows(2)
        broken = Path(td) / "broken.xlsx"
        wb.save(broken)
        try:
            load_io_table(broken)
            check("an account missing a sector is refused on the way in",
                  False, "it loaded")
        except LoaderError as exc:
            check("an account missing a sector is refused on the way in",
                  "partial account" in str(exc), str(exc)[:100])

    # 5 -- a table with no accounts writes no sheet and reads back clean.
    plain = load_ine_tio(ine, "interior", "residual_column")
    with tempfile.TemporaryDirectory() as td:
        p2 = write_interchange_xlsx(plain, Path(td) / "p.xlsx",
                                    derived_from="no accounts")
        import openpyxl
        names = [s.lower() for s in openpyxl.load_workbook(p2).sheetnames]
        check("a table with no accounts writes no Satellites sheet",
              "satellites" not in names,
              "an empty sheet is a claim that there is nothing to measure")
        check("and reads back with none, not with an empty one",
              load_io_table(p2).satellites == {})

    print()
    print("    A feature and its round trip belong in the same commit. The")
    print("    gap between them was one day, and one day was enough.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
