"""
SUT-EURO — `M-046`, UNH_18 §D.3 ¶18.89–18.102, pp. 575–577.

Project a square supply-use pair from macroeconomic aggregates alone — GVA by
industry, final use totals, total taxes less subsidies, total imports — when
industry outputs are not available. It is the third of the three methods
UNH_18 specifies, and the last one this project implemented.

DIFFERENT IN KIND FROM GRAS AND SUT-RAS
-----------------------------------------
`gras` and `sut_ras` are scaling methods: they minimise movement subject to
known margins. SUT-EURO has no margins to be subject to. ¶18.67, p. 566 places
it with the methods that "are not based on the minimization of some distance
function or some information loss principle, but rely on modelling
assumptions", and it buys its weaker data requirement with two of them:

  * **the fixed product sales structure model** (model D, `transformation.py`),
    which is what makes the tables consistent again after each scaling step;
  * **constant market shares** (¶18.89, p. 575).

Adopting SUT-EURO is adopting both. They are recorded in the result rather than
hidden in the code, because `../../CLAUDE.md` requires a method choice to carry
its reason.

THE LOOP, AND WHICH PARTS THE CHAPTER ACTUALLY WRITES DOWN
------------------------------------------------------------
Per iteration:

  1. **Scale** the base use table twice — once down the columns by each
     industry's GVA growth and each final-use category's growth, once across
     the rows by the growth of the industry whose primary output the product is
     — then take the cell-wise arithmetic mean (¶18.92–18.93, p. 576). The
     result is inconsistent **by design**: ¶18.94, p. 576 reports GDP from the
     use side at 258,432 against 257,346 from the supply side and does not
     repair it.
  2. **Restore consistency** with model D, holding the step-1 input structures
     and final uses fixed (¶18.95, p. 576): `x = (I − D·A)⁻¹ · D · f`.
  3. **Re-allocate** product output over industries at constant market shares
     (¶18.96, p. 576) to get the supply table.
  4. **Measure** each macroeconomic aggregate against its target and correct the
     growth rates by (E1) below (¶18.97, p. 577), applying the correction to the
     rates of the previous iteration and not to the original ones (¶18.100,
     p. 577).

Only (E1) is given in closed form. The scaling of step 1 and the recursion of
step 4 are prose, and what is written here is DERIVED from that prose plus the
printed tables of Box 18.7, pp. 578–579 — reproduced exactly for iteration 1,
see `run_sut_euro_austria.py`.

`ε` IS AN EXPONENT, NOT A TOLERANCE
-------------------------------------
¶18.97, p. 577 defines `ε = 0.9` as the exponent that damps the correction.
¶18.102, p. 577 then calls the same symbol "the tolerance level (ɛ)", and
Box 18.8, p. 580 gives the actual stopping rule as a 1 per cent difference with
no `ε` in it. The collision is the source's — `D_open_questions.md` OQ-B-10 —
and the consistent reading, adopted here, is that `ε` damps throughout. It is
called `damping_exponent` and never `tol` so that a reader coming fresh from the
chapter cannot reintroduce the confusion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


# Box 18.8, p. 580 branches on a 1 per cent difference. It is the only numeric
# convergence threshold the chapter states for any method except GRAS's
# illustrative 1e-8, and it is stated in a diagram rather than in the text.
STOP_PCT = 1.0

# PROJECT CHOICE. The chapter reports a run "after the fiftieth iteration"
# (¶18.101, p. 577) while Box 18.8's 1 per cent rule would have stopped far
# earlier; the two accounts are not reconciled (`M-046` LIMITATIONS). A limit is
# needed because nothing in the method guarantees the loop terminates.
#
# It was 200, chosen from a chapter whose own fixture converges in THREE. On
# real supply-use pairs that is nowhere near enough. Measured 2026-08-26,
# iterations to reach the chapter's own 1 per cent rule:
#
#     ES 2021 -> 2022     356        IT 2021 -> 2022   2,835
#     AT 2021 -> 2022     561        NL 2021 -> 2022   1,703
#     AT 2020 -> 2022   1,617
#
# At 200 every one of them stopped short — Austria at 9.4 per cent, Spain at
# 2.5 — and said "Converged in 200 iteration(s)", which was false and was the
# one sentence a reader would look at. Both halves of that are fixed: the
# ceiling is raised past what real data needs, and a run that reaches it now
# refuses instead of reporting.
PROJECT_MAX_ITER = 5000


class SutEuroError(ValueError):
    """The inputs do not describe a square SUT pair SUT-EURO can project."""


def correction_factor(dev, damping_exponent: float = 0.9):
    """(E1) — UNH_18 ¶18.97, p. 577, with `dev = actual / projected`.

        c = 1 + [(dev − 1)·100]^ε / 100      if dev > 1
        c = 1 − [(1 − dev)·100]^ε / 100      if dev < 1

    THE SECOND SIGN IS RECOVERED, NOT READ. The extraction renders both branches
    with a leading `1 +`, which would push the correction upward when the
    projection already overshoots — the wrong way, and it diverges. The minus is
    confirmed arithmetically against Box 18.7 table 9, p. 578, which prints the
    deviations beside the corrected rates: 0.9973 → 0.9969 and 0.9836 → 0.9844
    both follow from the minus branch and neither from the plus branch.

    At ε = 0.9 a 2.38 per cent deviation produces a 2.18 per cent correction —
    slightly less than a full one, which is what stops the outer loop
    oscillating.
    """
    dev = np.asarray(dev, dtype=float)
    gap = np.abs(dev - 1.0) * 100.0
    damped = np.power(gap, damping_exponent) / 100.0
    return np.where(dev >= 1.0, 1.0 + damped, 1.0 - damped)


@dataclass
class SutEuroStep1:
    """The inconsistent intermediate of ¶18.94, p. 576 — NOT a SUT.

    Kept as its own type rather than as a flag on the result, because the
    chapter is explicit that industry outputs do not equal industry inputs here
    and that GDP differs between the two sides. Nothing downstream should be
    able to mistake it for a table: it has no supply matrix and no output
    vector, and it carries the two GDP figures that disagree.
    """
    Ud: np.ndarray
    Um: np.ndarray
    tls: np.ndarray
    gva: np.ndarray
    gdp_supply_side: float
    gdp_use_side: float

    @property
    def inconsistency(self) -> float:
        return abs(self.gdp_use_side - self.gdp_supply_side)


@dataclass
class SutEuroResult:
    """A projected SUT pair, and everything needed to judge it."""
    Ud: np.ndarray                 # domestic use, products x (industries + final)
    Um: np.ndarray                 # imported use, same shape
    tls: np.ndarray                # taxes less subsidies, one row
    gva: np.ndarray                # by industry
    V: np.ndarray                  # supply, industries x products
    x: np.ndarray                  # industry output
    rates: dict                    # the growth rates actually used at the end
    deviations: dict               # actual / projected, per aggregate
    iterations: int
    converged: bool
    damping_exponent: float
    step1: SutEuroStep1            # the last iteration's inconsistent estimate
    assumptions: tuple = field(default=(
        "fixed product sales structure (model D, M-026)",
        "constant market shares (UNH_18 par. 18.89, p. 575)"))

    def __str__(self) -> str:
        mark = "CONVERGED" if self.converged else "NOT CONVERGED"
        worst = max(abs(v - 1.0) for v in self.deviations.values()) * 100
        return (f"[{mark}] SUT-EURO  iterations = {self.iterations}  "
                f"eps = {self.damping_exponent:g}\n"
                f"        worst deviation from the macro aggregates = "
                f"{worst:.3f} %\n"
                f"        assumed: {'; '.join(self.assumptions)}\n"
                f"        UNH_18 SS D.3 par. 18.89-18.102, pp. 575-577")


def _scaled_pair(U0, tls0, va0, rates, n_ind, impose_gva):
    """Step 1 of one iteration: the two scalings and their mean.

    Column scaling multiplies industry `j` by its own GVA growth and each final
    use column by its own; row scaling multiplies product `p` by the growth of
    the industry whose primary output it is (¶18.93, p. 576), and the taxes row
    by the taxes growth. `M-046` records that the same rates are applied to
    domestic and imported products, which is what ¶18.93 says to do "as starting
    values" — the chapter never says how they would later diverge, so they do
    not.
    """
    col = np.concatenate([rates["va"], rates["final_use"]])
    row = rates["va"]                               # square: product p ↔ industry p

    # The import shift is a ROW rate, and only a row rate. Column scaling is by
    # industry and by final-use category, which imported and domestic products
    # share; the row dimension is where product-specific rates live, so that is
    # where the two can diverge. Measured against Box 18.7's table 5(2): shifting
    # the row half misses the printed imported block by 1.8 on values up to
    # 1 050, shifting the whole block misses by 7.8.
    shift = np.array([1.0, rates["imports_shift"]])
    by_col = [U * col for U in U0]
    by_row = [U * (row * s)[:, None] if np.ndim(s) else U * row[:, None] * s
              for U, s in zip(U0, shift)]
    tls_col, tls_row = tls0 * col, tls0 * rates["tls"]

    U5 = [(a + b) / 2.0 for a, b in zip(by_col, by_row)]
    tls5 = (tls_col + tls_row) / 2.0

    # ¶18.93, p. 576 applies the domestic products' growth rates to the imported
    # ones too — but only "as STARTING values". The chapter never says how they
    # diverge afterwards, and `M-046` records that as NOT SPECIFIED. They have to
    # diverge somehow: table 9 measures total imports against their target, and
    # a deviation with no lever attached to it can never close. So the imported
    # block carries one multiplier of its own, starting at 1 — which reproduces
    # iteration 1 unchanged — and thereafter absorbing the import correction.
    # Box 18.7's own table 5(2) is what says this is right: its imported
    # agriculture row needs the second factor, and without it the block misses
    # the printed figures by ten times as much.

    # ¶18.92, p. 576: "except for GVA, which is set to the values of the
    # projected year". In the first iteration the rates ARE the targets, so that
    # is the target vector. Afterwards the rates have been corrected and the
    # projected year's GVA moves with them — the column scaling by each
    # industry's own rate, the row scaling by the total. Box 18.7's tables 3(2)
    # and 4(2) print 3 978 and 3 946 for agriculture, which is exactly those two
    # rules; the chapter states neither. DERIVED, and the arithmetic is in
    # `run_sut_euro_austria.py`.
    if impose_gva is not None:
        gva5 = impose_gva
    else:
        gva5 = (va0 * rates["va"] + va0 * rates["va_total"]) / 2.0
    return U5, tls5, gva5


def sut_euro(Ud0, Um0, tls0, V0, *, va_target, final_use_target, tls_target,
             imports_target, damping_exponent: float = 0.9,
             stop_pct: float = STOP_PCT,
             max_iter: int = PROJECT_MAX_ITER) -> SutEuroResult:
    """Project a square SUT pair. UNH_18 ¶18.89–18.102, pp. 575–577.

    Parameters
    ----------
    Ud0, Um0 : (p, n + k)
        Base-year domestic and imported use at basic prices — `n` industry
        columns then `k` final use columns.
    tls0 : (n + k,)
        Base-year taxes less subsidies on products, by column. May be negative:
        Box 18.7 carries −93 for agriculture throughout and the method neither
        removes it nor forbids it (`M-046` NEGATIVE_VALUES).
    V0 : (n, p)
        Base-year supply, industries by products. Its column shares are the
        market shares the method holds constant.
    va_target, final_use_target : arrays
        Projection-year GVA by industry and totals by final use category.
    tls_target, imports_target : float
        Projection-year totals.

    Raises
    ------
    SutEuroError
        On a non-square pair. ¶18.102, p. 577: the method "requires the number
        of industries and products to be equal ... it does not allow for
        rectangular SUTs estimation." This is a hard constraint, not a warning.
    """
    Ud0, Um0 = np.asarray(Ud0, float), np.asarray(Um0, float)
    tls0, V0 = np.asarray(tls0, float).ravel(), np.asarray(V0, float)
    va_target = np.asarray(va_target, float).ravel()
    final_use_target = np.asarray(final_use_target, float).ravel()

    n, p = V0.shape
    if n != p:
        raise SutEuroError(
            f"SUT-EURO needs as many industries as products and this pair has "
            f"{n} and {p} (UNH_18 par. 18.102, p. 577). Use SUT-RAS if the "
            f"industry outputs are known, or aggregate to a square pair and say "
            f"so in the method record.")
    k = Ud0.shape[1] - n
    if k < 1 or Um0.shape != Ud0.shape or tls0.size != n + k:
        raise SutEuroError(
            f"shapes do not describe one SUT pair: use {Ud0.shape}, imports "
            f"{Um0.shape}, taxes {tls0.shape}, supply {V0.shape}")

    q0 = V0.sum(axis=0)
    if np.any(q0 <= 0):
        raise SutEuroError("a product with no base-year output has no market "
                           "shares to hold constant")
    D = V0 / q0                                     # market shares, constant

    inputs0 = Ud0[:, :n].sum(0) + Um0[:, :n].sum(0) + tls0[:n]
    va0 = V0.sum(axis=1) - inputs0
    base = {
        "va": va0,
        "va_total": va0.sum(),
        "final_use": Ud0[:, n:].sum(0) + Um0[:, n:].sum(0) + tls0[n:],
        "tls": tls0.sum(),
        "imports": Um0.sum(),
    }
    target = {
        "va": va_target,
        "va_total": float(va_target.sum()),
        "final_use": final_use_target,
        "tls": float(tls_target),
        "imports": float(imports_target),
    }
    rates = {key: np.asarray(target[key], float) / np.asarray(base[key], float)
             for key in base}
    rates["imports_shift"] = 1.0     # see `_scaled_pair`: starts at parity

    result = None
    for iteration in range(1, max_iter + 1):
        # ---- step 1: scale, average, impose GVA -----------------------------
        impose = target["va"] if iteration == 1 else None
        (Ud5, Um5), tls5, gva5 = _scaled_pair((Ud0, Um0), tls0, va0, rates,
                                              n, impose)
        col_tot = Ud5[:, :n].sum(0) + Um5[:, :n].sum(0) + tls5[:n] + gva5
        step1 = SutEuroStep1(
            Ud=Ud5, Um=Um5, tls=tls5, gva=gva5,
            gdp_supply_side=float(gva5.sum() + tls5.sum()),
            gdp_use_side=float(Ud5[:, n:].sum() + Um5[:, n:].sum()
                               + tls5[n:].sum() - Um5.sum()))

        # ---- step 2: model D restores consistency ---------------------------
        A = Ud5[:, :n] / col_tot                    # domestic input structure
        f = Ud5[:, n:].sum(axis=1)                  # domestic final demand
        x = np.linalg.solve(np.eye(n) - D @ A, D @ f)

        # ---- step 3: rebuild at the consistent level ------------------------
        scale = x / col_tot
        Ud = np.column_stack([Ud5[:, :n] * scale, Ud5[:, n:]])
        Um = np.column_stack([Um5[:, :n] * scale, Um5[:, n:]])
        tls_new = np.concatenate([tls5[:n] * scale, tls5[n:]])
        gva = x - (Ud[:, :n].sum(0) + Um[:, :n].sum(0) + tls_new[:n])
        V = D * (Ud.sum(axis=1))                    # constant market shares

        # ---- step 4: measure, then correct the rates ------------------------
        achieved = {
            "va": gva,
            "va_total": float(gva.sum()),
            "final_use": Ud[:, n:].sum(0) + Um[:, n:].sum(0) + tls_new[n:],
            "tls": float(tls_new.sum()),
            "imports": float(Um.sum()),
        }
        projected = {key: np.asarray(achieved[key], float)
                     / np.asarray(base[key], float) for key in base}
        dev = {key: np.asarray(rates_actual, float) / projected[key]
               for key, rates_actual in
               {k2: target[k2] / np.asarray(base[k2], float)
                for k2 in base}.items()}

        worst = max(float(np.max(np.abs(np.atleast_1d(v) - 1.0)))
                    for v in dev.values()) * 100.0
        result = SutEuroResult(
            Ud=Ud, Um=Um, tls=tls_new, gva=gva, V=V, x=x,
            rates={key: np.copy(np.atleast_1d(v)) for key, v in rates.items()
                   if key != "imports_shift"},
            deviations={f"{key}[{i}]" if np.atleast_1d(v).size > 1 else key:
                        float(val)
                        for key, v in dev.items()
                        for i, val in enumerate(np.atleast_1d(v))},
            iterations=iteration, converged=worst < stop_pct,
            damping_exponent=damping_exponent, step1=step1)
        if result.converged:
            break

        # ¶18.100, p. 577: the correction multiplies the rates of the PREVIOUS
        # iteration, never the original ones. Every aggregate table 9 measures
        # is corrected here, and each correction reaches the tables through the
        # one lever that moves it: the industry rates scale the columns and the
        # domestic rows, the total-VA rate scales the GVA row of the row-scaled
        # table, the final-use rates scale their columns, the taxes rate scales
        # the taxes row, and the import shift scales the imported block.
        for key in ("va", "va_total", "final_use", "tls"):
            rates[key] = rates[key] * correction_factor(dev[key],
                                                        damping_exponent)
        rates["imports_shift"] = rates["imports_shift"] * correction_factor(
            dev["imports"], damping_exponent)
    return result
