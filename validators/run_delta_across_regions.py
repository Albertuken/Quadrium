"""
Does delta = 0.20 generalise? Nine Austrian regions say what does and what does not.

WHAT THIS ANSWERS
-------------------
`OQ-R-02` closed at v1.80 on one region: delta = 0.20 for Catalonia, and the
entry said so in its own limitation — "one region, one year, one country" —
naming `CORE_040` as the source that would settle whether it generalises. That
source is behind a portal. **What generalises a measurement is not a source but
more cases**, and there are nine survey-based ones in `run_austria_regional.py`.

BUILDING AUSTRIA'S NATIONAL TABLE, AND THE TWO ASSUMPTIONS IN IT
------------------------------------------------------------------
The nine regions are all of Austria, so the national domestic table is their
sum — the nine diagonal blocks plus the interregional flows between them. The
regional tables give the interregional block's margins but not its interior,
and one of the two margins is not directly observed either. Both gaps are filled
here explicitly rather than quietly:

1. **The column margin is exact.** Row `71 ROCimp` read across the intermediate
   columns gives, for each purchasing sector, what it buys from other regions.

2. **The row margin needs a split.** Column `61 EXPROC` gives each sector's
   total interregional sales, covering intermediate AND final use in the
   receiving region, and the tables never separate the two by selling sector.
   Assumed here: each sector splits its interregional sales the way it splits
   its own-region sales, which is observed. Rescaled to the exact column total,
   which it misses by 1.2 % — a small correction, and its size is the evidence
   the assumption is not doing much work.

3. **The interior comes from GRAS**, seeded with the aggregate of the nine
   diagonal blocks: interregional trade is assumed to follow the same i-to-j
   pattern as intraregional trade. That is the location quotient's own
   assumption, so using it here does not smuggle in anything the method under
   test does not already suppose.

WHAT IT MEASURES, IN ONE LINE
-------------------------------
Across the nine regions the FLQ at a fitted delta keeps mu1 under 0.5 %, against
**6.9 % to 20.0 %** for SLQ, and using Finland's modal 0.25 blind costs a mean
**2.2 points** of multiplier bias, 6.8 at worst. Those are the figures
`docs/GUIDE.md` §9 quotes and `src/quadrium/regionalise.py` prints.

Assumption 3 is varied at the end and moves delta by 0.02, against a spread of
0.46 between regions. Assumption 2 **cannot** be varied the obvious way: giving
every sector the same intermediate share of its interregional sales is
sign-infeasible, so GRAS refuses it rather than inventing an entry. That refusal
is a reason to prefer the own-structure split beyond its plausibility, and it is
checked below rather than described.

Run:
    python3 validators/run_delta_across_regions.py
"""
from __future__ import annotations

import math
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "mrio" / "truth" / "Austria"
REGIONS = ("AT11", "AT12", "AT13", "AT21", "AT22", "AT31", "AT32", "AT33", "AT34")
FD_OWN = ("57 HOU", "58 INV", "59 GOV", "60 EXPROW", "62 Stocks")
DELTAS = [round(0.02 * k, 2) for k in range(0, 51)]

# CORE_034 eq. (23), signs recovered in run_flq_delta.py from the paper's own
# worked example (Lappi: one of eight combinations reproduces the printed 0.202).
EQ23 = (-1.8379, 0.33195, 1.5834, -2.8812)
CATALONIA = (19.97, 0.20)          # share of Spain, and the delta fitted there
FINLAND_MODE = 0.25                # CORE_034: modal over 20 Finnish regions
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def multipliers(A):
    return np.linalg.inv(np.eye(len(A)) - A).sum(axis=0)


def mu(est, true):
    """CORE_034 p. 526 eqs. (16)-(17), both signed so both measure bias."""
    n = len(true)
    o1, o2 = true > 0, np.abs(true - 1.0) > 1e-9
    return (float(100 / n * np.sum((est[o1] - true[o1]) / true[o1])),
            float(100 / n * np.sum((est[o2] - true[o2]) / (true[o2] - 1.0))))


def flq(slq, lam):
    q = np.minimum((slq[:, None] / slq[None, :]) * lam, 1.0)
    np.fill_diagonal(q, np.minimum(slq * lam, 1.0))
    return q


def slq_only(slq, n):
    return np.minimum(slq, 1.0)[:, None] * np.ones((n, n))


def national(parts, split="own", seed_flat=False):
    """Austria's domestic table, from the nine regions. See the docstring."""
    from quadrium.gras import gras

    Zd = sum(p["Z"] for p in parts.values())
    Xc = sum(p["X_col"] for p in parts.values())
    fd = sum(p["Y"][:, [p["Y_labels"].index(c) for c in FD_OWN]].sum(1)
             for p in parts.values())
    exp = sum(p["Y"][:, p["Y_labels"].index("61 EXPROC")] for p in parts.values())
    col = sum(p["imports"]["rest of country"] for p in parts.values())

    if split == "own":
        share = np.clip(np.where(Zd.sum(1) + fd > 0,
                                 Zd.sum(1) / (Zd.sum(1) + fd), 0.0), 0.0, 1.0)
    else:
        # The same proportion for every sector. Note this has to be masked
        # where the seed row is empty: a sector that sells nothing to anyone
        # intraregionally cannot be given a positive interregional row target,
        # and GRAS refuses it outright rather than inventing a sign
        # (SignInfeasibleError, UNH_18 par. 18.35). The refusal is itself the
        # argument for the own-structure split, which produces those zeros by
        # construction.
        share = np.full(len(exp), col.sum() / exp.sum())
        share = np.where(Zd.sum(1) > 0, share, 0.0)
    row = exp * share
    row = row * (col.sum() / row.sum())
    # Assumption 3, and the one that CAN be varied: the seed. Flat-in-the-cells
    # -that-exist keeps the sign structure, so it stays feasible, and it drops
    # the i-to-j pattern entirely.
    seed = Zd.copy() if seed_flat is False else np.where(Zd > 0, 1.0, 0.0)
    res = gras(seed, row, col)
    Z = Zd + res.X
    with np.errstate(divide="ignore", invalid="ignore"):
        A = np.where(Xc > 0, Z / Xc, 0.0)
    return A, Xc, res


def fit_delta(A_nat, X_nat, part):
    """The delta that best reproduces one region's published multipliers."""
    Xr = part["X_col"]
    with np.errstate(divide="ignore", invalid="ignore"):
        true = multipliers(np.where(Xr > 0, part["Z"] / Xr, 0.0))
    share = Xr.sum() / X_nat.sum()
    base = math.log2(1.0 + share)
    s = (Xr / Xr.sum()) / (X_nat / X_nat.sum())
    s = np.where(np.isfinite(s) & (s > 0), s, 1e-12)
    best = None
    for d in DELTAS:
        m1, m2 = mu(multipliers(A_nat * flq(s, base ** d)), true)
        if best is None or abs(m1) < abs(best[1]):
            best = (d, m1, m2)
    at_default = mu(multipliers(A_nat * flq(s, base ** FINLAND_MODE)), true)[0]
    slq_m1 = mu(multipliers(A_nat * slq_only(s, len(Xr))), true)[0]
    return {"share": share * 100.0, "delta": best[0], "mu1": best[1],
            "mu2": best[2], "mu1_default": at_default, "mu1_slq": slq_m1}


def main() -> int:
    warnings.filterwarnings("ignore")
    from quadrium.io_loader import read_rokicki_components

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if not DATA.exists():
        print(f"    -- {DATA} absent; see data/mrio/_provenance.json.")
        return 0

    parts = {r: read_rokicki_components(DATA, r) for r in REGIONS}
    A_nat, X_nat, res = national(parts)
    check("Austria's national table is built and the interregional block balances",
          res.converged and res.max_row_dev < 1e-6 and A_nat.sum(0).max() < 1.0,
          f"GRAS converged in {res.iterations} iterations, margins met to "
          f"{max(res.max_row_dev, res.max_col_dev):.1e}; largest column sum of "
          f"A is {A_nat.sum(0).max():.3f}, so the table is productive")

    fits = {r: fit_delta(A_nat, X_nat, parts[r]) for r in REGIONS}

    print()
    print(f"    {'region':<8}{'share %':>9}{'delta*':>9}{'mu1 at delta*':>15}"
          f"{'mu1 at 0.25':>13}{'mu1 SLQ':>10}")
    for r in REGIONS:
        f = fits[r]
        print(f"    {r:<8}{f['share']:>9.2f}{f['delta']:>9.2f}{f['mu1']:>15.2f}"
              f"{f['mu1_default']:>13.2f}{f['mu1_slq']:>10.2f}")

    d = np.array([fits[r]["delta"] for r in REGIONS])
    print()
    print(f"    {'fitted delta across the nine':<44}"
          f"min {d.min():.2f}, median {np.median(d):.2f}, max {d.max():.2f}")
    print(f"    {'Catalonia, measured against IDESCAT':<44}{CATALONIA[1]:.2f}")
    print(f"    {'Finland, modal over 20 regions (CORE_034)':<44}{FINLAND_MODE:.2f}")

    check("the FLQ at a fitted delta beats the rest of the family on every region",
          all(abs(fits[r]["mu1"]) < 1.0 for r in REGIONS)
          and all(abs(fits[r]["mu1_slq"]) > 5.0 for r in REGIONS),
          f"|mu1| stays under {max(abs(fits[r]['mu1']) for r in REGIONS):.2f} % "
          f"fitted, against {min(abs(fits[r]['mu1_slq']) for r in REGIONS):.1f} "
          f"to {max(abs(fits[r]['mu1_slq']) for r in REGIONS):.1f} % for SLQ. "
          f"CORE_034's Finnish result, on nine regions it never saw")

    check("and the median lands where Finland's mode did, independently",
          abs(np.median(d) - FINLAND_MODE) <= 0.03,
          f"median {np.median(d):.2f} against {FINLAND_MODE:.2f} — a different "
          f"country, a different decade and a different sector scheme")

    check("but delta has no single value: it spans a factor of four",
          d.max() / d.min() > 3.0,
          f"{d.min():.2f} to {d.max():.2f} across nine regions of one country, "
          f"with Catalonia at {CATALONIA[1]:.2f}. Anyone quoting one number for "
          f"delta is quoting a central tendency, not a constant")

    # ---- does size predict it, as CORE_034 argues?
    print()
    R = np.array([fits[r]["share"] for r in REGIONS])
    lnR = np.log(R)
    slope, intercept = np.polyfit(lnR, d, 1)
    r2 = 1 - ((d - (intercept + slope * lnR)) ** 2).sum() / ((d - d.mean()) ** 2).sum()
    keep = np.array([r != "AT13" for r in REGIONS])
    s2, i2 = np.polyfit(lnR[keep], d[keep], 1)
    r2_wo = 1 - ((d[keep] - (i2 + s2 * lnR[keep])) ** 2).sum() / \
        ((d[keep] - d[keep].mean()) ** 2).sum()
    print(f"    delta against ln(size):  R2 = {r2:.3f}   "
          f"without AT13 (Vienna): R2 = {r2_wo:.3f}")
    print(f"    the Austrian relation predicts Catalonia at "
          f"{intercept + slope * math.log(CATALONIA[0]):.3f}, "
          f"{i2 + s2 * math.log(CATALONIA[0]):.3f} without Vienna; measured "
          f"{CATALONIA[1]:.2f}")

    check("size does NOT reliably predict delta, and one region carries the "
          "correlation",
          r2 < 0.4 and r2_wo < 0.15,
          f"R2 falls from {r2:.3f} to {r2_wo:.3f} when the largest region is "
          f"dropped, and the slope from {slope:.3f} to {s2:.3f}. CORE_034's "
          f"claim that the required delta rises with regional size is directed "
          f"correctly and is not usable as a predictor")

    # ---- eq. (23) out of sample, with P OBSERVED rather than guessed
    print()
    prop = {r: parts[r]["imports_total"]["rest of country"] /
            parts[r]["X_col"].sum() for r in REGIONS}
    inter = {r: (parts[r]["Z"].sum()
                 + sum(v.sum() for v in parts[r]["imports"].values()))
             / parts[r]["X_col"].sum() for r in REGIONS}
    mean_p = float(np.mean(list(prop.values())))
    nat_i = (sum(parts[r]["Z"].sum() + sum(v.sum() for v in parts[r]["imports"].values())
                 for r in REGIONS) / sum(parts[r]["X_col"].sum() for r in REGIONS))
    c, br, bp, bi = EQ23
    pred = np.array([math.exp(c + br * math.log(fits[r]["share"])
                              + bp * math.log(prop[r] / mean_p)
                              + bi * math.log(inter[r] / nat_i)) for r in REGIONS])
    err = np.abs(pred - d)
    print(f"    CORE_034 eq. (23) out of sample, with P read off the data rather")
    print(f"    than guessed: mean absolute error {err.mean():.3f}, "
          f"median {np.median(err):.3f},")
    print(f"    correlation with the fitted values r = "
          f"{np.corrcoef(pred, d)[0, 1]:+.3f}")

    check("eq. (23) does not transfer, and the missing survey quantity was not "
          "the reason",
          err.mean() > 0.05,
          f"mean absolute error {err.mean():.3f} against the under-0.03 the "
          f"paper reports for 18 of its own 20 regions. OQ-R-02 closed saying "
          f"the regression was 'unusable without the survey quantity'; here P "
          f"IS observed, in an interregional table, and it still does not "
          f"transfer. The limitation was the calibration, not the missing input")

    # ---- the number that is actually usable
    print()
    cost = np.array([abs(fits[r]["mu1_default"]) - abs(fits[r]["mu1"])
                     for r in REGIONS])
    print(f"    {'cost of using 0.25 blind, in points of mu1':<48}"
          f"mean {cost.mean():.2f}, median {np.median(cost):.2f}, "
          f"worst {cost.max():.2f}")
    print(f"    {'cost of not using the FLQ at all (SLQ)':<48}"
          f"{min(abs(fits[r]['mu1_slq']) for r in REGIONS):.1f} to "
          f"{max(abs(fits[r]['mu1_slq']) for r in REGIONS):.1f}")

    check("which confirms, on nine regions, the number measured on one",
          cost.mean() < 3.0
          and cost.mean() < min(abs(fits[r]["mu1_slq"]) for r in REGIONS) / 2,
          f"OQ-R-02 closed on Catalonia saying about 2 points for a blind 0.25 "
          f"against 8-9 for no FLQ. Austria: {cost.mean():.2f} mean, "
          f"{np.median(cost):.2f} median, against "
          f"{min(abs(fits[r]['mu1_slq']) for r in REGIONS):.1f}-"
          f"{max(abs(fits[r]['mu1_slq']) for r in REGIONS):.1f}. The usable "
          f"half of that entry survives contact with more cases")

    # ---- and the assumptions behind the national table do not drive it
    print()
    from quadrium.gras import SignInfeasibleError
    infeasible = False
    try:
        Zd_only = sum(p["Z"] for p in parts.values())
        exp_only = sum(p["Y"][:, p["Y_labels"].index("61 EXPROC")]
                       for p in parts.values())
        col_only = sum(p["imports"]["rest of country"] for p in parts.values())
        raw = exp_only * (col_only.sum() / exp_only.sum())
        from quadrium.gras import gras as _g
        _g(Zd_only.copy(), raw * (col_only.sum() / raw.sum()), col_only)
    except SignInfeasibleError:
        infeasible = True
    check("the flat alternative is not merely worse, it is infeasible",
          infeasible,
          "giving every sector the same intermediate share of its interregional "
          "sales hands a positive row target to a sector with an empty seed "
          "row, and GRAS refuses rather than inventing a sign (UNH_18 "
          "par. 18.35). The own-structure split produces those zeros by "
          "construction, which is a reason to prefer it beyond plausibility")

    # Assumption 3 CAN be varied, and is: drop the i-to-j pattern of the seed
    # entirely, keeping only which cells exist.
    A_alt, X_alt, _ = national(parts, seed_flat=True)
    d_alt = np.array([fit_delta(A_alt, X_alt, parts[r])["delta"] for r in REGIONS])
    moved = float(np.abs(d_alt - d).max())
    check("and the seed does not drive the answer",
          moved <= d.max() - d.min(),
          f"seeding the interregional block flat instead of with the "
          f"intraregional pattern moves delta by at most {moved:.2f}, against a "
          f"spread of {d.max() - d.min():.2f} between regions and a median of "
          f"{np.median(d):.2f}. The construction is declared in the docstring "
          f"because it should be, not because the result hangs on it")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
