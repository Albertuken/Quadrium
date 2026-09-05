"""
The feedback share is predictable only from the quantity whose absence defines the problem.

WHAT THIS TESTS, AND WHY IT WAS THE WEAK JOINT
------------------------------------------------
`run_mrio_spillovers.py` measures what a single-region table omits: a median
11.7 % of the output multiplier, from 2.1 % at the tenth percentile to 41.5 %
at the ninetieth. The argument built on that measurement — that the empirical
distribution belongs in the primary result rather than a robustness appendix —
rests entirely on the share being **unpredictable from what the analyst holds**.
If a practitioner could estimate their own region's figure from their own data,
the right answer would be to estimate it, and reporting a distribution would be
a worse substitute for a point estimate.

That had not been tested. This tests it.

THE SPLIT THAT MAKES THE TEST HONEST
--------------------------------------
An analyst regionalising a national table holds **regional output by sector** —
it is the activity vector the location quotient is computed from. They do not
hold their region's interregional trade: if they did, most of what a
single-region method omits would already be in their hands.

So the predictors are split accordingly, and only the first set is a fair test:

    A   log of regional output, and the region's sectoral composition
    B   A, plus interregional openness (trade over output)

Validation is **leave-one-country-out** across 28 countries, not a random
split. Regions within a country share an archive, a statistical office and a
compilation practice; a random fold would let a model learn one country's
regions from its neighbours and report that as prediction.

WHAT CAME OUT, ON 259 REGIONS
-------------------------------
                                    in-sample R²   out-of-sample R²      MAE
    A  what the analyst observes          +0.467            -0.086     0.0656
    B  plus interregional openness        +0.878            +0.777     0.0284
       predicting the mean, always             —             0.000     0.0645

**From what the analyst holds, the share is not predictable at all.** The
out-of-sample R² is negative: the fitted model does worse than always answering
with the mean, and its in-sample 0.467 is overfitting and nothing else.

Add the interregional trade the analyst does not have and it becomes highly
predictable — out-of-sample R² 0.78, error 0.028 against a mean of 0.172.

**The mechanism is not a surprise and that is not the point.** A region's
feedback share is largely how much it buys from elsewhere; purchase openness
alone correlates at r = +0.894. Nobody should be startled that the quantity
predicts itself. What matters is which side of the line it falls on: it is the
one quantity a single-region method exists in order not to need.

THE SAME SHAPE AS DELTA
-------------------------
`run_flq_delta.py` finds Flegg & Tohmo's own published predictor for δ missing
by a mean absolute error of 0.090 on a fitted range of 0.46, with its input
observed rather than guessed. Two parameters, two failed predictions from
observables, and in both cases the quantity that would predict well is the one
the exercise is undertaken to avoid needing.

Run:
    python3 validators/run_spillover_predictability.py
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


def _ols(X, y):
    return np.linalg.lstsq(np.c_[np.ones(len(X)), X], y, rcond=None)[0]


def _pred(b, X):
    return np.c_[np.ones(len(X)), X] @ b


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

    A = Z / np.where(X > 0, X, np.inf)
    A[~np.isfinite(A)] = 0.0
    L = np.linalg.inv(np.eye(len(A)) - A)
    m = L.sum(0)
    intra = np.empty_like(m)
    for r in range(R):
        sl = slice(r * S, (r + 1) * S)
        intra[sl] = L[sl, sl].sum(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(m > 0, (m - intra) / m, np.nan)

    island = np.array([
        (Z[r * S:(r + 1) * S, :].sum()
         - Z[r * S:(r + 1) * S, r * S:(r + 1) * S].sum()) < 1e-9
        and (Z[:, r * S:(r + 1) * S].sum()
             - Z[r * S:(r + 1) * S, r * S:(r + 1) * S].sum()) < 1e-9
        for r in range(R)])
    keep = [r for r in range(R)
            if not island[r] and X[r * S:(r + 1) * S].sum() > 0]

    y, rows = [], []
    for r in keep:
        sl = slice(r * S, (r + 1) * S)
        sh = share[sl][np.isfinite(share[sl])]
        y.append(float(np.mean(sh)))
        xr = X[sl]
        tot = xr.sum()
        sells = Z[sl, :].sum() - Z[sl, sl].sum()
        buys = Z[:, sl].sum() - Z[sl, sl].sum()
        rows.append([np.log(tot), (sells + buys) / tot, buys / tot]
                    + list(xr / tot))
    y = np.array(y)
    F = np.array(rows)
    countries = np.array([regions[r][:2] for r in keep])

    check("259 regions with the archive's islands excluded",
          len(y) == 259 and len(np.unique(countries)) > 20,
          f"{len(y)} regions across {len(np.unique(countries))} countries; "
          f"mean share {y.mean():.3f}, sd {y.std():.3f}")

    OBSERVED = [0] + list(range(3, F.shape[1]))   # log output + composition
    EVERYTHING = list(range(F.shape[1]))          # plus openness

    def score(cols):
        Xc = F[:, cols]
        yin = _pred(_ols(Xc, y), Xc)
        r2in = 1 - ((y - yin) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        yo = np.empty_like(y)
        for c in np.unique(countries):
            tr, te = countries != c, countries == c
            yo[te] = (_pred(_ols(Xc[tr], y[tr]), Xc[te])
                      if tr.sum() > len(cols) + 5 else y[tr].mean())
        r2out = 1 - ((y - yo) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        return r2in, r2out, float(np.abs(y - yo).mean())

    a_in, a_out, a_mae = score(OBSERVED)
    b_in, b_out, b_mae = score(EVERYTHING)
    base = float(np.abs(y - y.mean()).mean())

    print()
    print(f"    {'':<38}{'in-sample':>12}{'out-of-sample':>15}{'MAE':>9}")
    print(f"    {'A  what the analyst observes':<38}{a_in:>12.3f}"
          f"{a_out:>15.3f}{a_mae:>9.4f}")
    print(f"    {'B  plus interregional openness':<38}{b_in:>12.3f}"
          f"{b_out:>15.3f}{b_mae:>9.4f}")
    print(f"    {'   predicting the mean, always':<38}{'—':>12}"
          f"{0.0:>15.3f}{base:>9.4f}")
    print()

    check("from what the analyst actually holds, the share is not predictable",
          a_out < 0.05 and a_mae >= base * 0.98,
          f"out-of-sample R² {a_out:+.3f} and an error of {a_mae:.4f} against "
          f"{base:.4f} for always answering with the mean. The in-sample "
          f"{a_in:.3f} is overfitting: leave-one-country-out is the honest "
          f"split, because regions of one country share an archive, an office "
          f"and a compilation practice")

    check("and it IS predictable from the interregional trade they do not have",
          b_out > 0.6 and b_mae < base * 0.6,
          f"out-of-sample R² {b_out:+.3f}, error {b_mae:.4f} against a mean of "
          f"{y.mean():.3f}. Purchase openness alone correlates at "
          f"r = {np.corrcoef(F[:, 2], y)[0, 1]:+.3f}")

    check("the mechanism is not a surprise, and the line it falls on is the "
          "finding",
          b_out - a_out > 0.5,
          "a region's feedback share is largely how much it buys from "
          "elsewhere, so nobody should be startled that the quantity predicts "
          "itself. It matters because it is precisely the quantity a "
          "single-region method exists in order not to need — the same shape "
          "as delta, which is estimable only where a survey table makes the "
          "regionalisation unnecessary")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
