"""
Where surveys can check the European MRIO, it keeps a region's purchases at
home: about twice what they record, and a quarter of what they buy from the
rest of the country.

WHY THIS WAS MEASURED
-----------------------
On 2026-09-11 the report started printing, for a region loaded from the
archive, how much of each sector's multiplier runs through other regions:
16.4 % for Catalonia. The same archive is where this project measured that a
single-region table omits a median 11.7 % of the output multiplier
(`run_mrio_spillovers.py`), a figure the engine prints on every
regionalisation. Both numbers are only as good as the archive's
interregional block, and nothing had checked that block against a region
whose trade was actually measured.

This project holds ten such regions: the nine survey-based Austrian tables of
Rokicki et al. (2021) -- which carry what each region buys from the rest of
Austria -- and IDESCAT's Catalan table, which carries what Catalonia buys from
the rest of Spain. For each, the intermediate inputs a region buys are split
three ways, as shares of its output: from itself, from the rest of its
country, and from abroad.

WHAT IT FINDS
---------------
    rest of the country    MRIO / survey, median 0.24    lower in 10 of 10
    the region itself                         2.06
    abroad                                    0.54
    all intermediates                         close: the level is right,
                                              the ALLOCATION is not

The archive gets roughly how much a region buys and puts most of it at home.
**So the interregional feedback measured on it is more likely too low than too
high**, and the 11.7 % is a lower bound rather than a central estimate. By how
much it is low is not measured: a quarter of the interregional purchases does
not translate into a known fraction of the multiplier.

WHAT IT CANNOT RULE OUT
-------------------------
The years differ -- the surveys are 2010 (Austria) and 2021 (Catalonia), the
archive 2018 -- and the classifications do (56 and 63 branches against 10),
which is why only shares of total output are compared. A factor of four in the
same direction in ten regions of two countries is hard to put down to eight
years. The authors validated the archive against the same Austrian tables with
similarity scores; as far as their text shows, they did not report the
direction.

Run:
    python3 validators/run_mrio_against_surveys.py
"""
from __future__ import annotations

import importlib.util
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MRIO = ROOT / "data" / "mrio"
AUSTRIA = MRIO / "truth" / "Austria"
IDESCAT = ROOT / "data" / "idescat" / "mioc2021ts64.xlsx"
S = 10
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


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if not ((MRIO / "_mrio2018_cache.npz").exists()
            or (MRIO / "MRIO_2018_272regions.xlsx").exists()) \
            or not (MRIO / "Final_demand_2018.xlsx").exists() \
            or not AUSTRIA.is_dir():
        print("    -- the MRIO block or the Austrian survey tables are absent.")
        print("\n" + "=" * 78)
        print("Nothing was checked: the archive is not in this tree.")
        return NOTHING_CHECKED

    from quadrium.io_loader import read_rokicki_components
    from quadrium.regionalise import EVIDENCE

    spec = importlib.util.spec_from_file_location(
        "axis", ROOT / "validators" / "run_mrio_axis_scale.py")
    axis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(axis)
    Z, labels = axis.load_Z()
    _, fh, FD = axis.load_side(axis.FD, "rows")
    _, vh, VA = axis.load_side(axis.VA, "columns")
    X = FD[:, fh.index("TOTAL")]
    regions = list(dict.fromkeys(l.split("-", 1)[0] for l in labels))

    def archive(region):
        """own, rest of country, abroad -- as shares of the region's output."""
        k = regions.index(region)
        s = slice(k * S, (k + 1) * S)
        out = X[s].sum()
        home = [j for j, r in enumerate(regions)
                if r[:2] == region[:2] and j != k]
        away = [j for j, r in enumerate(regions) if r[:2] != region[:2]]
        own = Z[s, s].sum()
        roc = sum(Z[j * S:(j + 1) * S, s].sum() for j in home)
        abroad = sum(Z[j * S:(j + 1) * S, s].sum() for j in away) \
            + VA[s, vh.index("IM")].sum()
        return own / out, roc / out, abroad / out

    rows = []
    print(f"\n    {'region':8}{'own':>18}{'rest of country':>22}{'abroad':>18}")
    print(f"    {'':8}{'survey  MRIO':>18}{'survey  MRIO':>22}{'survey  MRIO':>18}")
    for r in ("AT11", "AT12", "AT13", "AT21", "AT22",
              "AT31", "AT32", "AT33", "AT34"):
        c = read_rokicki_components(AUSTRIA, r)
        x = c["X_col"].sum()
        survey = (c["Z"].sum() / x,
                  c["imports"]["rest of country"].sum() / x,
                  c["imports"]["rest of world"].sum() / x)
        rows.append((r, survey, archive(r)))

    if IDESCAT.exists():
        from quadrium.io_loader import load_idescat_mioc
        t = load_idescat_mioc(IDESCAT)
        x = t.X.sum()

        def va(fragment):
            return next(row.sum() for lab, row in zip(t.VA_labels, t.VA)
                        if fragment in lab)
        rows.append(("ES51", (t.Z.sum() / x, va("resta d'Espanya") / x,
                              va("resta del món") / x), archive("ES51")))

    for r, sv, ar in rows:
        print(f"    {r:8}{sv[0]:>9.1%}{ar[0]:>7.1%}{sv[1]:>13.1%}{ar[1]:>7.1%}"
              f"{sv[2]:>11.1%}{ar[2]:>7.1%}")
    print()

    sv = np.array([r[1] for r in rows])
    ar = np.array([r[2] for r in rows])
    ratio = np.median(ar / sv, axis=0)
    lower = int((ar[:, 1] < sv[:, 1]).sum())
    total = np.median(ar.sum(1) / sv.sum(1))

    check("the archive gives every region less trade with the rest of its "
          "country than the survey records",
          lower == len(rows),
          f"lower in {lower} of {len(rows)} regions; the median ratio is "
          f"{ratio[1]:.2f} — about a quarter")
    check("and puts the difference at home",
          ratio[0] > 1.5,
          f"purchases from the region itself, MRIO / survey, median "
          f"{ratio[0]:.2f}; from abroad {ratio[2]:.2f}")
    check("while the total it buys is about right, so the fault is the "
          "allocation and not the level",
          0.8 < total < 1.3,
          f"all intermediate purchases, MRIO / survey, median {total:.2f}")

    # The engine's figure is re-derived only on the full base. The Catalan
    # table is not redistributed, so a tree with the archive and without it
    # measures nine regions and would compare a different median.
    ev = EVIDENCE.get("mrio_vs_surveys") or {}
    if len(rows) == ev.get("regions", -1) or not ev:
        check("and the engine quotes this measurement, not a rounded memory "
              "of it",
              ev.get("regions") == len(rows)
              and ev.get("lower_in") == lower
              and abs(ev.get("rest_of_country_ratio", -1)
                      - round(float(ratio[1]), 2)) < 1e-9
              and abs(ev.get("own_ratio", -1)
                      - round(float(ratio[0]), 2)) < 1e-9,
              f"regionalise.EVIDENCE['mrio_vs_surveys'] is "
              f"{ev or 'absent'}; measured {len(rows)} regions, lower in "
              f"{lower}, ratios {ratio[1]:.2f} and {ratio[0]:.2f}")
    else:
        print(f"    -- {len(rows)} of the {ev['regions']} regions are here; the "
              f"engine's figure is not re-derived from a smaller base")

    print()
    print("    The 11.7 % a single-region table omits was measured on this")
    print("    archive. Where it can be checked it keeps trade at home, so the")
    print("    true share is more likely higher; by how much is not measured.")

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
