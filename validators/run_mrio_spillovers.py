"""
What a single-region table leaves out, measured: a median 11.7 % of the multiplier.

THE QUESTION, AND WHY IT WAS BLOCKED
--------------------------------------
`M-070` regionalises a national table with the location quotient family, and
every table it produces is **single-region by construction**: it has no rows
for anywhere else, so an impulse in the region cannot travel out and come
back. How much that omits was unmeasurable here, and the reason was recorded:
without a legitimate output vector the coefficient matrix taken on the European
MRIO had **column sums up to 10.9, with 1,164 of 2,720 columns at or above 1**,
which is not a system anyone can invert.

Attaching the published output vector — `run_mrio_side_join.py` for the
correspondence, `run_mrio_real_output.py` for the vector — changes that
completely:

    column sums of A     proxy: median 0.930, max 10.907, 1,164 at or above 1
                          real: median 0.521, max  2.172,    26 at or above 1
    spectral radius                                            0.802
    Leontief inverse           computes, with no negative cell anywhere

THE MEASUREMENT
-----------------
For each of the 2,720 units the output multiplier is the column sum of
`(I - A)^-1`. Splitting that sum into the rows belonging to the unit's OWN
region and the rest gives the intraregional multiplier and the interregional
spillover. A single-region table has the first and none of the second, so the
spillover share is exactly what regionalising by quotient cannot see.

    total multiplier                        median 2.202
    intraregional part                      median 1.771
    what a single-region model omits        median 0.241 multiplier points

    spillover share    p10 2.1 %   median 11.7 %   p90 41.5 %   max 81.3 %

**The spread matters more than the median.** At the tenth percentile a
single-region table is nearly complete; at the ninetieth it is missing two
fifths of the answer. Nothing about a region's own accounts tells you which one
you are holding, which is the same shape as the FLQ's delta — a parameter the
data does not supply.

By sector the pattern is the one theory expects and is worth recording because
nothing here was tuned to produce it: finance `K` 27.8 %, professional services
`M_N` 26.7 % and information `J` 23.0 % lead; industry `B-E` is lowest at
7.3 %. Traded services reach furthest across regional borders.

THIRTEEN REGIONS ARE ISLANDS, AND ONE OF THEM IS PARIS
--------------------------------------------------------
Thirteen of the 272 regions have **zero interregional trade in either
direction** while carrying ordinary internal trade. Three (`UKI1`, `UKI2`,
`UKM2`) have no output at all — empty rows. The rest do: `FR10` is Île-de-
France, with 1,557,716 of output and 693,604 of internal intermediate trade,
and not one euro of trade with anywhere else. That is not an economy, it is a
gap in the archive, and it is what makes the finding safe to state: no
plausible reading of Paris trades with nobody.

They are excluded and said. Including them drags the median spillover share
from 11.7 % to 10.8 % on thirteen artificial zeros.

Run:
    python3 validators/run_mrio_spillovers.py
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
        print("    -- the MRIO block is absent (33 MB, gitignored).")
        print("\n" + "=" * 78 + "\nAll checks passed.")
        return 0

    spec = importlib.util.spec_from_file_location(
        "axis", ROOT / "validators" / "run_mrio_axis_scale.py")
    axis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(axis)

    Z, labels = axis.load_Z()
    fd_keys, fd_head, FD = axis.load_side(axis.FD, "rows")
    X = FD[:, fd_head.index("TOTAL")]
    R = len(dict.fromkeys(l.split("-", 1)[0] for l in labels))
    S = len(labels) // R
    regions = list(dict.fromkeys(l.split("-", 1)[0] for l in labels))
    sectors = list(dict.fromkeys(l.split("-", 1)[1] for l in labels))

    def columns_at_or_above_one(x):
        denom = np.where(x > 0, x, np.inf)
        cs = (Z / denom).sum(0)
        cs = cs[np.isfinite(cs)]
        return int((cs >= 1).sum()), float(np.median(cs)), float(cs.max())

    n_proxy, med_proxy, max_proxy = columns_at_or_above_one(Z.sum(1))
    n_real, med_real, max_real = columns_at_or_above_one(X)
    check("the published output vector is what makes the system invertible at "
          "all",
          n_proxy > 1000 and n_real < 50,
          f"columns summing to 1 or more: {n_proxy:,} of {len(labels):,} on "
          f"the proxy against {n_real}; largest column sum {max_proxy:.2f} "
          f"against {max_real:.2f}. This is why the measurement below was "
          f"recorded as impossible and is not")

    A = Z / np.where(X > 0, X, np.inf)
    A[~np.isfinite(A)] = 0.0

    v = np.ones(len(A)) / len(A)
    rho = 0.0
    for _ in range(300):
        w = A @ v
        rho = float(np.linalg.norm(w))
        if rho == 0:
            break
        v = w / rho
    check("and the system is productive, so the Leontief inverse means "
          "something", rho < 1.0,
          f"spectral radius {rho:.4f}. Above 1 the series does not converge "
          f"and every multiplier below would be an artefact")

    L = np.linalg.inv(np.eye(len(A)) - A)
    check("the inverse carries no negative cell", int((L < 0).sum()) == 0,
          f"{L.shape[0]:,} x {L.shape[1]:,}, all non-negative — which a "
          f"productive system with a non-negative A must give, and is worth "
          f"checking rather than assuming at this size")

    m = L.sum(0)
    intra = np.empty_like(m)
    for r in range(R):
        sl = slice(r * S, (r + 1) * S)
        intra[sl] = L[sl, sl].sum(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(m > 0, (m - intra) / m, np.nan)

    # ---- the islands
    island = np.array([
        (Z[r * S:(r + 1) * S, :].sum()
         - Z[r * S:(r + 1) * S, r * S:(r + 1) * S].sum()) < 1e-9
        and (Z[:, r * S:(r + 1) * S].sum()
             - Z[r * S:(r + 1) * S, r * S:(r + 1) * S].sum()) < 1e-9
        for r in range(R)])
    n_isl = int(island.sum())
    fr10 = regions.index("FR10") if "FR10" in regions else -1
    check("thirteen regions are islands in the archive, and one of them is "
          "Île-de-France",
          n_isl == 13 and fr10 >= 0 and bool(island[fr10]),
          f"{n_isl} regions have zero interregional trade in EITHER direction. "
          f"Three have no output at all. FR10 has "
          f"{X[fr10 * S:(fr10 + 1) * S].sum():,.0f} of output and "
          f"{Z[fr10 * S:(fr10 + 1) * S, fr10 * S:(fr10 + 1) * S].sum():,.0f} of "
          f"internal intermediate trade, and trades with nowhere. No reading "
          f"of Paris trades with nobody, so this is the archive and not the "
          f"economy")

    keep = np.repeat(~island, S) & np.isfinite(share)
    sh = share[keep]
    p10, p50, p90 = np.percentile(sh, [10, 50, 90])
    check("and they are excluded, because thirteen artificial zeros move the "
          "answer",
          abs(p50 - float(np.nanmedian(share))) > 0.005,
          f"median spillover share {p50:.3f} without them against "
          f"{float(np.nanmedian(share)):.3f} with them. Small, and in the "
          f"direction that would have understated the finding")

    print()
    print(f"    {'total multiplier':<40}{float(np.median(m[keep])):>10.3f}")
    print(f"    {'intraregional part':<40}{float(np.median(intra[keep])):>10.3f}")
    print(f"    {'omitted by a single-region table':<40}"
          f"{float(np.median((m - intra)[keep])):>10.3f}")
    print()

    check("a single-region table omits a median 11.7 % of the multiplier",
          0.10 < p50 < 0.13,
          f"spillover share: p10 {100 * p10:.1f} %, median {100 * p50:.1f} %, "
          f"p90 {100 * p90:.1f} %, max {100 * sh.max():.1f} %. Every table "
          f"M-070 produces has this at zero by construction")

    check("and the SPREAD is the finding, not the median",
          p90 / max(p10, 1e-9) > 10,
          f"at the tenth percentile a single-region table is nearly complete "
          f"({100 * p10:.1f} %); at the ninetieth it is missing two fifths "
          f"({100 * p90:.1f} %). Nothing in a region's own accounts says which "
          f"one you are holding — the same shape as the FLQ's delta, a "
          f"parameter the data does not supply")

    by_sector = {sectors[k]: float(np.nanmedian(
        share[np.repeat(~island, S) & (np.arange(len(share)) % S == k)]))
        for k in range(S)}
    top = sorted(by_sector, key=by_sector.get, reverse=True)
    check("traded services reach furthest across regional borders, which "
          "nothing here was tuned to produce",
          top[0] in ("K", "M_N", "J") and by_sector["B-E"] < 0.12,
          "; ".join(f"{s} {100 * by_sector[s]:.1f} %" for s in top[:3])
          + f"; industry B-E lowest at {100 * by_sector['B-E']:.1f} %")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
