"""
The family is implemented, and every run says what it is known to get wrong.

THE DECISION THIS IMPLEMENTS
------------------------------
`OQ-R-01` measured that cross-hauling is 28.3 % of Catalonia's interregional
trade and that no member of the location quotient family is fitted to it, then
left one thing open that no measurement could settle: **implement the family
anyway and print the measured cost beside the result, or wait for a source that
handles cross-hauling directly.** The owner chose to implement, on 2026-09-01.

So `quadrium --regionalise` exists, and this file checks the part that makes the
choice defensible rather than merely convenient: **the cost is not optional**.
It is written into `report.md`, into `assumption_ledger.json`, and printed to
the terminal on every run, whether or not anybody asked. `CORE_036` p. 35 is the
argument — the responsibility for a table is the analyst's and there is no
refuge in mechanically produced figures — and a feature that hid its own
limitations behind a flag would be exactly that refuge with a switch on it.

WHAT IS CHECKED
-----------------
That the command runs end to end on a real national table; that it writes the
coefficients, the implicit interregional imports and the two records; that the
cost block names actual numbers; and that the refusals fire — including on a
**published** table, because the UK analytical table carries negative
coefficients at basic prices and the method does not admit them.

Run:
    python3 validators/run_regionalise_cli.py
"""
from __future__ import annotations

import csv
import io
import json
import shutil
import sys
import tempfile
import warnings
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

ES = ROOT / "data" / "ine" / "cne_tio_21.xlsx"
UK = ROOT / "UK_IOAT_2023_domestic_ixi.xlsx"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def run(argv):
    """The CLI, with its streams captured."""
    from quadrium.cli import main

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def activity_file(table, path, factor=None):
    rng = np.random.default_rng(11)
    share = (np.clip(0.20 * np.exp(rng.normal(0, 0.5, table.n)), 0.02, 0.85)
             if factor is None else factor)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)                       # quoted: a sector code can
        w.writerow(["sector_code", "regional"])  # contain a comma
        for c, x, s in zip(table.sector_codes, table.X, share):
            w.writerow([c, f"{x * s:.6f}"])
    return share


def main_() -> int:
    warnings.filterwarnings("ignore")
    from quadrium.io_loader import load_ine_tio

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    check("a national table to regionalise is on disk", ES.exists(), ES.name)
    if not ES.exists():
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="quadrium_regionalise_"))
    try:
        table = load_ine_tio(ES, variant="interior")
        act = tmp / "activity.csv"
        activity_file(table, act)

        code, out, err = run(["--regionalise", str(act), "--national", str(ES),
                              "--national-kind", "ine", "--method", "FLQ",
                              "--delta", "0.25", "--outputs", str(tmp),
                              "--name", "run"])
        check("the command runs end to end on a real national table",
              code == 0, f"exit {code}" + (f"; stderr: {err[:90]}" if err else ""))

        d = tmp / "run"
        wrote = {p.name for p in d.glob("*")} if d.exists() else set()
        check("and writes the coefficients, the implicit imports and both records",
              wrote >= {"coefficients.csv", "implicit_imports.csv", "report.md",
                        "assumption_ledger.json"},
              ", ".join(sorted(wrote)))

        A = np.loadtxt(d / "coefficients.csv", delimiter=",", comments="#")
        check("the coefficients are the right shape and nowhere above the "
              "national ones",
              A.shape == (table.n, table.n) and float(A.max()) <= 0.5,
              f"{A.shape[0]}x{A.shape[1]}, largest {A.max():.4f}. The quotient "
              f"only ever scales down, so this is a property the output must "
              f"have and not a hope")

        report = (d / "report.md").read_text()
        ledger = json.loads((d / "assumption_ledger.json").read_text())
        for where, text in (("report.md", report),
                            ("the printed output", out)):
            check(f"the measured cost is in {where}, unasked for",
                  "known to get wrong" in text and "28.3" in text
                  and "2.2 points" in text and "CORE_036" in text
                  and "11.7" in text and "SINGLE-REGION" in text,
                  "it names the cross-hauling share, the price of a blind "
                  "delta, the family's multiplier bias, and the interregional "
                  "feedback a single-region table cannot contain at all — a "
                  "median 11.7 % of the multiplier across 259 European "
                  "regions, measured in run_mrio_spillovers.py — and says "
                  "where the position comes from")
        check("and in the machine-readable record",
              len(ledger.get("caveats", [])) >= 3
              and ledger.get("delta") == 0.25
              and ledger.get("national_activity_from") == "table output",
              f"{len(ledger.get('caveats', []))} caveats, delta and the source "
              f"of the national activity — so a later reader knows what was "
              f"assumed without reading the prose")

        # ---- and the region comes back as a table the engine can take
        from quadrium.io_loader import load_io_table
        back = load_io_table(d / "regional_table.xlsx")
        A_back = np.nan_to_num(back.Z / np.where(back.X > 0, back.X, 1.0))
        check("the region is written as a TABLE, and reads back into the engine",
              back.n == table.n
              and float(np.abs(A_back - A).max()) < 1e-12,
              f"{back.n} sectors, coefficients preserved to "
              f"{np.abs(A_back - A).max():.1e}. Before v1.85 the command wrote "
              f"a matrix and stopped: nothing downstream could diagnose the "
              f"region, split a sector of it, or point --national at it")

        check("and it carries what it is, not just what it contains",
              len(back.Y_labels) == 1 and "residual" in back.Y_labels[0]
              and len(back.VA_labels) == 1 and back.lineage,
              f"one final-demand column ({back.Y_labels[0]!r}) and one "
              f"value-added row, because a location quotient says nothing "
              f"about how either divides; and {len(back.lineage)} lines of "
              f"lineage, so a table read later cannot pass for observed")

        # ---- the refusals
        print()
        cases = []
        c, _, e = run(["--regionalise", str(act), "--national", str(ES),
                       "--national-kind", "ine", "--outputs", str(tmp)])
        cases.append(("the FLQ without a delta", c == 2
                      and "no defensible default" in e))

        c, _, e = run(["--national", str(ES)])
        cases.append(("--national on its own", c == 2
                      and "only means something with --regionalise" in e))

        c, _, e = run(["--regionalise", str(act), "--outputs", str(tmp)])
        cases.append(("--regionalise without a national table", c == 2
                      and "there has to be one" in e))

        short = tmp / "short.csv"
        short.write_text("sector_code,regional\n1,10\n")
        c, _, e = run(["--regionalise", str(short), "--national", str(ES),
                       "--national-kind", "ine", "--method", "SLQ",
                       "--outputs", str(tmp)])
        cases.append(("an activity file missing sectors", c == 2
                      and "do not describe the same sectors" in e))

        nohdr = tmp / "nohdr.csv"
        nohdr.write_text("code,value\n1,10\n")
        c, _, e = run(["--regionalise", str(nohdr), "--national", str(ES),
                       "--national-kind", "ine", "--method", "SLQ",
                       "--outputs", str(tmp)])
        cases.append(("an activity file with the wrong header", c == 2
                      and "sector_code,regional" in e))

        fired = [n for n, ok in cases if ok]
        check("every refusal the command documents fires",
              len(fired) == len(cases),
              f"{len(fired)} of {len(cases)}: " + "; ".join(fired))

        # ---- and one on a table a statistical office published
        if UK.exists():
            from quadrium.io_loader import load_uk_analytical_iot
            uk = load_uk_analytical_iot(UK)
            uk_act = tmp / "uk.csv"
            activity_file(uk, uk_act)
            c, _, e = run(["--regionalise", str(uk_act), "--national", str(UK),
                           "--national-kind", "uk", "--method", "SLQ",
                           "--outputs", str(tmp)])
            check("and it refuses a PUBLISHED table for a documented reason",
                  c == 2 and "is negative" in e,
                  "the UK analytical table carries negative coefficients at "
                  "basic prices — this project found them in five distinct "
                  "blocks — and M-070 does not admit them, because min(q, 1) "
                  "scales a negative one UP. Refused rather than quietly "
                  "producing a number")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main_())
