"""
A region of the European MRIO, with its employment from Eurostat.

WHY
-----
The owner's first example for satellite accounts was an employment multiplier
for a region, and the engine could not give one: the accounts existed, but
somebody had to type the employment in. For a region of the European MRIO it
does not have to be typed. The archive's ten sectors are exactly Eurostat's A10
grouping, and Eurostat's regional accounts publish employment by NUTS-2 region
on that same grouping -- `nama_10r_3empers`, thousand persons, employed persons
`EMP`. So `mrio_employment: yes` fetches it for the region and year loaded,
keeps the download with its provenance, and attaches it as the account
`employment`.

WHAT IS CHECKED
-----------------
Catalonia, 2018, from the download kept in `data/eurostat/`, offline: the
account carries Eurostat's ten figures in the table's sector order, they add
up to the total Eurostat publishes, the report prints employment multipliers,
and the account's notes say what the ratio mixes -- employment is measured,
the archive's output is estimated.

WHAT IT CANNOT DO, AND SAYS
-----------------------------
Eurostat publishes the current NUTS codes and the archive codes France on NUTS
2013 and Greece on NUTS 2010, so there the codes do not meet. The engine
refuses and points at the `satellites` sheet rather than translating a code by
hand; `tests/test_engine.py` fires that refusal without a network.

Run:
    python3 validators/run_eu_mrio_employment.py
"""
from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import warnings
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MRIO = ROOT / "data" / "mrio"
CUBE = ROOT / "data" / "eurostat" / "nama_10r_3empers_ES51_2018.json"
REGION, YEAR = "ES51", 2018
FAIL: list[str] = []

# Exit code 3, not 0. `check.sh` counts it as SKIPPED rather than as a pass:
# this validator opened no file and measured nothing, and a run that says
# "All checks passed" on evidence it never saw is the fault the suite exists
# to catch. It is not a failure -- a tree without the workbook still exits 0.
NOTHING_CHECKED = 3


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def cube_values(path):
    """Eurostat's figure per NACE code, read here without the engine."""
    doc = json.loads(Path(path).read_text())
    idx = doc["dimension"]["nace_r2"]["category"]["index"]
    # Every other dimension was fetched with one category, so a cell's
    # position is its sector's position.
    return {code: doc["value"].get(str(i)) for code, i in idx.items()}


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    need = [MRIO / f for f in ("MRIO_2018_272regions.xlsx",
                               "Final_demand_2018.xlsx", "TAXSUB_VA_2018.xlsx")]
    if not all(p.exists() for p in need) or not CUBE.exists():
        print("    -- the 2018 archive or the kept Eurostat download is absent.")
        print("\n" + "=" * 78)
        print("Nothing was checked: the archive or the employment download is "
              "not in this tree.")
        return NOTHING_CHECKED

    import openpyxl

    from quadrium.cli import main as cli
    from quadrium.config import load_config

    tmp = Path(tempfile.mkdtemp(prefix="quadrium_emp_"))
    cache = tmp / "data" / "eurostat"
    cache.mkdir(parents=True)
    shutil.copy(CUBE, cache / CUBE.name)
    side = CUBE.with_suffix(CUBE.suffix + ".provenance")
    if side.exists():
        shutil.copy(side, cache / side.name)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "project"
    for k, v in (("project_id", "emp"), ("table_path", str(MRIO)),
                 ("table_kind", "eu_mrio"), ("mrio_region", REGION),
                 ("mrio_year", YEAR), ("mrio_employment", "sí")):
        ws.append([k, v])
    ws = wb.create_sheet("splits")
    ws.append(["sector_code", "new_code", "new_label", "key_id"])
    ws.append(["G-I", "GI1", "Trade and transport", "k1"])
    ws.append(["G-I", "GI2", "Accommodation and food", "k1"])
    ws = wb.create_sheet("keys")
    ws.append(["key_id", "new_sector_code", "value", "source", "source_year",
               "strength"])
    ws.append(["k1", "GI1", 70, "validator fixture, not a measurement", 2018,
               "weak"])
    ws.append(["k1", "GI2", 30, "validator fixture, not a measurement", 2018,
               "weak"])
    book = tmp / "emp.xlsx"
    wb.save(book)

    try:
        cfg = load_config(book, offline=True)
    except Exception as exc:                              # noqa: BLE001
        check("a workbook asking for the region's employment loads offline "
              "from the kept download", False, str(exc).splitlines()[0][:150])
        print(f"\n{len(FAIL)} check(s) FAILED.")
        return 1
    table = cfg["table"]
    sat = (table.satellites or {}).get("employment")
    want = cube_values(CUBE)
    expected = [want.get(c) for c in table.sector_codes]
    check("the account carries Eurostat's ten figures, in the table's sector "
          "order",
          sat is not None and None not in expected
          and list(sat.values) == expected,
          f"{REGION} {YEAR}: " + ", ".join(
              f"{c} {v:,.1f}" for c, v in zip(table.sector_codes, expected)
              if v is not None))
    check("and they add up to the total Eurostat publishes",
          sat is not None and abs(sum(sat.values) - want["TOTAL"]) < 0.5,
          f"{sum(sat.values) if sat else 0:,.1f} against a published "
          f"{want['TOTAL']:,.1f} thousand persons")
    check("and the account says what the ratio mixes",
          sat is not None and "measured" in (sat.notes or "")
          and "estimated" in (sat.notes or ""),
          (sat.notes or "")[:120] if sat else "no account")

    out = tmp / "out"
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        code = cli([str(book), "--outputs", str(out), "--offline"])
    rep = out / "emp" / "report.md"
    text = rep.read_text() if rep.exists() else ""
    check("and the report prints employment multipliers for the region",
          code == 0 and "employment" in text and "thousand persons" in text,
          f"exit {code}")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED:")
        for f in FAIL:
            print(f"  - {f}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
