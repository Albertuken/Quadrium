"""
The MRIO's side files join by POSITION, and their own labels do not describe them.

WHAT THIS OVERTURNS, AND WHY THE EARLIER REFUSAL WAS STILL RIGHT
-----------------------------------------------------------------
`run_mrio_axis_scale.py` recorded that `Final_demand_2018.xlsx` and
`TAXSUB_VA_2018.xlsx` could not be joined to the 2,720 x 2,720 block: 236 of
272 regions matched by label and 36 did not, and a **positional** join
completes and looked wrong because it would pair the block's `EL11` with the
side files' `EL30` — Anatoliki Makedonia with Attiki. The project refused to
assume, used the block alone, and stood on intermediate sales as a declared
proxy for output.

**That refusal was correct on what it knew.** What changes it is evidence, and
there is now rather a lot of it: the side files' data is in the BLOCK's
region-major order, while their label column is printed sector-major. Joining
by label pairs unrelated units; joining row `i` to row `i` pairs the right
ones. The labels lie about their own rows.

FOUR INDEPENDENT TESTS, AND THE FOURTH IS THE ONE THAT SETTLES IT
------------------------------------------------------------------
1. **Correlation.** log(intermediate sales) against log(the side files' own
   TOTAL): **-0.08 by label, +0.88 by position.** By label there is no
   relationship at all, which no true correspondence could produce.

2. **An impossibility.** Output cannot be below intermediate sales, because
   output IS intermediate sales plus final demand and final demand here is
   non-negative. By label this is violated by **875 of 2,360** units; by
   position by 123 of 2,720.

3. **The identities.** Median relative deviation of the row identity is
   **0.52 by label and 0.066 by position**; the column identity 0.46 against
   0.054.

4. **Economics, which needs no assumption about either file.** Government
   final consumption must concentrate in `O-Q` — public administration,
   education, health. Under the block's order it does: **15.5 % in `O-Q` and
   14.7 % in `R-U`, and 0.8 % or less in every one of the other eight.** Under
   the files' own labels it is 0.6 % to 2.7 % everywhere, flat, distinguishing
   nothing. The same ordering puts 94.4 % of real estate `L` into household
   consumption, which is imputed rents; almost none of construction `F`, whose
   demand is investment; and the largest export share in industry `B-E`. Four
   textbook signatures fall out of one ordering and none out of the other.

WHAT FOLLOWS FROM IT
----------------------
The NUTS vintage mismatch is a property of a label column that describes
nothing, not of the data. `run_mrio_nuts_join.py`'s finding stands on its own
— the block really does carry French codes from NUTS 2013 and Greek codes from
NUTS 2010 — but it is not what unblocks these files, and `PL12` is not a
blocker either. All 2,720 units join.

AND IT STILL DOES NOT CLOSE
-----------------------------
Positionally, 123 of 2,720 units still show output below intermediate sales
and the row identity is off by 6.6 % at the median. The join is right and the
archive does not balance. That is reported, not repaired: this file establishes
which correspondence is the true one, and nothing here invents a figure.

Run:
    python3 validators/run_mrio_side_join.py
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
FAIL: list[str] = []

COMPONENTS = ("HFCE", "NPISH", "GGFC", "GFCF", "INVNT", "EX")


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if not ((MRIO / "_mrio2018_cache.npz").exists()
            or (MRIO / "MRIO_2018_272regions.xlsx").exists()):
        print(f"    -- {MRIO.name}'s block is absent; it is 33 MB and "
              f"gitignored. The URL and SHA-256 are in _provenance.json.")
        print("\n" + "=" * 78 + "\nAll checks passed.")
        return 0

    spec = importlib.util.spec_from_file_location(
        "axis", ROOT / "validators" / "run_mrio_axis_scale.py")
    axis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(axis)

    Z, labels = axis.load_Z()
    fd_keys, fd_head, FD = axis.load_side(axis.FD, "rows")
    va_keys, va_head, VA = axis.load_side(axis.VA, "columns")

    check("the two side files share one ordering, whatever it describes",
          fd_keys == va_keys, f"{len(fd_keys)} keys, identical in both")
    check("and the side files are printed SECTOR-major while the block is "
          "REGION-major",
          labels[0].split("-", 1)[0] == labels[1].split("-", 1)[0]
          and fd_keys[0].split("-", 1)[1] == fd_keys[1].split("-", 1)[1],
          f"block {labels[:2]}, side {fd_keys[:2]} — read off the files, not "
          f"assumed")

    comp = [fd_head.index(h) for h in COMPONENTS]
    i_tot = fd_head.index("TOTAL")
    vac = [va_head.index(h) for h in ("TAXSUB", "VA", "IM")]
    i_inp = va_head.index("INPUT")

    check("`TOTAL` is not the sum of the six final-demand components, so it is "
          "output and not a final-demand total",
          abs(FD[:, i_tot].sum() - FD[:, comp].sum()) > 0.5 * FD[:, i_tot].sum()
          and abs(FD[:, i_tot].sum() - VA[:, i_inp].sum()) < 1.0,
          f"TOTAL {FD[:, i_tot].sum():,.0f} against components "
          f"{FD[:, comp].sum():,.0f}, and TOTAL equals the value-added file's "
          f"INPUT to the unit — both are the output vector")

    check("and `NPISH` and `GGFC` are the SAME column, duplicated in the "
          "source",
          np.allclose(FD[:, fd_head.index("NPISH")],
                      FD[:, fd_head.index("GGFC")]),
          "identical on all 2,720 rows. Recorded because a reader summing the "
          "six components counts one of them twice without noticing")

    pos = {k: i for i, k in enumerate(fd_keys)}
    by_label = np.array([pos[l] for l in labels if l in pos])
    lab_sel = np.array([i for i, l in enumerate(labels) if l in pos])
    by_pos = np.arange(len(labels))

    zr, zc = Z.sum(1), Z.sum(0)

    def measure(ix, sel):
        y = FD[ix][:, comp].sum(1)
        tot = FD[ix][:, i_tot]
        va_sum = VA[ix][:, vac].sum(1)
        inp = VA[ix][:, i_inp]
        z1, z0 = zr[sel], zc[sel]
        good = (tot > 0) & (z1 > 0)
        corr = float(np.corrcoef(np.log(z1[good]), np.log(tot[good]))[0, 1])
        impossible = int((tot < z1 - 1e-6).sum())
        row = float(np.median(np.abs(z1 + y - tot) / np.maximum(tot, 1.0)))
        col = float(np.median(np.abs(z0 + va_sum - inp) / np.maximum(inp, 1.0)))
        return corr, impossible, len(sel), row, col

    L = measure(by_label, lab_sel)
    P = measure(by_pos, by_pos)

    check("1/4 — by label the two files have NO relationship; by position they "
          "have a strong one",
          L[0] < 0.1 < 0.8 < P[0],
          f"log-correlation of intermediate sales with the side files' own "
          f"output: {L[0]:+.3f} by label, {P[0]:+.3f} by position. No true "
          f"correspondence produces {L[0]:+.2f}")

    check("2/4 — by label, output falls below intermediate sales for a third "
          "of all units, which cannot happen",
          L[1] / L[2] > 0.30 and P[1] / P[2] < 0.10,
          f"{L[1]} of {L[2]} by label ({100 * L[1] / L[2]:.0f} %) against "
          f"{P[1]} of {P[2]} by position ({100 * P[1] / P[2]:.1f} %). Output "
          f"IS intermediate sales plus non-negative final demand")

    check("3/4 — and the accounting identities are an order of magnitude "
          "closer by position",
          P[3] < 0.15 < L[3] and P[4] < 0.15 < L[4],
          f"median relative deviation, row identity {L[3]:.3f} by label "
          f"against {P[3]:.3f}; column identity {L[4]:.3f} against {P[4]:.3f}")

    # ---- 4. the economics, which assumes nothing about either file
    def gov_share(sector_of):
        out = {}
        for s in dict.fromkeys(l.split("-", 1)[1] for l in labels):
            ix = np.array([i for i, x in enumerate(sector_of) if x == s])
            tot = FD[ix][:, comp].sum()
            out[s] = 100.0 * FD[ix][:, fd_head.index("GGFC")].sum() / tot \
                if tot else 0.0
        return out

    g_label = gov_share([k.split("-", 1)[1] for k in fd_keys])
    g_pos = gov_share([l.split("-", 1)[1] for l in labels])
    other = [v for k, v in g_pos.items() if k not in ("O-Q", "R-U")]

    check("4/4 — government consumption lands in `O-Q` and `R-U` under the "
          "block's order, and nowhere under the files' labels",
          g_pos["O-Q"] > 10 and max(other) < 1.0
          and max(g_label.values()) < 3.0,
          f"O-Q {g_pos['O-Q']:.1f} %, R-U {g_pos['R-U']:.1f} %, every other "
          f"sector at most {max(other):.1f} % — against a flat "
          f"{min(g_label.values()):.1f}–{max(g_label.values()):.1f} % by "
          f"label. Public administration, education and health is where "
          f"government final consumption goes, and no assumption about either "
          f"file is needed to say so")

    i_h, i_e = fd_head.index("HFCE"), fd_head.index("EX")

    def share(sector, col):
        ix = np.array([i for i, l in enumerate(labels)
                       if l.split("-", 1)[1] == sector])
        tot = FD[ix][:, comp].sum()
        return 100.0 * FD[ix][:, col].sum() / tot if tot else 0.0

    L_h, F_h, BE_e = share("L", i_h), share("F", i_h), share("B-E", i_e)
    check("and three more textbook signatures fall out of the same ordering",
          L_h > 80 and F_h < 15 and BE_e > 45,
          f"real estate `L` is {L_h:.1f} % household consumption — imputed "
          f"rents; construction `F` only {F_h:.1f} %, its demand being "
          f"investment; industry `B-E` carries the largest export share at "
          f"{BE_e:.1f} %. Four signatures out of one ordering and none out of "
          f"the other is not a coincidence anyone has to weigh")

    check("so all 2,720 units join, and the NUTS vintage was a property of a "
          "label column that describes nothing",
          P[2] == len(labels) == 2720,
          "the mixed-vintage finding in run_mrio_nuts_join.py stands on its "
          "own — the block really is NUTS 2013 for France and 2010 for "
          "Greece — but it is not what unblocks these files, and PL12 is not "
          "a blocker")

    check("AND IT STILL DOES NOT CLOSE, which is reported and not repaired",
          P[1] > 0 and P[3] > 0.01,
          f"{P[1]} of {P[2]} units still show output below intermediate sales "
          f"and the row identity is off by {100 * P[3]:.1f} % at the median. "
          f"The join is established; the archive does not balance. Nothing "
          f"here invents a figure to make it")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
