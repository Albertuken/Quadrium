"""
GRAS — generalized RAS, as specified in UNH_18 (UN Handbook on SUT and IOT
2018, ch. 18, "Projecting supply, use and input-output tables").

This is the first balancing/projection algorithm in the project that is written
out by a source rather than merely named. Everything in this module is traceable
to UNH_18 §D.1 / ¶18.81, p. 569 (the seven steps) and Box 18.4, p. 571 (the
flow diagram). Nothing here is invented; where the source stops, the code raises
rather than guessing, and the exception names the gap.

WHY GRAS AND NOT RAS
--------------------
Plain RAS "can only be applied to non-negative matrices" (CORE_012 Box 11.3,
p. 345). Every real SUT or IOT this project has touched has negatives: the run
against the UK 2023 analytical IOT found them in five distinct blocks, all in an
official, already-balanced table. GRAS "allows for positive and negative values
in the initial tables and is sign preserving" (UNH_18 ¶18.35, p. 558), and
"The RAS method can be considered as a special case of the GRAS method" (ibid.).

THE ALGORITHM (UNH_18 ¶18.81, p. 569)
---------------------------------------
Step 1  Split the base table T into a non-negative P and a matrix N holding the
        negatives IN ABSOLUTE TERMS, so that  T = P − N.
Step 2  Starting from r = 1, form the column aggregates
            p_j(r) = Σ_i r_i · p_ij          n_j(r) = Σ_i n_ij / r_i
Step 3  s_j = [ v_j + sqrt( v_j² + 4·p_j(r)·n_j(r) ) ] / ( 2·p_j(r) )
        with v the projected COLUMN totals.
Step 4  p_i(s) = Σ_j p_ij · s_j              n_i(s) = Σ_j n_ij / s_j
Step 5  r_i = [ u_i + sqrt( u_i² + 4·p_i(s)·n_i(s) ) ] / ( 2·p_i(s) )
        with u the projected ROW totals.
Step 6  Repeat 2–5 until |s_j(k+1) − s_j(k)| < ε for all j.
Step 7  t_ij = r_i(k)·p_ij·s_j(k) − n_ij / ( r_i(k)·s_j(k) )

In matrix form that last line is the familiar  X = r̂ P ŝ − r̂⁻¹ N ŝ⁻¹.

THE TOLERANCE ε — READ THIS BEFORE REUSING THE NUMBER
------------------------------------------------------
UNH_18 gives ε only as an ILLUSTRATION, and gives it twice, inconsistently:

  * ¶18.81 Step 6, p. 569: "less than a certain threshold (for example 10-8) for
    all the elements. Convergence needs to be guaranteed."
  * ¶18.82, p. 569: "the projected IOTs after 11 iterations (or the imposition of
    a threshold of 10 -8)"
  * Box 18.3, p. 570, caption of the converged table: "After 11 iterations
    (threshold 0.0000001)" — that is 1e-7, not 1e-8.

So the chapter's own worked example disagrees with its own text by one order of
magnitude. GRAS_EPS below takes the value from the normative text (1e-8) and the
discrepancy is recorded in ../specs/D_open_questions.md OQ-B-06.

This ε is a convergence threshold on the SCALING FACTORS s — dimensionless
multipliers near 1. It is NOT an accounting tolerance and must never be copied
into identities.ABS_TOL / identities.REL_TOL, which are residuals in the table's
currency unit. Those remain PROJECT CHOICE; see OQ-B-02.

WHAT THE SOURCE DOES NOT SAY, AND WHAT THIS MODULE DOES ABOUT IT
-----------------------------------------------------------------
* p_j(r) = 0 or p_i(s) = 0 — an entirely non-positive column or row. Steps 3 and
  5 divide by it. The chapter flags the case twice ("Note that Temurshoev and
  others (2013) propose a different formulation in which p_j(r) = 0") and never
  writes that formulation down. ¶18.36, pp. 558–559 confirms it is real: "the row
  elements of trade industries in a trade margins matrix are always negative".
  -> SOLVED at v1.10, and not by obtaining that paper. The scaling factor is
     defined by Step 7's constraint `p*x - n/x = t`, which at p = 0 is linear,
     not undefined: `x = n/(-t)`. Steps 3 and 5 divide by `p` because they print
     the quadratic's root. See `_scaling_factor` and OQ-B-07. Refusing this
     meant refusing real published margins matrices -- the Austrian one has
     eight such rows.
* A zero or sign-changing target margin. GRAS is sign preserving by construction
  (Step 7 with r, s > 0), so a cell cannot cross zero; ¶18.33, pp. 557–558 names
  this as a drawback and points at Lenzen and others (2014) for the fix, which is
  not in the chapter. -> flagged in the report, not silently accepted.
* Any iteration limit. -> max_iter is a PROJECT CHOICE and is labelled.
* Any feasibility condition beyond "Convergence needs to be guaranteed"
  (¶18.81 Step 6, p. 569). Σu = Σv is necessary; the chapter never states it.
  -> CHECKED at v1.10 and refused: MarginImbalanceError. Still never repaired.
     The bound is each margin vector's own precision floor (OQ-B-02), because
     the chapter states none. This had been declared and never wired up; while
     a degenerate line raised first, infeasible margins were caught by
     accident, and solving that case exposed it.

Convergence is necessary but not sufficient for a usable result
(CORE_006 ¶9.51, p. 288; CORE_012 ¶11.105, pp. 342–343). Every value this module
produces has data status BALANCED and must never be relabelled OBSERVED.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from quadrium.precision import (  # noqa: E402
    assertable_tolerance, printed_decimals)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# SOURCED, with the caveat above: UNH_18 §D.1 / ¶18.81 Step 6, p. 569 and
# ¶18.82, p. 569. Illustrative ("for example"), not prescriptive.
GRAS_EPS = 1e-8

# The value Box 18.3, p. 570 actually used for its published run.
GRAS_EPS_BOX_18_3 = 1e-7

# PROJECT CHOICE. UNH_18 states no iteration limit anywhere; it says only
# "Convergence needs to be guaranteed" (¶18.81 Step 6, p. 569).
PROJECT_MAX_ITER = 10_000

# WAS a PROJECT CHOICE and was NEVER WIRED UP -- declared here and referenced
# nowhere, for as long as it existed. That went unnoticed because a degenerate
# row used to raise before the iteration started, so infeasible margins were
# being caught by accident. Solving the degenerate case (OQ-B-07) removed that
# accident and exposed the gap: `gras()` would run 10,000 iterations and drive
# the free scale factor to 1e+235 instead of saying the margins do not agree.
#
# And the value was wrong. UNH_18's OWN fixture, Box 18.2, p. 568, has
# Σu − Σv = 0.032, a relative 3.7e-08 -- so enforcing 1e-9 would have rejected
# the Handbook's own worked example. It is not an error: `u` is printed to three
# decimals and `v` to none, and a five-term sum of integers is entitled to 2.5
# on rounding alone.
#
# Replaced by the precision floor of OQ-B-02, applied to each margin vector
# SEPARATELY and added. Separately matters: run together, `printed_decimals`
# sees the finest precision present and understates the coarser vector's
# uncertainty -- 0.0065 instead of 2.504, which would still have rejected
# Box 18.2. See `_assert_margins_consistent`.
PROJECT_MARGIN_IMBALANCE_REL = None

# PROJECT CHOICE. Relative bound used only when BOTH margin vectors are
# unrounded, i.e. the caller computed them rather than reading them from a
# publication. The OQ-B-02 precision floor does not apply there -- see
# `_assert_margins_consistent`. Chosen four orders of magnitude above observed
# float64 accumulation on the project's fixtures and eleven below the smallest
# real imbalance the module has caught.
PROJECT_COMPUTED_MARGIN_REL = 1e-12


class SignInfeasibleError(ValueError):
    """A target margin whose sign the sign-preserving update rule cannot reach.

    DERIVED from the algebra of Step 7, not quoted from the source. With r, s > 0
    a row sums to  sum_j r_i p_ij s_j  -  sum_j n_ij /(r_i s_j). If that row has
    no negative part, the second term is zero and the sum is >= 0 for ANY r, s:
    a negative target is unattainable, not merely hard. Symmetrically, a row with
    no positive part can never reach a positive target.

    UNH_18 does not discuss the case. It is the margin-side counterpart of the
    sign-preservation limitation the chapter DOES name at par. 18.33, pp. 557-558
    -- "the cell value can switch sign between periods" -- and it is tracked as
    D_open_questions.md OQ-B-09.

    Raising is the honest behaviour: the alternative is a scaling factor of
    exactly zero, then a division by zero, then a table of NaN that looks like a
    solver failure when it is really an infeasible constraint set.
    """


class DegenerateMarginError(ValueError):
    """Retained for the callers that catch it; no longer raised for `p = 0`.

    It used to be raised whenever a row or column had a non-negative part
    summing to zero, on the grounds that UNH_18 ¶18.81 Steps 3 and 5, p. 569
    divide by `p_j(r)` and `p_i(s)` and the chapter names a different
    formulation (Temurshoev and others, 2013) without reproducing it.

    **That was one step too cautious.** See `_scaling_factor`: the case is
    solvable from the chapter's own Step 7, and refusing it meant refusing real
    published tables. Kept as a class so existing `except` clauses still
    compile; a genuinely unreachable target now raises `SignInfeasibleError`,
    which is what it always was.
    """


@dataclass
class GrasResult:
    X: np.ndarray                    # the projected table, status BALANCED
    r: np.ndarray                    # row scaling factors at convergence
    s: np.ndarray                    # column scaling factors at convergence
    iterations: int
    converged: bool
    eps: float
    max_s_step: float                # |s(k+1) − s(k)|_inf at the last iteration
    max_row_dev: float               # |X·1 − u|_inf
    max_col_dev: float               # |1ᵀ·X − v|_inf
    margin_imbalance: float          # Σu − Σv, reported, never repaired
    sign_changes: int                # cells whose sign differs from the base
    history: list = field(default_factory=list)   # per-iteration diagnostics

    def __str__(self) -> str:
        mark = "CONVERGED" if self.converged else "NOT CONVERGED"
        return (
            f"[{mark}] GRAS  iterations = {self.iterations}  eps = {self.eps:g}\n"
            f"        |s(k+1)-s(k)|_inf = {self.max_s_step:.3e}\n"
            f"        max |row total - u| = {self.max_row_dev:.6g}\n"
            f"        max |col total - v| = {self.max_col_dev:.6g}\n"
            f"        margin imbalance (sum u - sum v) = {self.margin_imbalance:.6g}\n"
            f"        sign changes vs base table = {self.sign_changes}\n"
            f"        UNH_18 SS D.1 / par. 18.81, p. 569; Box 18.4, p. 571"
        )


def split_pn(T: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Step 1 — T = P − N, N holding the negatives in absolute terms.

    UNH_18 ¶18.81 Step 1, p. 569: "The IOTs (T) must be split up into a matrix
    P with non-negative values and a matrix N with negative values in absolute
    terms, see Box 18.4. This means that: T = P – N."
    """
    T = np.asarray(T, dtype=float)
    P = np.where(T > 0.0, T, 0.0)
    N = np.where(T < 0.0, -T, 0.0)
    return P, N


def _scaling_factor(target: np.ndarray, p: np.ndarray, n: np.ndarray,
                    axis_name: str) -> np.ndarray:
    """The positive root shared by Steps 3 and 5 (UNH_18 ¶18.81, p. 569).

        x = [ t + sqrt( t² + 4·p·n ) ] / ( 2·p )

    It is the positive solution of  p·x − n/x = t,  which is Step 7 aggregated
    along the axis being scaled. Where n = 0 it collapses to t/p, i.e. plain RAS
    — the chapter's own statement that "The RAS method can be considered as a
    special case of the GRAS method" (¶18.35, p. 558).

    THE `p = 0` CASE, WHICH THIS PROJECT USED TO REFUSE (`OQ-B-07`)
    ---------------------------------------------------------------
    An entirely non-positive row or column makes `p = 0` and Steps 3 and 5
    divide by it. Both steps footnote that "Temurshoev and others (2013) propose
    a different formulation in which p_j(r) = 0" and the chapter never gives it,
    so this module raised rather than guess.

    **No alternative formulation is needed.** The quantity being solved for is
    not defined by the printed root; it is defined by the CONSTRAINT the root
    solves, `p·x − n/x = t`, which is Step 7 aggregated. At `p = 0` that
    constraint does not vanish — it stops being quadratic and becomes linear:

        −n/x = t        =>        x = n / (−t),  the unique positive solution
                                  whenever n > 0 and t < 0.

    Steps 3 and 5 divide by `p` because they print the root of the quadratic,
    not because the problem requires `p > 0`. This is DERIVED from the
    chapter's own Step 7, and it is verified two ways in
    `run_gras_degenerate.py`: it satisfies the constraint exactly, and it is the
    limit of the printed root as `p → 0⁺`.

    It is **not** claimed to be Temurshoev's formulation, which is still
    unobtained (`CORE_042`) and which also treats infeasible RAS cases this does
    not. The claim is narrower and sufficient: the degenerate case has one
    positive solution and this is it.

    AND IT IS BETTER THAN THE WORKAROUND THE CHAPTER REPORTS. ¶18.36, p. 559
    notes that "small positive numbers are often added to the initial table in
    order to guarantee convergence". Besides perturbing OBSERVED data, that is
    numerically worse: with `t < 0` the printed root loses precision to
    cancellation in `t + sqrt(t² + 4pn)`, and by `p = 1e-10` it is further from
    the true answer than at `p = 1e-6`. Solving the degenerate case exactly is
    both more honest and more accurate.

    Remaining `p = 0` cases have no positive solution at all and raise
    `SignInfeasibleError`: `t > 0` (an all-non-positive line cannot reach a
    positive total) and `t = 0` with `n > 0` (it would need `x → ∞`).
    """
    target = np.asarray(target, float)
    p = np.asarray(p, float)
    n = np.asarray(n, float)
    x = np.empty(target.shape, float)

    regular = p > 0.0
    disc = target * target + 4.0 * p * n
    # disc >= 0 whenever p, n >= 0, which split_pn guarantees.
    x[regular] = ((target[regular] + np.sqrt(disc[regular]))
                  / (2.0 * p[regular]))

    deg = ~regular
    if deg.any():
        solvable = deg & (n > 0.0) & (target < 0.0)
        empty = deg & (n <= 0.0) & (target == 0.0)
        unreachable = deg & ~solvable & ~empty
        if unreachable.any():
            i = int(np.flatnonzero(unreachable)[0])
            raise SignInfeasibleError(
                f"{axis_name} {i}: the non-negative part sums to zero and the "
                f"target is {target[i]:.6g}. An entirely non-positive "
                f"{axis_name} sums to -n/x < 0 for every x > 0, so no positive "
                f"scaling factor reaches that target. "
                f"{int(unreachable.sum())} {axis_name}(s) affected. This is an "
                f"infeasible constraint set, not the `p = 0` case OQ-B-07 was "
                f"about -- that one is solved here."
            )
        x[solvable] = n[solvable] / (-target[solvable])
        x[empty] = 1.0          # the line is identically zero; any factor works
    return x


class MarginImbalanceError(ValueError):
    """Row margins and column margins that do not sum to the same total.

    GRAS projects a table onto both at once, so `Σu = Σv` is a precondition and
    not something the solver can reconcile. Reported for as long as this module
    has existed and never CHECKED, which was survivable only while a degenerate
    line raised first. It does not any more (`OQ-B-07`), and without this the
    symptom is 10,000 iterations and a scale factor of 1e+235.
    """


def _assert_margins_consistent(u, v, margin_floor: float | None = None) -> None:
    """Refuse margins that cannot both be met, at the precision they carry.

    The bound is the OQ-B-02 floor, applied to each vector separately and
    added, because `Σu` and `Σv` are independent sums of independently rounded
    figures. Below it the two totals agree as closely as their own publication
    permits; above it they disagree, and no scaling can fix that.
    """
    imbalance = float(u.sum() - v.sum())
    # PUBLISHED margins get the OQ-B-02 precision floor, per vector and added.
    # COMPUTED margins cannot: `assertable_tolerance`'s float64 branch bounds the
    # error of summing the vector it is given, and a margin that is itself a row
    # or column sum arrives already carrying error that no bound on the last
    # operation can see. The first version ignored that and refused a synthetic
    # fixture whose margins summed to 12 and 12 with a difference of 2.7e-14.
    # Widening the float64 branch did not fix it and could not: even the textbook
    # `(n-1)*u*sum|x|` bound comes out below the observed residual. The floor is
    # sound for published data, which is what it was derived for, and overreached
    # everywhere else.
    # THE MARGINS' OWN DECIMALS ARE NOT THE SOURCE'S, AND THEIR LENGTH IS NOT
    # THE NUMBER OF FIGURES BEHIND THEM.
    #
    # A margin handed to this solver is rarely something a publisher printed.
    # It is a published cell multiplied by a weight, or a published total minus
    # a sum over sixty-odd published cells. Two things follow, and the first
    # version of this check got both wrong:
    #
    #   * the DECIMALS are an artefact of the arithmetic -- seven where the
    #     publisher printed two -- so inferring `d` from the values bounds the
    #     wrong quantity, far too tightly;
    #   * the TERM COUNT is `u.size`, which is 2 for a two-way split, when the
    #     rounding those two numbers carry was accumulated over the ~65 cells
    #     each of them was formed from.
    #
    # Measured on 2026-08-25: splitting one sector of the Portuguese symmetric
    # table, published to two decimals, gave margins summing to 221.53 and
    # 221.56. The 0.03 difference is an ordinary published table's row and
    # column disagreeing by less than its own rounding allows -- the table's
    # own floor is 0.37. Inferring from the products refused it at 1.1e-05;
    # counting two terms instead of two-times-sixty-five refused it at 0.02.
    #
    # Only the caller knows what the margins were built from, so the caller
    # supplies the bound. `scenarios.py` does, from the source table's printed
    # precision and the number of its cells that went into each margin.
    if margin_floor is not None:
        floor = float(margin_floor)
    elif printed_decimals(u) is None and printed_decimals(v) is None:
        # PROJECT CHOICE, and labelled as one. No loaded source states a bound
        # for margins the caller computed rather than read.
        floor = PROJECT_COMPUTED_MARGIN_REL * max(abs(u.sum()), abs(v.sum()), 1.0)
    else:
        floor = (assertable_tolerance(u, u.size)
                 + assertable_tolerance(v, v.size))
    if abs(imbalance) > floor:
        raise MarginImbalanceError(
            f"the row margins sum to {u.sum():,.6g} and the column margins to "
            f"{v.sum():,.6g}, a difference of {imbalance:,.6g}. That is beyond "
            f"the {floor:,.6g} their own printed precision allows, so they are "
            f"mutually infeasible: GRAS meets both or neither. Reconcile the "
            f"margins before projecting. (UNH_18 states no bound; this one is "
            f"derived from the sources' precision -- see OQ-B-02.)"
        )


def sign_pattern_feasible(T, u, v) -> tuple[bool, str]:
    """Can ANY table with T's sign pattern have row totals `u` and column `v`?

    This is the answerable half of `OQ-B-09`, which asks "whether a sign change
    in the target margins is detectable in advance from the base table and the
    margins alone". It is, exactly, and it is a linear feasibility problem.

    GRAS preserves signs cell by cell (Step 7 with r, s > 0), so it can only ever
    return a table whose sign pattern is T's. The question of whether the
    requested projection needs a sign change is therefore the question of whether
    the constraint set

        X_ij = sign(T_ij) * x_ij,   x_ij >= 0 on supp(T),
        X 1 = u,    1' X = v

    has a solution. That is an LP.

    STRICTLY STRONGER THAN `_assert_sign_feasible`, which tests one line at a
    time and is necessary but not sufficient. The smallest separating case is
    2x2:

        T = [[+1, 0], [0, -1]],   u = (200, -100),   v = (300, -200)

    Every line passes on its own -- the all-positive row has a positive target,
    the all-negative row a negative one, likewise the columns, and the margins
    sum to the same total. It is still infeasible: the single positive cell has
    to equal 2 and 3 at once.

    ONE CAVEAT, AND IT IS THE HONEST DIRECTION OF THE TEST. The LP allows
    `x = 0`; GRAS's factors are strictly positive, so it needs the relative
    interior. **Infeasible here means GRAS certainly cannot do it** -- a sound
    refusal. Feasible here means the sign pattern is not the obstruction; it does
    not promise convergence.

    Returns `(True, "")` when scipy is unavailable, with the reason: the project
    is otherwise numpy-only and this is not worth a hard dependency. The per-line
    test in `_assert_sign_feasible` always runs regardless.

    Costs 17 ms on a 65x72 table, 127 ms on 104x113.
    """
    try:
        from scipy.optimize import linprog
    except ImportError:
        return True, "scipy unavailable; only the per-line test was applied"
    T = np.asarray(T, float)
    sign = np.sign(T)
    idx = np.argwhere(sign != 0)
    if idx.size == 0:
        return True, "empty support"
    m, n = T.shape
    A = np.zeros((m + n, len(idx)))
    for k, (i, j) in enumerate(idx):
        A[i, k] = A[m + j, k] = sign[i, j]
    # EACH MARGIN IS A PUBLISHED FIGURE AND CARRIES ITS OWN ROUNDING, so the
    # constraints are a band and not an equality. The first draft used `A_eq`
    # and declared UNH_18's OWN Box 18.2 fixture infeasible: its margins are
    # printed to different precisions and miss each other by 0.032, and an
    # equality system with Sigma-u != Sigma-v is infeasible by construction --
    # sum the row rows and the column rows and they contradict. The band is the
    # OQ-B-02 floor for a SINGLE published figure, per vector.
    u, v = np.ravel(u), np.ravel(v)
    tol = np.concatenate([np.full(m, assertable_tolerance(u, 1)),
                          np.full(n, assertable_tolerance(v, 1))])
    b = np.concatenate([u, v])
    res = linprog(np.zeros(len(idx)),
                  A_ub=np.vstack([A, -A]),
                  b_ub=np.concatenate([b + tol, -(b - tol)]),
                  bounds=(0, None), method="highs")
    if res.status == 0:
        return True, ""
    return False, (
        "no table with this sign pattern has those margins, so the projection "
        "requires at least one cell to change sign. GRAS cannot: it is sign "
        "preserving by construction (UNH_18 par. 18.35, p. 558). UNH_18 "
        "par. 18.33, pp. 557-558 names the cells this happens to -- taxes less "
        "subsidies on products and changes in inventories -- and points at "
        "Lenzen and others (2014), which this project does not hold. See "
        "OQ-B-09."
    )


def _assert_sign_feasible(P, N, u, v) -> None:
    """Refuse target margins the sign-preserving rule provably cannot reach.

    See SignInfeasibleError. Checked before iterating, because the symptom
    otherwise is a zero scaling factor and a table of NaN several steps later.
    """
    for axis, targets, label in ((1, u, "row"), (0, v, "column")):
        pos = P.sum(axis=axis)
        neg = N.sum(axis=axis)
        bad_neg = np.flatnonzero((neg <= 0) & (targets < 0))
        bad_pos = np.flatnonzero((pos <= 0) & (targets > 0))
        for idx, why, sign in ((bad_neg, "no negative entries", "negative"),
                               (bad_pos, "no positive entries", "positive")):
            if idx.size:
                i = int(idx[0])
                raise SignInfeasibleError(
                    f"{label} {i} has {why}, so a sign-preserving method can "
                    f"never make it sum to the {sign} target {targets[i]:.6g}. "
                    f"This is an infeasible constraint set, not a solver "
                    f"failure: GRAS preserves signs by construction "
                    f"(UNH_18 par. 18.35, p. 558), so the target must be "
                    f"reachable from the seed's sign structure. "
                    f"{idx.size} {label}(s) affected. See OQ-B-09."
                )


def quadratic_scaling_factor(target, p, n, axis_name: str = "axis"):
    """Public entry point to the root shared by GRAS and SUT-RAS.

    `sut_ras.py` reuses it: UNH_18 par. 18.86, p. 572 applies the same
    positive root of `p*x - n/x = t` to the industry-output and use-column
    factors, and applies it at t = 0 for the product rows, where it collapses
    to sqrt(n/p).
    """
    return _scaling_factor(target, p, n, axis_name)


def is_connected(T) -> tuple[bool, list]:
    """Bacharach's connectedness, and the blocks if it fails.

    CORE_016 p. 110 defines it: "A matrix is called disconnected if rows and
    columns can be ordered, in at least one way, so it can be expressed as a
    block-diagonal matrix... A matrix is called connected if it is not
    disconnected."

    WHY IT MATTERS, AND WHY THIS PROJECT NEEDED IT. CORE_016 p. 109 states the
    guarantee: Bacharach (1965) "proves that if a matrix is connected, then a
    solution of the RAS-type problem is unique if the sum of the row targets
    matches the sum of the column targets of the matrix."

    That is a **sufficient condition for uniqueness**, and this library had none.
    `../../CLAUDE.md` records that convergence is necessary and not sufficient
    (CORE_006 par. 9.51, p. 288); the module has been able to say when a solver
    stopped moving and never whether the answer it stopped at was the only one.
    Connected + matching margins now says so.

    Implemented as connectivity of the bipartite graph whose edges are the
    non-zero cells: rows and columns are the two vertex sets, and a permutation
    to block-diagonal form exists exactly when that graph is disconnected.

    Returns `(connected, components)` where each component is
    `(row_indices, col_indices)`. A fully zero row or column is its own
    component and makes the matrix disconnected, which is correct: nothing ties
    it to the rest.
    """
    T = np.asarray(T, float)
    m, n = T.shape
    seen_r, seen_c, comps = set(), set(), []
    nz_rows = [np.flatnonzero(T[i] != 0) for i in range(m)]
    nz_cols = [np.flatnonzero(T[:, j] != 0) for j in range(n)]
    for start in range(m):
        if start in seen_r:
            continue
        rq, cq, rs, cs = [start], [], {start}, set()
        while rq or cq:
            while rq:
                i = rq.pop()
                for j in nz_rows[i]:
                    if j not in cs:
                        cs.add(int(j))
                        cq.append(int(j))
            while cq:
                j = cq.pop()
                for i in nz_cols[j]:
                    if i not in rs:
                        rs.add(int(i))
                        rq.append(int(i))
        seen_r |= rs
        seen_c |= cs
        comps.append((sorted(rs), sorted(cs)))
    stray = [c for c in range(n) if c not in seen_c]
    for c in stray:
        comps.append(([], [c]))
    return len(comps) == 1, comps


def mras(T, u, v, known: dict, **kw) -> "GrasResult":
    """RAS/GRAS with cells the analyst already knows. CORE_016 p. 116.

    This is the join `OQ-B-01` has been asking for since v1.2. The project could
    compute a reliability map -- `pinned` / `restricted` / `free`, `M-032` -- and
    had no specified method that could read one: "The RAS method does not allow
    the use of relative reliabilities" (UNH_18 par. 18.33, p. 558). `pinned` is
    the half that a method CAN take, and CORE_016 p. 116 supplies it, attributing
    it to Paelinck and Waelbroeck (1963) as M-RAS:

      "allowing any predetermined (known) elements to be initially set to zero in
      the matrix. Subsequently, target adjustments are made to reflect the
      presence of these known elements. Following these modifications, the M-RAS
      algorithm is executed to find a solution, after which the zero placeholders
      are replaced with the pre-known values."

    Four steps, exactly as written: zero the known cells, subtract their values
    from both margins, solve, put them back.

    `known` maps `(i, j)` to the value. Everything else is `gras()`'s contract,
    including its refusals -- which now bite more often, and the source says so:
    fixed elements "inherently limit the degrees of freedom... potentially
    transforming the optimisation problem into an infeasible one" (CORE_016 p. 116).

    THE RESIDUE OF OQ-B-01 IS NARROWED, NOT CLOSED. `restricted` -- a cell that
    may move but not freely -- still has no method. CORE_016 p. 116 goes as far
    as saying that where known values and targets conflict "either the target
    values or the additional information must be reconciled, potentially
    requiring a compromise, especially when both sets of information are less
    reliable", and specifies no compromise.
    """
    T = np.asarray(T, float).copy()
    u_full = np.asarray(u, float)
    v_full = np.asarray(v, float)
    u, v = u_full.copy(), v_full.copy()
    for (i, j), value in known.items():
        T[i, j] = 0.0
        u[i] -= value
        v[j] -= value
    res = gras(T, u, v, **kw)
    for (i, j), value in known.items():
        res.X[i, j] = value
    # Deviations are reported against the margins the CALLER asked for, not
    # against the reduced ones the solver saw.
    res.max_row_dev = float(np.abs(res.X.sum(1) - u_full).max())
    res.max_col_dev = float(np.abs(res.X.sum(0) - v_full).max())
    return res


def gras(T, u, v, *, eps: float = GRAS_EPS, max_iter: int = PROJECT_MAX_ITER,
         margin_floor: float | None = None) -> GrasResult:
    """Project base table `T` onto row totals `u` and column totals `v`.

    Parameters
    ----------
    T : (m, n) array_like
        The base table. May contain negatives and zeros. Status OBSERVED or
        BALANCED; it is not modified.
    u : (m,) array_like
        Projected ROW totals for the target period (UNH_18 Box 18.4, p. 571:
        "u = projected row totals").
    v : (n,) array_like
        Projected COLUMN totals ("v = projected column totals", ibid.).
    eps : float
        Convergence threshold on the column scaling factors, Step 6. Defaults to
        the chapter's illustrative 1e-8. See the module docstring.
    max_iter : int
        PROJECT CHOICE. The chapter states no limit.

    Returns
    -------
    GrasResult — every cell of `X` has data status BALANCED.
    """
    T = np.asarray(T, dtype=float)
    u = np.asarray(u, dtype=float).ravel()
    v = np.asarray(v, dtype=float).ravel()
    if T.ndim != 2:
        raise ValueError("T must be two-dimensional")
    if T.shape != (u.size, v.size):
        raise ValueError(f"shape mismatch: T is {T.shape}, u is {u.size}, "
                         f"v is {v.size}")

    _assert_margins_consistent(u, v, margin_floor)
    P, N = split_pn(T)

    # A TARGET BELOW THE FLOOR, ON A LINE THAT IS ENTIRELY ZERO, IS ZERO.
    #
    # Three sign tests below compare a target against exact zero -- the
    # per-line one here, the exhaustive one after it, and `_scaling`'s
    # `target == 0.0` for an empty line. The caller already computes the
    # tightest residual this problem's own numbers can be held to and passes it
    # as `margin_floor` (`precision.assertable_tolerance`, via
    # `balancing.balance`), and `_assert_margins_consistent` uses it one line
    # above -- but these did not, so a margin the source cannot distinguish
    # from zero was read as a sign the seed could never match.
    #
    # It cost three real splits of `Q87_88`, health and social work, whose
    # parent has NO internal sales: the block is exactly zero, its targets are
    # the rounding of a difference of large sums, and Hungary 2022 was refused
    # over -2.8e-14 while France 2021 was refused over -0.021, against a floor
    # of the order of a tenth. Snapped here, once, so every test downstream
    # sees the same consistent problem -- and only where the seed line is
    # empty, because a small target on a line with mass IS a constraint.
    if margin_floor:
        floor = abs(float(margin_floor))
        empty_r = (P.sum(axis=1) <= 0) & (N.sum(axis=1) <= 0)
        empty_c = (P.sum(axis=0) <= 0) & (N.sum(axis=0) <= 0)
        u = np.where(empty_r & (np.abs(u) <= floor), 0.0, u)
        v = np.where(empty_c & (np.abs(v) <= floor), 0.0, v)

    _assert_sign_feasible(P, N, u, v)
    # The exact version of the same question, which the per-line test above can
    # pass while the system is still infeasible. Costs 17 ms on a 65x72 table
    # and converts a silently wrong table into a stated refusal, which is the
    # trade this project makes everywhere else. Degrades to a no-op without
    # scipy; the per-line test has already run either way. See OQ-B-09.
    feasible, why = sign_pattern_feasible(T, u, v)
    if not feasible:
        raise SignInfeasibleError(f"{why} (exact test, not the per-line one)")

    # Reported, never repaired. Sum(u) == Sum(v) is necessary for the two
    # constraint sets to be simultaneously satisfiable; UNH_18 says only
    # "Convergence needs to be guaranteed" (par. 18.81 Step 6, p. 569) and states
    # no feasibility condition.
    margin_imbalance = float(u.sum() - v.sum())

    m, n = T.shape
    r = np.ones(m)
    s_prev = np.ones(n)
    history: list[dict] = []
    converged = False
    max_s_step = np.inf
    k = 0

    for k in range(1, max_iter + 1):
        # Step 2 — column aggregates under the current r.
        p_j = P.T @ r
        n_j = N.T @ (1.0 / r)
        # Step 3 — new column factors against the projected column totals.
        s = _scaling_factor(v, p_j, n_j, "column")
        # Step 4 — row aggregates under the new s.
        p_i = P @ s
        n_i = N @ (1.0 / s)
        # Step 5 — new row factors against the projected row totals.
        r = _scaling_factor(u, p_i, n_i, "row")

        # Step 6 — the stopping rule is on s, element-wise.
        max_s_step = float(np.max(np.abs(s - s_prev)))
        history.append({
            "iteration": k,
            "p_j": p_j.copy(), "n_j": n_j.copy(), "s": s.copy(),
            "p_i": p_i.copy(), "n_i": n_i.copy(), "r": r.copy(),
            "max_s_step": max_s_step,
        })
        s_prev = s
        if max_s_step < eps:
            converged = True
            break

    s = s_prev
    # Step 7 — reconstruct. r̂ P ŝ − r̂⁻¹ N ŝ⁻¹.
    X = (r[:, None] * P * s[None, :]) - (N / (r[:, None] * s[None, :]))

    # GRAS is sign preserving (par. 18.35, p. 558): with r, s > 0 no cell can
    # cross zero. Verified rather than assumed -- a nonzero count here means the
    # implementation, not the table, is wrong.
    sign_changes = int(np.count_nonzero(np.sign(X) != np.sign(T)))

    return GrasResult(
        X=X, r=r, s=s, iterations=k, converged=converged, eps=eps,
        max_s_step=max_s_step,
        max_row_dev=float(np.max(np.abs(X.sum(axis=1) - u))),
        max_col_dev=float(np.max(np.abs(X.sum(axis=0) - v))),
        margin_imbalance=margin_imbalance,
        sign_changes=sign_changes,
        history=history,
    )
