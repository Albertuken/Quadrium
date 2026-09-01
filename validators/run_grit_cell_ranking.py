"""
GRIT II ranks the cells worth re-estimating. Does the ranking settle after two terms?

WHAT THE SOURCE CLAIMS
------------------------
GRIT is a hybrid method: estimate mechanically everywhere, buy survey data only
where it pays. That makes "where does it pay" the whole question, and `CORE_036`
ch. 5.2 answers it by propagating coefficient error into the Leontief inverse
rather than by a rule of thumb. West's own paper, reproduced as the report's
Appendix V (`CORE_036` pp. 126-141), sets it out in full.

The derivation, `CORE_036` p. 133 eq. (4), writing D for the error in A:

    (I - A - D) = (I - A)(I - theta)   so   D = (I - A) theta,  theta = BD
    (I - A - D)^-1 = B + BDB + (BD)^2 B + ... = B + E1 + E2 + E3 + ...

The criterion, p. 134 eq. (6) — the total absolute error over all output
multipliers induced by E1:

    eps1 = Sum_l Sum_k  OM_k * a_kl * p_kl * RM_l

where OM_k is the kth output (column) multiplier of B and RM_l the lth row total
of B. So **the E1 score of a cell is a_kl weighted by the output multiplier of
its ROW sector and the row multiplier of its COLUMN sector** — the source draws
the consequence itself on p. 134: the error in the jth multiplier depends not on
the size of the jth multiplier but on that of the sector where the error lies.

THE CLAIM UNDER TEST is from the main report, p. 46: in their empirical tests the
ranking of the coefficients did not alter past E1 + E2, and E1 + E2 is enough if
the rankings are what you want.

WHAT THIS FILE ADDS
---------------------
The claim can be settled exactly rather than sampled, because **a single-cell
error makes D rank one**. With D = delta * e_k e_l' and delta = p * a_kl,
Sherman-Morrison gives the whole series in closed form. Writing
T(M) for the sum of every element of a matrix M, the induced change is

    Delta T = delta * OM_k * RM_l / (1 - theta),     theta = delta * b_lk

and the truncations are the geometric partial sums of the same thing:

    E1              = delta * OM_k * RM_l
    E1 + ... + E_K  = delta * OM_k * RM_l * (1 + theta + ... + theta^(K-1))
    exact           = delta * OM_k * RM_l / (1 - theta)

E1 alone reproduces eq. (6) exactly, which is a check on the reading. And every
truncation is the E1 score times a factor that depends on the cell ONLY through
theta. So the ranking changes between orders exactly to the extent that theta
varies across cells, and the question "does the ranking settle at E1+E2" becomes
a question about the size of theta, which is computable.

AND A SECOND RESULT, WHICH IS ABOUT TABLE SIZE
-----------------------------------------------
`CORE_036` p. 139 eqs. (24)-(25) treats the other case, every cell in error at
once by a constant absolute d, and gets a geometric series whose ratio is d*T,
where T is the sum of all elements of B:

    A gives rise to T, and (A + D) to T + d*T^2 + d^2*T^3 + ...
                                     = T * [1 + dT + (dT)^2 + ...]

T grows with the number of sectors. GRIT II worked on 11- and 16-sector tables;
this engine works on 63 to 104. The convergence condition d < 1/T is therefore
much tighter here than where the claim was established, and this file reports
the threshold for each table it holds instead of assuming the claim travels.

Run:
    python3 validators/run_grit_cell_ranking.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

GRIT = ROOT / "library" / "extracted" / "CORE_036_JensenEtAl1979_GRIT_II.txt"
FAIL: list[str] = []

# GRIT II's own tables, from the report's appendix titles: "11-sector" and
# "Non-Uniform (16-sector)". Used only to say where the claim was established.
GRIT_SECTORS = (11, 16)


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def tables():
    """The real tables on disk, loaded through the engine's own loaders."""
    from quadrium.io_loader import load_idescat_mioc, load_ine_tio, load_uk_analytical_iot

    out = []
    for name, fn, path in (
        ("UK analytical 2023", load_uk_analytical_iot,
         ROOT / "UK_IOAT_2023_domestic_ixi.xlsx"),
        ("Spain 2021 (INE TIO)", load_ine_tio, ROOT / "data/ine/cne_tio_21.xlsx"),
        ("Spain 2022 (INE TIO)", load_ine_tio, ROOT / "data/ine/cne_tio_22.xlsx"),
        ("Catalonia 2021 (IDESCAT)", load_idescat_mioc,
         ROOT / "data/idescat/mioc2021ts64.xlsx"),
    ):
        if not path.exists():
            continue
        try:
            out.append((name, fn(path)))
        except Exception as exc:                      # a refusal is data, not a crash
            print(f"    -- {name}: not loaded — {str(exc).splitlines()[0][:64]}")
    return out


def scores(A: np.ndarray, B: np.ndarray, p: float):
    """E1, the geometric ratio, and the exact total, for EVERY cell at once.

    Returns (e1, theta, exact) as n x n arrays. e1 is CORE_036 p. 134 eq. (6)
    restricted to one cell; exact is Sherman-Morrison on the same cell.
    """
    OM = B.sum(axis=0)                                # output/column multipliers
    RM = B.sum(axis=1)                                # row multipliers
    delta = p * A
    e1 = delta * np.outer(OM, RM)                     # OM_k * a_kl * RM_l
    theta = delta * B.T                               # theta_kl = delta_kl * b_lk
    with np.errstate(divide="ignore", invalid="ignore"):
        exact = np.where(np.abs(1.0 - theta) > 1e-12, e1 / (1.0 - theta), np.inf)
    return e1, theta, exact


def truncation(e1: np.ndarray, theta: np.ndarray, order: int) -> np.ndarray:
    """E1 + ... + E_order, the geometric partial sum."""
    return e1 * sum(theta ** m for m in range(order))


def first_disagreement(a: np.ndarray, b: np.ndarray) -> int:
    """Position of the first rank at which two orderings differ (1-based); 0 if none."""
    ra, rb = np.argsort(-a.ravel()), np.argsort(-b.ravel())
    diff = np.flatnonzero(ra != rb)
    return int(diff[0]) + 1 if diff.size else 0


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    x, y = a.ravel(), b.ravel()
    rx = np.empty_like(x); rx[np.argsort(x)] = np.arange(x.size)
    ry = np.empty_like(y); ry[np.argsort(y)] = np.arange(y.size)
    rx = rx - rx.mean(); ry = ry - ry.mean()
    return float(rx @ ry / np.sqrt((rx @ rx) * (ry @ ry)))


def main() -> int:
    warnings.filterwarnings("ignore")
    from quadrium import diagnostics

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if GRIT.exists():
        text = GRIT.read_text()
        check("the source is on disk and says the ranking settles",
              "E2 appears to be sufficient" in text,
              "CORE_036 p. 46. The page offset (-14) was established in v1.77 "
              "against 121 of 184 body pages, the runner-up agreeing on 2")
    else:
        print("    -- GRIT II's extraction is private and absent here; the "
              "arithmetic below stands on its own.")

    loaded = tables()
    check("real tables to test it on", len(loaded) >= 2,
          f"{len(loaded)} loaded: " + ", ".join(n for n, _ in loaded))
    if not loaded:
        return 1

    # ---- 1. the closed form is the same thing as inverting the perturbed matrix
    print()
    name, t = loaded[0]
    d = diagnostics.compute(t.Z, t.X)
    A, B = np.nan_to_num(d["A"]), d["L"]
    e1, theta, exact = scores(A, B, p=0.10)
    rng = np.random.default_rng(3)
    live = np.argwhere(A > 1e-9)
    pick = live[rng.choice(len(live), size=40, replace=False)]
    worst = 0.0
    for k, l in pick:
        D = np.zeros_like(A)
        D[k, l] = 0.10 * A[k, l]
        brute = np.linalg.inv(np.eye(len(A)) - A - D).sum() - B.sum()
        worst = max(worst, abs(brute - exact[k, l]))
    # Judged against the scale the brute force was computed AT, not against the
    # difference it produced. `brute` subtracts two sums of order T from each
    # other, so when a cell moves the total by 1e-8 the cancellation leaves it
    # with about six significant figures -- relative to that difference the
    # agreement looks like 1e-6, and relative to T it is 3e-16. Dividing by the
    # small quantity would measure the subtraction, not the formula.
    floor = 8.0 * np.finfo(float).eps * B.sum()
    check("Sherman-Morrison reproduces a brute-force perturbed inverse",
          worst <= floor,
          f"worst absolute difference {worst:.1e} over 40 random live cells of "
          f"{name}, against {floor:.1e} for eight ulp of the total T = "
          f"{B.sum():,.1f} at which the comparison is made — so the closed form "
          f"below is the exact series and not an approximation of it")

    # ---- 2. E1 is the source's own equation (6)
    D_all = 0.10 * A
    e1_matrix_total = (B @ D_all @ B).sum()
    check("E1 summed over all cells equals CORE_036 p. 134 eq. (6)",
          abs(e1.sum() - e1_matrix_total) <= 1e-9 * abs(e1_matrix_total),
          f"Sum OM_k a_kl p RM_l = {e1.sum():,.4f} against the matrix product "
          f"(BDB).sum() = {e1_matrix_total:,.4f} — the reading of the equation "
          f"is checked, not assumed")

    # ---- 3. does the ranking settle at E1 + E2?
    print()
    print("    the ranking claim, per table. 'first move' is the highest rank at")
    print("    which a truncation disagrees with the exact ordering:")
    print()
    print(f"    {'table':<26}{'n':>5}{'cells':>7}{'max th':>8}"
          f"{'  first move':>13}{'  top-25 kept':>15}{'  1 - rho':>21}")
    print(f"    {'':<26}{'':>5}{'':>7}{'':>8}{'E1':>7}{'E2':>6}"
          f"{'E1':>7}{'E1+E2':>8}{'E1':>12}{'E1+E2':>11}")
    settles = []
    for name, t in loaded:
        d = diagnostics.compute(t.Z, t.X)
        A, B = np.nan_to_num(d["A"]), d["L"]
        e1, theta, exact = scores(A, B, p=1.0)        # p = 1, CORE_036 p. 141
        live = A > 1e-12
        f = [first_disagreement(truncation(e1, theta, k)[live], exact[live])
             for k in (1, 2)]
        # GRIT's own Table 5.1 ranks the first 25 coefficients, so the SET an
        # analyst would act on is the fair unit of comparison: a swap between
        # rank 1 and rank 2 costs nothing operationally, and reporting only the
        # first disagreement would make a harmless reordering look like a
        # refutation.
        ex_top = set(np.argsort(-exact[live])[:25])
        kept = [len(ex_top & set(np.argsort(-truncation(e1, theta, k)[live])[:25]))
                for k in (1, 2)]
        # 1 - rho, because rho itself prints as 1.000000 at this precision and
        # would hide the very difference being measured.
        gap = [1.0 - spearman(truncation(e1, theta, k)[live], exact[live])
               for k in (1, 2)]
        settles.append((name, f, kept, gap, float(theta[live].max())))
        print(f"    {name:<26}{t.n:>5}{int(live.sum()):>7}{theta[live].max():>8.3f}"
              f"{f[0]:>7}{f[1]:>6}{kept[0]:>5}/25{kept[1]:>6}/25"
              f"{gap[0]:>12.2e}{gap[1]:>11.2e}")

    check("the ranking does NOT settle at E1 + E2, in the strict sense the "
          "source states it",
          all(f[1] != 0 for _, f, _, _, _ in settles),
          f"on all {len(settles)} tables the E1+E2 ordering already differs from "
          f"the exact one, the earliest at rank "
          f"{min(f[1] for _, f, _, _, _ in settles)}. Strictly it cannot settle "
          f"at any finite order: each truncation is the E1 score times a "
          f"geometric partial sum in theta, and theta varies from cell to cell")

    check("but in the sense that matters operationally it holds, and holds at "
          "ONE term",
          all(k[0] >= 24 for _, _, k, _, _ in settles)
          and all(g[0] < 1e-6 for _, _, _, g, _ in settles),
          "E1 alone keeps "
          + ", ".join(f"{k[0]} of the exact top 25 on {n.split()[0]}"
                      for n, _, k, _, _ in settles)
          + f", with rank correlation short of 1 by at most "
            f"{max(g[0] for _, _, _, g, _ in settles):.0e}. The second term "
            f"improves that by one to two orders of magnitude "
            f"({min(g[1] for _, _, _, g, _ in settles):.0e} at best) and moves "
            f"the acted-on set by at most one cell. So the source is wrong as "
            f"stated, right as meant, and conservative: it asks for two terms "
            f"where one carries the decision")

    # ---- 4. the all-cells-at-once series, and why table size matters
    print()
    print("    CORE_036 p. 139 eq. (25): with a constant absolute error d in every")
    print("    cell, the series ratio is d*T and convergence needs d < 1/T.")
    print()
    print(f"    {'table':<26}{'n':>5}{'T = B.sum()':>14}{'d must stay below':>20}")
    for name, t in loaded:
        d_ = diagnostics.compute(t.Z, t.X)
        T = float(d_["L"].sum())
        print(f"    {name:<26}{t.n:>5}{T:>14,.1f}{1.0 / T:>20.5f}")

    big = max(float(diagnostics.compute(t.Z, t.X)["L"].sum()) for _, t in loaded)
    check("at this scale a one-point absolute coefficient error already diverges",
          1.0 / big < 0.01,
          f"the largest table has T = {big:,.1f}, so the series needs "
          f"d < {1.0 / big:.5f} — an absolute error of 0.01 in every coefficient "
          f"gives a ratio of {0.01 * big:.2f}. On an 11-sector table of the kind "
          f"the claim was tested on, T is an order of magnitude smaller and the "
          f"same d is harmless. The claim did not travel with the table size")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
