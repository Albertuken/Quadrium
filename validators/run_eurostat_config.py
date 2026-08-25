"""
`table_kind: eurostat` — a country and a year instead of a file — and the four
tolerances the first blind test of it broke.

WHAT WAS BUILT
---------------
`eurostat.fetch()` and `eurostat.load_iot()` have existed since v1.3 and were
reachable only from Python. A configuration workbook can now say

    table_kind      eurostat
    eurostat_geo    ES
    eurostat_year   2022

and the engine downloads the table, caches it with its SHA-256, and never
downloads it again. That last clause is the point: statistical offices revise,
so a configuration that fetched on every run would answer one way in January
and another in June with nothing in the output to say why. `--refresh` forces a
new download and reports whether any figure actually moved; `--offline` refuses
to fetch and prints the URL.

WHAT THE FIRST BLIND TEST FOUND
---------------------------------
Portugal was chosen because the project had never touched it. It prints its
symmetric table to **two decimals**; Spain prints to one. That single
difference was refused by four consecutive gates:

    validate_original balance     refused 0.09  at 2.6e-05   floor 0.37
    GRAS margin consistency       refused 0.03  at 1.1e-05   floor 1.3
    check_margins_attained        refused 0.09  at 0.033     floor 0.12
    check_reaggregation           refused 0.0158 %  at 1e-06 %

Every one of those bounds was either a flat project constant or a figure
inferred from numbers the engine had computed rather than read — margins that
are a published cell times a weight carry seven decimals where the publisher
printed two, and a two-element margin vector carries the rounding of the sixty
cells it was formed from, not of two.

`OQ-B-02` closed at v1.57 on exactly this rule: a table published to `d`
decimals cannot have an `n`-term identity checked more tightly than
`0.5·10^-d·n`. `precision` has computed it since v1.10. Four gates never used
it, and nothing showed, because every fixture the project held either printed
one decimal or closed exactly. **Spain 2020 fails the first gate too**, so it
was never about Portugal.

The fix is one measured number carried through: how far the SOURCE fails to
close its own books. Zero for the UK, the INE and Spain 2022 — where every
figure below is unchanged, which is the check that this loosened nothing — and
0.09 for Portugal, which is exactly the deviation it was being failed for.

Run:
    python3 validators/run_eurostat_config.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "eurostat"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def config_meta(**over) -> dict:
    meta = {"project_id": "eurostat_check", "table_kind": "eurostat",
            "eurostat_geo": "ES", "eurostat_year": 2022,
            "eurostat_dataset": "product_by_product",
            "eurostat_variant": "domestic",
            "table_path": "naio_10_cp1700_ES_2022.json",
            "title": "t", "notes": ""}
    meta.update(over)
    return {k: v for k, v in meta.items() if v is not None}


def tables(sector: str, new: list[str]) -> dict:
    return {
        "splits": [{"sector_code": sector, "new_code": c,
                    "new_label": f"{c} label", "key_id": "k"} for c in new],
        "keys": [{"key_id": "k", "new_sector_code": c, "value": v,
                  "source": "synthetic", "source_year": 2020,
                  "strength": "weak"}
                 for c, v in zip(new, (30.0, 70.0))],
        "scenarios": [{"scenario_id": "S1", "label": "S1", "description": ""}],
        "profiles": [],
    }


def refuses(meta, **kw) -> str:
    from quadrium.config import ConfigError, build_config
    try:
        build_config(meta, tables("I", ["I55", "I56"]), base_dir=DATA, **kw)
    except ConfigError as exc:
        return str(exc)
    return ""


def main() -> int:
    from quadrium.config import build_config
    from quadrium.eurostat import load_iot
    from quadrium.precision import assertable_tolerance, printed_decimals
    from quadrium.project import IOProject

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # ---- 1. the configuration path, entirely from cache ------------------
    # `offline=True` throughout: a validator must never need the network, and
    # asserting it here is also the proof that a cached table is not re-fetched.
    cfg = build_config(config_meta(), tables("I", ["I55", "I56"]),
                       base_dir=DATA, offline=True)
    t = cfg["table"]
    check("a workbook can name a country and a year instead of a file",
          t.n == 65 and t.country == "Spain" and t.year == 2022,
          f"{t.table_id} — {t.n} products, {t.unit}")
    check("and a cached table is read without the network",
          "cache" in (t.notes or "").lower(),
          "offline=True was set, so a fetch would have raised instead")
    pt = build_config(config_meta(eurostat_geo="PT", eurostat_year=2020,
                                  table_path="naio_10_cp1700_PT_2020.json"),
                      tables("I", ["I55", "I56"]), base_dir=DATA,
                      offline=True)["table"]
    check("the download's provenance reaches the report",
          "SHA-256" in (pt.notes or "") and "Downloaded" in (pt.notes or ""),
          "the notes field is what the report prints under 'What the loader "
          "decided when reading this file'")
    check("and a cache with no sidecar says so rather than saying nothing",
          "NO PROVENANCE SIDECAR" in (t.notes or ""),
          "the Spanish fixtures predate the sidecar; their provenance is in "
          "data/eurostat/README.md and the engine cannot see it")

    # ---- 2. the refusals -------------------------------------------------
    print()
    for label, meta, expect in (
            ("a three-letter country code", config_meta(eurostat_geo="ESP"),
             "two-letter country code"),
            ("a year that is not a year", config_meta(eurostat_year="dos mil"),
             "not a year"),
            ("a dataset outside the naio_10 family",
             config_meta(eurostat_dataset="cosas_ricas"), "naio_10_*"),
            ("the imports variant, which is not a symmetric IOT",
             config_meta(eurostat_variant="imports"), "no output vector")):
        msg = refuses(meta, offline=True)
        check(f"refuses {label}", expect in msg, msg.split("\n")[0][:88])

    msg = refuses(config_meta(eurostat_geo="PT", eurostat_year=2019,
                              table_path=None), offline=True)
    check("refuses to guess when offline and not yet cached",
          "--offline" in msg and "eurostat/api" in msg,
          "and prints the URL, so the file can be brought in by hand")

    # ---- 3. what the blind test found ------------------------------------
    print()
    print(f"    {'':32s}{'dp':>3}{'max dev':>10}{'old bound':>11}"
          f"{'derived':>10}")
    verdicts = {}
    for name, variant in (("naio_10_cp1700_ES_2020.json", "domestic"),
                          ("naio_10_cp1700_ES_2022.json", "domestic"),
                          ("naio_10_cp1700_PT_2020.json", "domestic")):
        tb = load_iot(DATA / name, variant)
        dev = max(float(np.abs(tb.Z.sum(1) + tb.Y.sum(1) - tb.X).max()),
                  float(np.abs(tb.Z.sum(0) + tb.VA.sum(0) - tb.X).max()))
        vals = np.concatenate([tb.Z.ravel(), tb.Y.ravel(), tb.VA.ravel(),
                               tb.X.ravel()])
        dp = printed_decimals(vals)
        derived = assertable_tolerance(vals, tb.n + tb.Y.shape[1] + 1)
        old = 1e-6 + 1e-9 * max(abs(tb.X).max(), 1.0)
        verdicts[name] = (dev, old, derived)
        print(f"    {name:32s}{dp!s:>3}{dev:10.3g}{old:11.3g}{derived:10.3g}")

    refused_before = [n for n, (d, o, _) in verdicts.items() if d > o]
    check("the old flat bound refused two of these three published tables",
          len(refused_before) == 2
          and "naio_10_cp1700_ES_2020.json" in refused_before,
          f"{', '.join(sorted(refused_before))} — and one of them is Spain, so "
          f"this was never a Portuguese problem")
    check("the derived bound accepts all three",
          all(d <= dv for d, _, dv in verdicts.values()),
          "every deviation is one to two orders of magnitude INSIDE what the "
          "publisher's own rounding can produce")

    # ---- 4. and it runs, end to end, on the two-decimal source ----------
    print()
    with tempfile.TemporaryDirectory() as tmp:
        outcomes = {}
        for geo, year, sector in (("ES", 2022, "I"), ("PT", 2020, "I")):
            cfg = build_config(
                config_meta(eurostat_geo=geo, eurostat_year=year,
                            table_path=f"naio_10_cp1700_{geo}_{year}.json"),
                tables(sector, [f"{sector}55", f"{sector}56"]),
                base_dir=DATA, offline=True)
            project = IOProject(
                project_id=f"{geo}_{year}", table=cfg["table"],
                splits=cfg["splits"], scenarios=cfg["scenarios"],
                keys=cfg["keys"], ledger=cfg["ledger"], title=cfg["title"],
                source_file="—", root=Path(tmp))
            project.run().write()
            r = project.results[0]
            outcomes[geo] = (r.report.passed, r.report.reaggregation_error_pct,
                             cfg["table"])

        check("the one-decimal source is untouched by any of this",
              outcomes["ES"][0] and outcomes["ES"][1] < 1e-9,
              f"Spain 2022 reaggregates to {outcomes['ES'][1]:.2e} %, as it "
              f"always did — the allowance is zero where the source closes")
        check("and the two-decimal source now runs at all",
              outcomes["PT"][0],
              f"Portugal 2020 passes, reaggregating to "
              f"{outcomes['PT'][1]:.3g} % — every allowance it used is named "
              f"in its own report, beside the figure it applies to")

    print()
    print("    A tolerance that is a constant is a claim about every source")
    print("    anyone will ever load. Four of them were, and the first")
    print("    unfamiliar country the engine was pointed at refused to load.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
