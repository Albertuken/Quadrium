"""
The spread across keys reaches the reader, by both doors, and never as a ranking.

WHAT THIS IS FOR
-----------------
`OQ-E-03`. `key_alternatives()` computes what the split would have been under
each registered key; this checks that the number arrives where a user meets it
— in `report.md` — and that it arrives with the three things that keep it from
being read as the opposite of what it says.

THE THREE, AND EACH ONE IS A MISTAKE THAT WAS NEARLY MADE
-----------------------------------------------------------
**Levels before multipliers.** The first version of the feature reported the
multiplier alone and returned a spread of 0.00 % across keys spanning a factor
of five in subsector size. `run_key_sensitivity.py` had already established why
— the weight cancels in `a_ij = Z_ij / X_j` — and had warned in terms that a
study of this kind "would have reported a spread of zero and been mistaken for
a finding about robustness". Printed first, that zero is a robustness claim.

**The zero is labelled.** Not left for the reader to derive from a sentence in
the guide. It says: read this as *the choice does not touch that number*, never
as *my sources agree*.

**No ranking.** The report already removed one ranking for cause — `OQ-S-06`,
where the key that disagreed most turned out to be the closest to the truth.
This section carries the second measurement of the same lesson: the key with
the best conceptual match is +40.8 % out and the loosest match is the closest.

AND BOTH DOORS
---------------
`docs/GUIDE.md` opens by promising no Python is needed. A feature reachable only
from the command line breaks that promise, which is what regionalisation was
doing until v1.86. So `key_alternatives  yes` in the `project` sheet and
`--key-alternatives` must both work, and this checks the workbook door — the
one a user actually takes.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "examples"))

FAIL = []


def check(label, ok, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    if detail:
        print(f"         {detail}")
    if not ok:
        FAIL.append(label)


def main():
    table_path = ROOT / "data" / "ine" / "cne_tio_22.xlsx"
    if not table_path.exists():
        print("  the Spanish table is absent; nothing to render.")
        return 0

    import es_hosteleria as ex
    from quadrium.config import _yes, write_template
    from quadrium.io_loader import load_ine_tio
    from quadrium.models import Scenario, SplitSpec
    from quadrium.project import IOProject
    from quadrium.reporting import build_report

    table = load_ine_tio(table_path, variant="interior",
                         unbalanced="residual_column")
    keys = ex.build_keys()
    va_rows = {table.VA_labels[0]: "k_compras",
               table.VA_labels[2]: "k_gastos_personal"}
    splits = [SplitSpec("36", ex.NEW, ex.LBL,
                        keys_by_block={"output": "k_tod_produccion"},
                        va_row_keys=va_rows,
                        va_residual_row=table.VA_labels[4])]

    def report(on):
        pr = IOProject(project_id="e03", table=table, splits=splits,
                       scenarios=[Scenario(scenario_id="S1", label="size only",
                                           description="base")],
                       keys=keys, ledger=ex.build_ledger())
        pr.run(key_alternatives=on)
        return build_report(pr.results, pr.meta, pr.ledger)

    HEAD = "### What the answer would have been under a different key"
    md = report(True)

    # 1 -- it is there, and it is absent when not asked for.
    check("the section reaches the report", HEAD in md)
    check("and is absent when the run did not ask for it",
          HEAD not in report(False),
          "a section that appears whatever was asked is not a switch")

    body = md[md.find(HEAD):]
    body = body[:body.find("\n### ", 10)] if "\n### " in body[10:] else body

    # 2 -- levels lead, and every key is named with its own strength.
    check("the table leads with levels, not multipliers",
          body.find("level") < body.find("multiplier"),
          "the multiplier is invariant to the key, so printing it first shows "
          "a column of zeros that reads as agreement between sources")
    for k in ("k_empleo", "k_ebe", "k_produccion", "k_empresas"):
        check(f"`{k}` is named in the table", f"`{k}`" in body)
    check("the weak key is marked weak where it is printed",
          "weak" in body, "k_empresas is the one, and it is the furthest out")

    # 3 -- the zero is explained rather than left to be read.
    check("the identical multipliers are labelled arithmetic",
          "arithmetic rather than agreement" in body)
    check("and the misreading is named explicitly",
          "never as *my sources agree*" in body,
          "the sentence that stops a zero being read as robustness")

    # 4 -- the refusal to rank, with its measured reason.
    check("the report refuses to say which key is right",
          "will not pretend otherwise" in body)
    check("and gives the measurement behind the refusal",
          "+40.8 %" in body and "-11.3 %" in body,
          "the conceptual favourite against the loosest match, on the one "
          "split where the INE publishes the answer")
    check("and asks the user to choose and record why",
          "assumption ledger" in body)

    # 5 -- ASKED FOR AND EMPTY. The one outcome that must be spoken.
    solo = IOProject(
        project_id="e03solo", table=table,
        splits=[SplitSpec("36", ex.NEW, ex.LBL,
                          keys_by_block={"output": "k_tod_produccion"})],
        scenarios=[Scenario(scenario_id="S1", label="size only",
                            description="base")],
        keys={"k_tod_produccion": keys["k_tod_produccion"]},
        ledger=ex.build_ledger())
    solo.run(key_alternatives=True)
    solo_md = build_report(solo.results, solo.meta, solo.ledger)
    solo_body = solo_md[solo_md.find(HEAD):]
    solo_body = solo_body[:solo_body.find("\n### ", 10)]
    check("with one key registered the section says there was nothing to "
          "compare against",
          "only one allocation key is registered" in solo_body,
          "it printed the heading and a paragraph and then stopped, which a "
          "reader takes for agreement or for a switch that did not work")
    check("and calls it an absent test rather than a clean result",
          "absent test" in solo_body)

    # 6 -- the key that cannot drive the split is named, not dropped.
    check("a key declared for one block is named, not silently omitted",
          "k_vab" in body,
          "a candidate that disappears looks like one never registered")

    # 7 -- the workbook door, which is the one the guide promises.
    with tempfile.TemporaryDirectory() as td:
        cfg = write_template(Path(td) / "t.xlsx")
        import openpyxl
        wb = openpyxl.load_workbook(cfg)
        text = " ".join(str(r[0]) for r in wb["project"].iter_rows(values_only=True)
                        if isinstance(r[0], str))
    check("the template tells the user the key exists",
          "key_alternatives" in text,
          "a switch nobody is told about is a switch nobody uses")
    check("and the spreadsheet's own spellings of yes are accepted",
          all(_yes(v) for v in ("yes", "YES", "true", "1", "si", "sí", True))
          and not any(_yes(v) for v in ("", None, "no", "false", 0)),
          "Excel returns a bool for some of these and text for others, and a "
          "Spanish workbook says si")

    print()
    print("    The number is useless in a JSON nobody opens. This checks it")
    print("    reaches the page, with the sentence that stops it being read")
    print("    backwards.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
