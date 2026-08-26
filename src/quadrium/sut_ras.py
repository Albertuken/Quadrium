"""
SUT-RAS — joint projection of a supply-and-use pair, as specified in UNH_18
(UN Handbook on SUT and IOT 2018, ch. 18), §D.2 / ¶18.86, pp. 571–573, with the
flow diagram at Box 18.6, p. 575.

WHAT IT DOES THAT GRAS CANNOT
-----------------------------
`gras.py` needs both row and column totals. For a real SUT the row totals are
product outputs, and UNH_18 ¶18.38, p. 559 says plainly that this "is sometimes
unrealistic … Indeed, the total product outputs are not usually known and,
consequently, row totals are not known."

SUT-RAS replaces the unknown product row totals with an IDENTITY: total supply of
a product equals total use of it. In the algebra that is the same quadratic root
GRAS uses, evaluated at target zero, where it collapses to sqrt(n/p) — see
`_product_factors`. Everything else follows from that one substitution.

It also does three things GRAS does not (¶18.38, p. 559; ¶18.51, p. 562):
distinguishes domestic from imported use structurally, admits basic OR
purchasers' prices, and projects supply and use jointly so that both products and
industries balance.

BLOCK STRUCTURE (¶18.85, p. 571)
--------------------------------
    d   domestic intermediate and final use          (products x use columns)
    m   imported intermediate and final use, PLUS an additional row for taxes
        less subsidies on products                   (products+1 x use columns)
    v   the supply table transposed                  (industries x products)

Each is split P - N as in GRAS. GVA is NOT a block: ¶18.87, p. 573 — "At the end,
the GVA components are simply added to the projected table, since they are
assumed to be known." This module never touches GVA, structurally rather than by
convention.

TARGETS FOR THE PROJECTION YEAR
-------------------------------
    x    industry outputs                      (Box 18.6, p. 575: "projected
                                                (supply) row total")
    u    use column totals, EXCLUDING GVA      ("projected (use) column total")
    MT   total imports + total taxes less subsidies of the projected year

`u` for an industry column is that industry's output minus its GVA. The chapter
lists the required inputs as "industry outputs; GVA totals by industry; totals of
final use categories; total imports; and total taxes less subsidies on products"
(¶18.84, p. 571) and leaves the subtraction implicit. It is DERIVED, and it is
verified: `run_sut_ras_austria.py` recovers the chapter's own printed s(1) from
it exactly.

WHAT IS NOT SPECIFIED
---------------------
* No value of the convergence threshold. ¶18.86, p. 573 says only "less than a
  certain threshold for all the elements. Convergence needs to be guaranteed."
  Unlike GRAS, which at least offers 1e-8 by example (¶18.81, p. 569), SUT-RAS
  gets no number at all. PROJECT_SUT_RAS_EPS below is a PROJECT CHOICE and is
  labelled as one. See D_open_questions.md OQ-B-02.
* No iteration limit.
* Degenerate rows/columns whose non-negative part sums to zero — the same gap as
  GRAS, OQ-B-07. Raises rather than guessing. An entirely EMPTY import row whose
  projected import total is also zero is not that case and is left alone: a
  product a country does not import has nothing for a factor to reach. That
  distinction is what made this method runnable on published data at all — with
  the guard as first written it refused all 61 Eurostat back-test pairs.
* The purchasers'-price and external-information capabilities the chapter claims
  (¶18.38, p. 559; ¶18.51, p. 562) are asserted and never shown. Not implemented.

Output is BALANCED. Convergence is necessary and not sufficient
(CORE_006 ¶9.51, p. 288).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .gras import DegenerateMarginError, quadratic_scaling_factor, split_pn

# PROJECT CHOICE. UNH_18 states no threshold for this method.
PROJECT_SUT_RAS_EPS = 1e-10

# PROJECT CHOICE. No iteration limit is stated.
PROJECT_MAX_ITER = 10_000


@dataclass
class SutRasResult:
    Fd: np.ndarray            # projected domestic use
    Fm: np.ndarray            # projected imported use + taxes row
    Fv: np.ndarray            # projected supply, transposed (industries x products)
    rd: np.ndarray
    rm: np.ndarray
    rv: np.ndarray
    s: np.ndarray
    r: float
    iterations: int
    converged: bool
    eps: float
    max_rd_step: float
    max_rm_step: float
    history: list = field(default_factory=list)

    def __str__(self) -> str:
        mark = "CONVERGED" if self.converged else "NOT CONVERGED"
        return (f"[{mark}] SUT-RAS  iterations = {self.iterations}  "
                f"eps = {self.eps:g} (PROJECT CHOICE)\n"
                f"        |r_d(k+1)-r_d(k)|_inf = {self.max_rd_step:.3e}\n"
                f"        |r_m(k+1)-r_m(k)|_inf = {self.max_rm_step:.3e}\n"
                f"        UNH_18 SS D.2 / par. 18.86, pp. 571-573; Box 18.6, p. 575")


def _product_factors(Pd, Nd, Pv, Nv, s, rv):
    """Step 2's r^d (UNH_18 par. 18.86, p. 572).

        p_i^d = sum_j p_ij^d s_j + sum_k n_ki^v / r_k^v
        n_i^d = sum_j n_ij^d / s_j + sum_k p_ki^v r_k^v
        r_i^d = sqrt( n_i^d / p_i^d )

    The square root is the GRAS root at target zero: the product row is
    constrained by the supply-equals-use identity, not by a known total. Use
    aggregates carry P with s and N against s; supply aggregates enter with the
    signs swapped, because supply sits on the other side of the identity.
    """
    p_d = Pd @ s + (Nv / rv[:, None]).sum(axis=0)
    n_d = (Nd / s).sum(axis=1) + (Pv * rv[:, None]).sum(axis=0)
    if (p_d <= 0.0).any():
        raise DegenerateMarginError(
            f"product rows {np.flatnonzero(p_d <= 0.0).tolist()}: the "
            f"non-negative part sums to zero. Unlike the GRAS case of OQ-B-07, "
            f"which was solvable and is now solved, this one is not: par. 18.86, "
            f"p. 572 uses the ZERO-target root sqrt(n/p), and at p = 0 the "
            f"constraint -n/x = 0 has no finite positive solution. An entirely "
            f"non-positive product row cannot be made to balance supply against "
            f"use by positive scaling."
        )
    return np.sqrt(n_d / p_d), p_d, n_d


def _import_factors(Pm, Nm, m, s, r):
    """Step 2's r^m (UNH_18 par. 18.86, p. 572).

        r_i^m = sqrt( ( sum_j n_ij^m / s_j + r m_i ) / ( sum_j p_ij^m s_j ) )

    `r m_i` is the projected import (or taxes) total for row i, so this is again
    the zero-target root: imports supplied must equal imports used.
    """
    denom = Pm @ s
    numer = (Nm / s).sum(axis=1) + r * m

    # AN EMPTY ROW WITH AN EMPTY TARGET IS NOT DEGENERATE, IT IS DONE.
    #
    # The guard refused every row whose non-negative part summed to zero. Most
    # of those are products a country simply does not import: Spain's `G47`
    # retail trade services, `L68A` imputed rents, `S95`, `T` — the whole row is
    # zero and the projected import total for it is zero too. There is nothing
    # for a factor to reach, the row stays zero whatever factor is chosen, and
    # refusing is refusing arithmetic that already holds.
    #
    # It is not a rare corner. **SUT-RAS could not be run on ONE of the 61
    # Eurostat back-test pairs** — every country has four to twenty such rows —
    # so a method verified against the chapter's printed iterations had never
    # touched a published table.
    #
    # The genuine case stays refused: a row whose non-negative part is zero and
    # which still has something to reach, because it carries negatives or a
    # non-zero import total. No positive factor gets there.
    scale = float(np.abs(Pm).sum() + np.abs(Nm).sum() + np.abs(m).sum())
    tiny = max(scale, 1.0) * 1e-12
    empty = (np.abs(Pm).sum(axis=1) <= tiny) & (np.abs(Nm).sum(axis=1) <= tiny)
    inert = empty & (np.abs(numer) <= tiny)
    bad = (denom <= 0.0) & ~inert
    if bad.any():
        raise DegenerateMarginError(
            f"import rows {np.flatnonzero(bad).tolist()}: the "
            f"non-negative part sums to zero (UNH_18 par. 18.86, p. 572), and "
            f"no positive factor can make an all-non-positive import row meet a "
            f"non-negative import total. Not the OQ-B-07 case, which is solved."
        )
    out = np.ones_like(denom, dtype=float)
    live = ~inert
    out[live] = np.sqrt(numer[live] / denom[live])
    return out


def sut_ras(Pd, Nd, Pm, Nm, Pv, Nv, m, x, u, MT, *,
            eps: float = PROJECT_SUT_RAS_EPS,
            max_iter: int = PROJECT_MAX_ITER) -> SutRasResult:
    """Project a SUT pair onto industry outputs `x`, use column totals `u` and
    total imports-plus-taxes `MT`. Product outputs are NOT required.

    All six block arrays are non-negative: `N*` holds the absolute values of the
    negatives, per the `T = P - N` convention of UNH_18 ¶18.86, pp. 571–572.
    Use `blocks_from_signed()` if you have signed tables.
    """
    Pd, Nd, Pm, Nm, Pv, Nv = (np.asarray(a, float)
                              for a in (Pd, Nd, Pm, Nm, Pv, Nv))
    m = np.asarray(m, float).ravel()
    x = np.asarray(x, float).ravel()
    u = np.asarray(u, float).ravel()

    n_ind, n_prod = Pv.shape
    n_col = Pd.shape[1]
    if Pd.shape != (n_prod, n_col) or Pm.shape != (m.size, n_col):
        raise ValueError(f"block shapes disagree: d {Pd.shape}, m {Pm.shape}, "
                         f"v {Pv.shape}, m-vector {m.size}, columns {n_col}")
    if x.size != n_ind or u.size != n_col:
        raise ValueError(f"target shapes disagree: x {x.size} vs {n_ind} "
                         f"industries, u {u.size} vs {n_col} columns")

    # Step 2's starting points (par. 18.86, p. 572).
    s = np.ones(n_col)
    rv = np.ones(n_ind)
    r = 1.0
    rd = np.ones(n_prod)
    rm = np.ones(m.size)
    history: list[dict] = []
    converged = False
    max_rd_step = max_rm_step = np.inf
    k = 0

    for k in range(1, max_iter + 1):
        rd_prev, rm_prev = rd, rm

        # ---- Step 2: product-row and import-row factors, from s, r^v, r.
        rd, p_d, n_d = _product_factors(Pd, Nd, Pv, Nv, s, rv)
        rm = _import_factors(Pm, Nm, m, s, r)

        # ---- Step 3: industry, use-column and import-scalar factors, from r^d, r^m.
        A = (Pv / rd[None, :]).sum(axis=1)      # sum_j p_ij^v / r_j^d
        B = (Nv * rd[None, :]).sum(axis=1)      # sum_j n_ij^v r_j^d
        rv = quadratic_scaling_factor(x, A, B, "industry")

        p_s = rd @ Pd + rm @ Pm
        n_s = (Nd / rd[:, None]).sum(axis=0) + (Nm / rm[:, None]).sum(axis=0)
        s = quadratic_scaling_factor(u, p_s, n_s, "use column")

        r = float(MT / (m / rm).sum())

        # ---- Step 4: convergence, on r^d AND r^m, element-wise (p. 573).
        max_rd_step = float(np.max(np.abs(rd - rd_prev)))
        max_rm_step = float(np.max(np.abs(rm - rm_prev)))
        history.append({
            "iteration": k,
            "p_d": p_d.copy(), "n_d": n_d.copy(), "rd": rd.copy(),
            "rm": rm.copy(), "p_v": A.copy(), "n_v": B.copy(), "rv": rv.copy(),
            "p_s": p_s.copy(), "n_s": n_s.copy(), "s": s.copy(), "r": r,
            "dev_rd": (rd - rd_prev).copy(), "dev_rm": (rm - rm_prev).copy(),
        })
        # k == 1 compares against the SEEDED ones, not against a computed
        # iterate, so it is not a convergence test. On this chapter's own
        # fixture it would fire immediately and wrongly: the base year already
        # balances, so r_d(1) = r_m(1) = 1 exactly and the step reads as zero.
        # Box 18.5, p. 574 prints its dev columns from iteration 2 for the same
        # reason.
        if k > 1 and max_rd_step < eps and max_rm_step < eps:
            converged = True
            break

    # ---- Step 5: reconstruction (par. 18.86, p. 573).
    Fd = rd[:, None] * Pd * s[None, :] - Nd / (rd[:, None] * s[None, :])
    Fm = rm[:, None] * Pm * s[None, :] - Nm / (rm[:, None] * s[None, :])
    # The supply block inverts: r^v over r^d for P, r^d over r^v for N.
    Fv = (rv[:, None] * Pv / rd[None, :]) - (rd[None, :] * Nv / rv[:, None])

    return SutRasResult(Fd=Fd, Fm=Fm, Fv=Fv, rd=rd, rm=rm, rv=rv, s=s, r=r,
                        iterations=k, converged=converged, eps=eps,
                        max_rd_step=max_rd_step, max_rm_step=max_rm_step,
                        history=history)


def blocks_from_signed(Fd, Fm, Fv):
    """Convenience: signed blocks -> the six P/N arrays sut_ras() expects."""
    Pd, Nd = split_pn(Fd)
    Pm, Nm = split_pn(Fm)
    Pv, Nv = split_pn(Fv)
    return Pd, Nd, Pm, Nm, Pv, Nv


def imports_and_taxes(result: SutRasResult, m) -> np.ndarray:
    """Step 6 (par. 18.86, p. 573): the projected import / taxes vector.

        r m_i / r_i^m(k)  =  sum_j f_ij^m

    The chapter calls the two sides "equivalent mathematical expressions", so
    their disagreement is a bug. Returns the left-hand side; the caller should
    compare it with `result.Fm.sum(axis=1)`.
    """
    return result.r * np.asarray(m, float).ravel() / result.rm
