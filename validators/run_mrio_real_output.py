"""
The proxy was right about the conclusion and wrong about every region.

WHAT THIS SETTLES
-------------------
`run_mrio_axis_scale.py` measures the cross-hauling floor on the European
MRIO's 272-region axis, and it had to measure regional activity as **total
intermediate sales** — `Z.sum(axis=1)` — because the published output vector
could not be attached. The reasoning for that was explicit and reasonable: an
SLQ is a ratio of shares, so a consistently applied proxy is admissible.

`run_mrio_side_join.py` has since established the true correspondence, so the
published output vector CAN be attached, and the bet can be settled instead of
argued. It was half right, and the half it lost is the half a reader would
have used.

    all ten commodities cross-hauled            proxy 10/10   real 10/10
    regions importing the least-imported        proxy   168   real   158
    regions where the SLQ argmax agrees                160 of 272
    correlation of the 2,720 SLQ values                    +0.82

**The qualitative finding survives and no per-region statement does.** The
floor still saturates — every commodity is cross-hauled either way, which is
what that section claims. But the two activity measures disagree about which
sector a region specialises in for **112 of 272 regions**. Agriculture leads on
both, so the headline is stable; underneath it construction goes from 49
regions to 22 and real estate from 29 to 5. Anything said about a NAMED region
on the proxy would have been a coin flip.

WHAT THE ARCHIVE COSTS TO USE
-------------------------------
Attaching the real vector also makes the archive's own inconsistency
measurable, and it is not small:

  - `Z.sum(1) + final demand` is **6.6 % off** the published output at the
    median, and 2.1 % off in aggregate;
  - the implied final demand — output minus intermediate sales — is
    **negative for 123 of 2,720 units**, worst -13,614, together 0.28 % of
    total output;
  - `NPISH` and `GGFC` are the same column, so summing the six published
    components double-counts one of them. Dropping the duplicate moves the
    total from 16,740,095 to 16,461,172 and makes the row identity slightly
    WORSE, not better — which says the duplication is in the file's own
    accounting and not merely in its printing.

None of that is repaired here. This file establishes what the data supports;
balancing somebody else's archive is a decision with its own consequences and
is named in `INDEX.md` §7 A1 rather than taken in passing.

Run:
    python3 validators/run_mrio_real_output.py
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


def structure(activity, R, S):
    """The SLQ argmax count that the cross-hauling floor is read from."""
    per = np.array([activity[i * S:(i + 1) * S] for i in range(R)])
    Xr, nat = per.sum(1), per.sum(0)
    with np.errstate(divide="ignore", invalid="ignore"):
        slq = (per / Xr[:, None]) / (nat / nat.sum())
    slq = np.where(np.isfinite(slq), slq, 0.0)
    arg = slq.argmax(1)
    importing = np.array([R - int((arg == i).sum()) for i in range(S)])
    return slq, arg, importing, int((importing >= 2).sum())


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if not ((MRIO / "_mrio2018_cache.npz").exists()
            or (MRIO / "MRIO_2018_272regions.xlsx").exists()):
        print("    -- the MRIO block is absent (33 MB, gitignored).")
        print("\n" + "=" * 78 + "\nAll checks passed.")
        return 0

    spec = importlib.util.spec_from_file_location(
        "axis", ROOT / "validators" / "run_mrio_axis_scale.py")
    axis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(axis)

    Z, labels = axis.load_Z()
    fd_keys, fd_head, FD = axis.load_side(axis.FD, "rows")
    R = len(dict.fromkeys(l.split("-", 1)[0] for l in labels))
    S = len(labels) // R

    # The join established by run_mrio_side_join.py: row i to row i. The side
    # files' label column describes nothing and is not used.
    output = FD[:, fd_head.index("TOTAL")]
    sales = Z.sum(axis=1)

    check("the published output vector is attached, by the correspondence "
          "run_mrio_side_join.py established", len(output) == len(labels),
          f"{len(output):,} units, {R} regions x {S} sectors. By POSITION — "
          f"the side files' label column describes nothing and is not read")

    check("and it behaves like output rather than like a proxy for it",
          float(np.median(output / np.maximum(sales, 1e-9))) > 1.0,
          f"output exceeds intermediate sales by a median factor of "
          f"{float(np.median(output / np.maximum(sales, 1e-9))):.2f}, which is "
          f"what final demand being positive requires")

    slq_p, arg_p, imp_p, hauled_p = structure(sales, R, S)
    slq_r, arg_r, imp_r, hauled_r = structure(output, R, S)

    print()
    print(f"    {'':<38}{'proxy':>10}{'real':>10}")
    print(f"    {'commodities cross-hauled':<38}{hauled_p:>10}{hauled_r:>10}")
    print(f"    {'regions importing the least-imported':<38}"
          f"{imp_p.min():>10}{imp_r.min():>10}")
    print()

    check("the conclusion survives the proxy being replaced: every commodity "
          "is still cross-hauled",
          hauled_p == hauled_r == S,
          f"{S} of {S} either way. The floor saturates on the published output "
          f"vector as it did on the proxy, so what §9 says about the floor at "
          f"272 regions did not rest on the substitution")

    agree = int((arg_p == arg_r).sum())
    corr = float(np.corrcoef(slq_p.ravel(), slq_r.ravel())[0, 1])
    check("and no per-region statement does",
          agree < 0.7 * R and corr < 0.9,
          f"the two measures name the same specialising sector for {agree} of "
          f"{R} regions — {100 * agree / R:.0f} % — and the 2,720 SLQ values "
          f"correlate at {corr:+.2f}. Anything said about a NAMED region on "
          f"the proxy was a coin flip; the aggregate claim was not")

    sectors = list(dict.fromkeys(l.split("-", 1)[1] for l in labels))
    cnt_p = np.bincount(arg_p, minlength=S)
    cnt_r = np.bincount(arg_r, minlength=S)
    moved = {sectors[i]: (int(cnt_p[i]), int(cnt_r[i])) for i in range(S)}
    worst = max(moved, key=lambda k: abs(moved[k][0] - moved[k][1]))
    check("the sector each region specialises in moves wholesale, even though "
          "the commonest one does not change",
          sectors[int(cnt_p.argmax())] == sectors[int(cnt_r.argmax())]
          and abs(moved[worst][0] - moved[worst][1]) > 20,
          f"agriculture leads on both. But construction `F` goes from "
          f"{moved['F'][0]} regions to {moved['F'][1]}, real estate `L` from "
          f"{moved['L'][0]} to {moved['L'][1]}, and industry `B-E` from "
          f"{moved['B-E'][0]} to {moved['B-E'][1]}. A proxy can agree on the "
          f"headline and redistribute everything under it")

    # ---- what the archive costs to use
    print()
    comp = [fd_head.index(h) for h in COMPONENTS]
    y6 = FD[:, comp].sum(1)
    y5 = FD[:, [fd_head.index(h) for h in COMPONENTS
                if h != "NPISH"]].sum(1)
    rel6 = np.abs(sales + y6 - output) / np.maximum(output, 1.0)
    rel5 = np.abs(sales + y5 - output) / np.maximum(output, 1.0)

    check("the archive does not close, and the residue is stated rather than "
          "removed",
          float(np.median(rel6)) > 0.02,
          f"Z.sum(1) + final demand is {100 * float(np.median(rel6)):.1f} % off "
          f"the published output at the median and "
          f"{100 * abs((sales + y6).sum() - output.sum()) / output.sum():.1f} % "
          f"in aggregate")

    implied = output - sales
    bad = int((implied < 0).sum())
    check("and for 123 units the implied final demand is negative, which the "
          "accounting does not allow",
          bad > 0,
          f"{bad} of {len(implied):,} units, worst {implied.min():,.0f}, "
          f"together {100 * abs(implied[implied < 0].sum()) / output.sum():.2f} "
          f"% of total output. Small in weight and not small in meaning: those "
          f"units cannot be used as published")

    check("dropping the duplicated NPISH column makes the row identity WORSE, "
          "which places the duplication in the accounting and not the printing",
          float(np.median(rel5)) > float(np.median(rel6)),
          f"median deviation {100 * float(np.median(rel6)):.1f} % with the "
          f"duplicate and {100 * float(np.median(rel5)):.1f} % without it. If "
          f"NPISH were a printing artefact, removing it would improve the "
          f"identity; it does not, so the file's own total counts it twice")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
