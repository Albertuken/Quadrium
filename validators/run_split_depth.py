"""
`OQ-S-02`: how many subsectors a table can support — measured, and the answer is
that the question has no accuracy-based answer.

WHAT THE ENTRY HAS ASKED SINCE v1.3
------------------------------------
For a rule: a defensible number of subsectors. Six sources have now declined.
CORE_024 p. 17 offers only "it should be thoroughly weighted whether a coarser
but more reliable MRIO table is preferred or a less accurate but more detailed
one"; the UN Handbook is procedural across 735 pages (v1.40); CORE_015, CORE_017
and CORE_031 say nothing.

Two halves have been measured instead. `run_split_budget.py` and v1.25 give what
a split of depth `k` COSTS IN COVERAGE — share(n, k) = [2k(n−1) + k²]/(n−1+k)²
of the table becomes `PROXY_ESTIMATED`, and k/(n−1) = √2 − 1 is where half of it
does. `run_disagg_error_budget.py` and v1.30 give how wrong the estimates are
for ONE fixed k=2, as the key degrades.

Nobody has varied `k` itself. That is what this file does, and it changes the
shape of the entry.

THE DESIGN, AND THE ONE CHECK THAT MAKES IT MEAN ANYTHING
-----------------------------------------------------------
A synthetic economy of 20 sectors plus a parent that truly consists of `k`
subsectors. The parent is aggregated into the table a compiler would hold, then
split back by output share — the engine's own rule — and every reconstructed
input coefficient is scored against the truth it came from.

The subsectors are variations on one profile, with dispersion `δ`: at δ = 0 they
are homogeneous — same sales profile, and every seller divides its deliveries to
them in proportion to their size — and at δ = 1 they are barely related.

**At δ = 0 the reconstruction is exact, to 0.0000 %, for every k from 2 to 12.**
That is the check the rest rests on: proportional allocation is not approximately
right for homogeneous parts, it is exactly right, at any depth. So every error
below is heterogeneity, not arithmetic, and not the number of parts.

WHAT IT SHOWS
--------------
1. **`k` is not the operative variable. δ is.** Error is zero at δ = 0 for every
   depth tried, and grows roughly linearly in δ. Splitting into eight things
   that are alike costs less than splitting into two that are not.
2. **Per-estimated-cell error saturates in k.** At δ = 0.25 it runs 14.4, 18.4,
   20.0, 20.4 % for k = 2, 4, 8, 12 — a 42 % rise across a sixfold increase in
   depth, and flat past k ≈ 8. The tenth subsector is not much worse estimated
   than the second.
3. **What does grow with k is coverage, and that was already known exactly.**
   The whole-table error decomposes as `share(n, k) × per-cell error`, and the
   share term does nearly all the growing: 17.4 % of cells at k = 2 against
   60.9 % at k = 12.

So the accuracy cost of one more subsector is dominated by a term this project
can compute before starting (v1.25) times a term that barely moves. **There is
no depth at which accuracy falls off a cliff**, which is why no source states
one, and CORE_024's "weigh it up" is not evasion — it is the correct shape of
the answer.

WHAT THIS CANNOT SUPPORT
-------------------------
Absolute levels. The economy is synthetic, the draws are Dirichlet and the
dispersion parameter δ is not a quantity any published table reports. Nothing
here says a real split of Spanish hospitality has δ = 0.25 rather than 0.5, and
measuring δ on real data needs the sub-sector detail whose absence is `OQ-S-05`.
What the design supports is structural: the exactness at δ = 0, the saturation
in k, and the decomposition.

It also says nothing about `M-053`'s internal-block damping (`OQ-S-04`): this
truth has no self-consumption structure to recover, so α = 1 is the neutral
choice here and 1.5 would be measuring the generator.

Run:
    python3 validators/run_split_depth.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

REPLICATIONS = 150
N_OTHER = 20
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def trial(rng: np.random.Generator, k: int, delta: float,
          key_sigma: float = 0.0) -> tuple[float, float, float]:
    """One replication: (whole-table error %, split-cell error %, share split)."""
    n = N_OTHER + k
    parent = np.arange(k)

    X = rng.uniform(50, 250, n)                    # output
    mu = rng.uniform(0.4, 0.6, n)                  # intermediate share of output
    pi = rng.dirichlet(np.ones(n) * 3.0, size=n)   # each seller's sales shares

    # The parent's subsectors share ONE sales profile, dispersed by delta.
    common = rng.dirichlet(np.ones(n) * 3.0)
    for t in parent:
        f = common * np.exp(delta * rng.standard_normal(n))
        pi[t] = f / f.sum()
        mu[t] = mu[parent[0]]

    # And every seller divides its deliveries to the parent between the
    # subsectors in proportion to their SIZE, again dispersed by delta. Without
    # this the columns are heterogeneous even at delta = 0 and the harness
    # cannot be checked against a known-exact case.
    share = X[parent] / X[parent].sum()
    for i in range(n):
        mass = pi[i, parent].sum()
        f = share * np.exp(delta * rng.standard_normal(k))
        pi[i, parent] = mass * f / f.sum()

    Z = (X * mu)[:, None] * pi
    A = Z / X

    # The table the compiler holds: the parent aggregated into one sector.
    M = np.zeros((N_OTHER + 1, n))
    M[0, parent] = 1
    for t, j in enumerate(range(k, n)):
        M[1 + t, j] = 1
    Z_agg, X_agg = M @ Z @ M.T, M @ X

    # Split it back by output share, optionally with a biased key.
    w = share * np.exp(key_sigma * rng.standard_normal(k))
    w /= w.sum()
    P = np.zeros((n, N_OTHER + 1))
    P[parent, 0] = w
    for t, j in enumerate(range(k, n)):
        P[j, 1 + t] = 1
    A_hat = (P @ Z_agg @ P.T) / (P @ X_agg)

    rel = np.abs(A_hat - A) / A
    touched = np.zeros((n, n), bool)
    touched[parent, :] = True
    touched[:, parent] = True
    return (float(rel.mean() * 100), float(rel[touched].mean() * 100),
            float(touched.mean()))


def sweep(seed: int, k: int, delta: float, key_sigma: float = 0.0):
    rng = np.random.default_rng(seed)
    r = np.array([trial(rng, k, delta, key_sigma) for _ in range(REPLICATIONS)])
    return r[:, 0].mean(), r[:, 1].mean(), r[:, 2].mean()


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    DEPTHS = (2, 4, 8, 12)
    DISPERSIONS = (0.0, 0.10, 0.25, 0.50, 1.00)

    grid = {(d, k): sweep(1000 + 7 * i + j, k, d)
            for i, d in enumerate(DISPERSIONS) for j, k in enumerate(DEPTHS)}

    print(f"\n    one sector split into k, {REPLICATIONS} replications, mean "
          f"absolute error\n    on the input coefficients — whole table / the "
          f"cells the split created\n")
    print("    " + " " * 7 + "".join(f"{'k = ' + str(k):>18}" for k in DEPTHS))
    for d in DISPERSIONS:
        cells = "".join(f"{grid[(d, k)][0]:>8.2f}% /{grid[(d, k)][1]:>7.2f}%"
                        for k in DEPTHS)
        print(f"    δ={d:<5.2f}" + cells)
    print("    " + " " * 7
          + "".join(f"{grid[(0.25, k)][2]:>17.1%} " for k in DEPTHS)
          + "   <- share of cells")

    # 1 -- THE check. Homogeneous parts reconstruct exactly, at every depth.
    exact = [grid[(0.0, k)][1] for k in DEPTHS]
    check("homogeneous subsectors reconstruct EXACTLY, at every depth",
          max(exact) < 1e-9,
          f"{max(exact):.2e} % over k = {DEPTHS} — proportional allocation is "
          f"not approximately right for parts that are alike, it is exactly "
          f"right, and it does not degrade with depth")

    # 2 -- so the error is heterogeneity, and it scales with it.
    check("error is driven by how unlike the parts are",
          grid[(1.0, 2)][1] > 10 * grid[(0.10, 2)][1],
          f"at k = 2: {grid[(0.10, 2)][1]:.2f} % at δ = 0.10 against "
          f"{grid[(1.0, 2)][1]:.2f} % at δ = 1.00")

    # 3 -- and depth barely moves the per-cell error.
    lo, hi = grid[(0.25, 2)][1], grid[(0.25, 12)][1]
    check("per-estimated-cell error saturates in k",
          hi < 1.6 * lo,
          f"{lo:.2f} % at k = 2 against {hi:.2f} % at k = 12, a factor of "
          f"{hi / lo:.2f} across a sixfold increase in depth — and flat past "
          f"k ≈ 8 ({grid[(0.25, 8)][1]:.2f} %)")

    # 4 -- the whole-table error is the coverage budget times that.
    worst = max(abs(grid[(d, k)][0] - grid[(d, k)][1] * grid[(d, k)][2])
                for d in DISPERSIONS for k in DEPTHS)
    check("whole-table error decomposes as coverage x per-cell error",
          worst < 1e-9,
          f"exact to {worst:.2e} pp across the grid — so v1.25's share(n, k), "
          f"which is computable before the split, carries the whole of the "
          f"growth in k")

    # 5 -- and for scale: the key's own error is the smaller of the two effects
    #      at comparable nominal size.
    print()
    print(f"    {'key σ':<8}{'k = 2':>16}{'k = 8':>16}   (δ = 0, so this is "
          f"the KEY's error alone)")
    for s in (0.10, 0.20, 0.35):
        a, b = sweep(77, 2, 0.0, s), sweep(78, 8, 0.0, s)
        print(f"    {s:<8.2f}{a[1]:>15.2f}%{b[1]:>15.2f}%")
    key35 = sweep(77, 2, 0.0, 0.35)[1]
    check("a bad key costs less than unlike parts, at comparable size",
          key35 < grid[(0.50, 2)][1],
          f"{key35:.2f} % from a key with σ = 0.35 against "
          f"{grid[(0.50, 2)][1]:.2f} % from δ = 0.50 parts, both at k = 2. "
          f"Improving the key cannot rescue a split of things that differ")

    print()
    print("    What this does NOT give: a defensible number of subsectors.")
    print("    It gives the reason there is none. Accuracy has no cliff in k;")
    print("    the cost is coverage (computable in advance) times a per-cell")
    print("    error set by heterogeneity, which no published table reports")
    print("    and which OQ-S-05's missing detail is what would measure.")
    print("    Absolute levels are synthetic and transfer to nothing.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
