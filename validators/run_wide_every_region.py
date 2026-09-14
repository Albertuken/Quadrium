"""
The three-block table, asked of every region the archive has: 259 of 272.

WHY THIS EXISTS
-----------------
Everything measured about `load_eu_mrio_wide` until 2026-09-12 rested on seven
regions chosen by hand and nine Austrian ones. Then a table for Cyprus turned
up multipliers of `nan` -- Cyprus, Estonia, Luxembourg and Malta have a single
region in the archive, so the middle block is empty, its ten columns have an
output of zero, and `A = Z / X` divided by it. The loader handed that on
without a word.

It was found by accident, while preparing something else. That is the argument
for this file: a table built for one region at a time has to be asked of every
region there is, because the archive is not uniform and the awkward cases are
not the ones anybody picks.

WHAT IT ASKS OF ALL 272
-------------------------
Load it. Then: no `nan` or infinity anywhere in the table or in where an
impulse lands; both identities close against the table's own scale; the three
blocks tile the archive exactly, 1 + the rest of the country + the rest; the
regional axis has one code per unit and names the three blocks; and the
region's own ten sectors all carry output.

WHAT IT FOUND, 2018
---------------------
    load and pass every check          259
    refused, and correctly             13

The thirteen are the archive's own defects, both already named elsewhere and
neither of them this loader's to repair:

    4   no output at all -- UKI1, UKI2, UKM2, UKM3 (`run_mrio_spillovers.py`)
    9   no interregional trade in either direction: DED2, FR10, HR03, HR06,
        HU11, PT30, RO11, SI04, SK01. Three blocks do not rescue a region the
        archive gives no trade: the other two would sit there with nothing
        crossing to them, so the refusal stands for this scope as well.

Nothing else broke, and nothing was suspect. The empty middle block is the
case this file was written for, and it now passes for all four countries that
have one.

WHAT IT COSTS
---------------
About two minutes: two solves of the 2,720-unit system per region, which is
what the one-region comparison figures in the table's notes are made of. The
side files are parsed once and kept (`_MRIO_SIDE_CACHE`), which halved it;
caching the two inverses instead would cost 118 MB and make the ordinary
one-region load slower, so it is not done.

Run:
    python3 validators/run_wide_every_region.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MRIO = ROOT / "data" / "mrio"
YEAR = 2018
FAIL: list[str] = []

NOTHING_CHECKED = 3

# What the archive is known to be missing, each named by the validator that
# measured it. A refusal for any OTHER reason is a failure here.
NO_OUTPUT = {"UKI1", "UKI2", "UKM2", "UKM3"}
NO_TRADE = {"DED2", "FR10", "HR03", "HR06", "HU11", "PT30", "RO11", "SI04",
            "SK01"}


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if not ((MRIO / "_mrio2018_cache.npz").exists()
            or (MRIO / f"MRIO_{YEAR}_272regions.xlsx").exists()):
        print("    -- the 2018 archive is absent (33 MB, gitignored). The URL "
              "and SHA-256 are in data/mrio/_provenance.json.")
        print("\n" + "=" * 78)
        print("Nothing was checked: the archive is not in this tree.")
        return NOTHING_CHECKED

    from quadrium.io_loader import (LoaderError, _mrio_block, _mrio_files,
                                    load_eu_mrio_wide)

    blk, _, _ = _mrio_files(MRIO, YEAR)
    _, labels = _mrio_block(blk)
    regions = list(dict.fromkeys(l.split("-", 1)[0] for l in labels))

    loaded, refused, broke, suspect = 0, {}, [], []
    for region in regions:
        try:
            t = load_eu_mrio_wide(MRIO, region, YEAR)
        except LoaderError as exc:
            refused[region] = str(exc).splitlines()[0]
            continue
        except Exception as exc:                              # noqa: BLE001
            broke.append(f"{region}: {type(exc).__name__}: {str(exc)[:70]}")
            continue

        S = t.n // 3
        wrong = []
        lands = np.array(t.interregional["lands"], dtype=float)
        if not (np.isfinite(lands).all() and np.isfinite(t.Z).all()
                and np.isfinite(t.X).all()):
            wrong.append("nan or infinity in the table or in where it lands")
        scale = max(float(np.abs(t.X).max()), 1.0)
        row = float(np.abs(t.Z.sum(1) + t.Y.sum(1) - t.X).max())
        col = float(np.abs(t.Z.sum(0) + t.VA.sum(0) - t.X).max())
        if row > 1e-6 * scale or col > 1e-6 * scale:
            wrong.append(f"identities row {row:.2e} col {col:.2e}")
        counts = t.interregional["regions_in_blocks"]
        if counts[0] != 1 or sum(counts) != len(regions):
            wrong.append(f"blocks {counts} against {len(regions)} regions")
        if (list(t.region_codes or []) == []
                or len(t.region_codes) != t.n
                or t.regions != t.interregional["blocks"]):
            wrong.append("the regional axis does not name the three blocks")
        if (np.asarray(t.X[:S]) <= 0).any():
            wrong.append(f"{int((np.asarray(t.X[:S]) <= 0).sum())} of the "
                         f"region's own sectors carry no output")
        if wrong:
            suspect.append(f"{region}: " + "; ".join(wrong))
        else:
            loaded += 1

    print(f"\n    {len(regions)} regions: {loaded} load and pass every check, "
          f"{len(refused)} refused, {len(broke)} raised something else, "
          f"{len(suspect)} suspect\n")

    check("every region the archive carries either loads or is refused, and "
          "none raises anything else",
          not broke, "; ".join(broke[:4]) if broke
          else "no exception outside the loader's own refusals")
    check("and every one that loads is finite, closes both identities, and "
          "tiles the archive in three blocks",
          not suspect, "; ".join(suspect[:4]) if suspect
          else f"{loaded} regions, including the four whose middle block is "
               f"empty because their country has one region in the archive")
    unexplained = {r: m for r, m in refused.items()
                   if r not in NO_OUTPUT | NO_TRADE}
    check("and every refusal is one of the archive's two known defects, not a "
          "new one",
          not unexplained,
          "; ".join(f"{r}: {m[:60]}" for r, m in list(unexplained.items())[:3])
          if unexplained else
          f"{len(NO_OUTPUT & set(refused))} with no output, "
          f"{len(NO_TRADE & set(refused))} with no interregional trade")
    missing = (NO_OUTPUT | NO_TRADE) - set(refused)
    check("and each of those thirteen is still refused, so a repair to the "
          "archive would be noticed rather than assumed",
          not missing,
          f"{', '.join(sorted(missing))} loaded this time" if missing
          else "the same thirteen as when this was written")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED:")
        for f in FAIL:
            print(f"  - {f}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
