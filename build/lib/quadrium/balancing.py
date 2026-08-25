"""
Balancing: RAS, GRAS, and the rule that chooses between them.

WHY THIS FILE DEPARTS FROM MVP_0.1 §7
-------------------------------------
The June spec balances with RAS and asserts `np.all(Z0 >= 0)`. That assertion
fires on any real IO table. Negatives are not errors in this framework
(`library/specs/A_core_accounting_spec.md` §A.8.1): trade and transport margins
sum to zero economy-wide through offsetting negative entries on the margin
industries' rows, subsidies are negative taxes, and inventory changes, valuables,
existing-goods transfers, merchanting and the CIF/FOB adjustment are all
legitimately negative. Running the project's validators against the UK 2023
analytical IOT — an official, already-balanced table — found negatives in five
separate blocks.

So the method is selected, not assumed, following `B_method_cards/M-047`:

    negatives present  ->  GRAS   (UNH_18 ¶18.35, p. 558)
    strictly non-negative -> RAS is admissible; GRAS still reproduces it
                             exactly, because RAS is the special case with N = 0

`select_method()` returns the choice **and the reason**, because a method choice
without a recorded reason is not finished work (`CLAUDE.md`).

THE SOLVER ITSELF IS NOT REIMPLEMENTED HERE
-------------------------------------------
`gras()` lives in `library/validators/gras.py`, where it is verified against the
UN Handbook's own worked example (UNH_18 Box 18.2, p. 568 → Box 18.3, p. 570)
by `library/validators/run_gras_austria.py`. Importing it rather than copying it
keeps one implementation and one test.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from .gras import DegenerateMarginError, SignInfeasibleError, gras
# Imported for the same reason `gras` is: one definition, one test. The rule for
# judging a solver's margins lives with the identity checks and is verified
# there (`run_tolerance_engine.py`); copying the number into the engine is how
# the two would drift apart.
from .identities import solver_margin_tolerance


class BalancingError(RuntimeError):
    """Raised when the requested method cannot be applied to this matrix."""


def select_method(Z: np.ndarray, requested: str = "GRAS") -> tuple[str, str]:
    """Choose the balancing method by domain, not by preference.

    Returns (method, reason). `B_method_cards/M-047` (C4): the eliminations are
    structural feasibility conditions, not tastes.
    """
    Z = np.asarray(Z, float)
    n_neg = int((Z < 0).sum())
    requested = requested.upper()

    if n_neg and requested == "RAS":
        raise BalancingError(
            f"RAS requested but the seed matrix has {n_neg} negative "
            f"cell(s). RAS 'can only be applied to non-negative matrices' "
            f"(CORE_012 Box 11.3, p. 345). Use GRAS, which 'allows for "
            f"positive and negative values in the initial tables and is sign "
            f"preserving' (UNH_18 ¶18.35, p. 558). Negatives in an IO table "
            f"are legitimate -- see A_core_accounting_spec.md §A.8.1 -- and "
            f"must not be zeroed to make a solver run."
        )
    if n_neg:
        return "GRAS", (f"{n_neg} negative cell(s) in the seed matrix; RAS is "
                        f"undefined there (CORE_012 Box 11.3, p. 345)")
    if requested == "RAS":
        return "RAS", "seed matrix is non-negative; RAS is admissible"
    return "GRAS", ("seed matrix is non-negative, so GRAS reduces exactly to "
                    "RAS (UNH_18 ¶18.35, p. 558); used for one code path")


def ras(Z0, target_row_sums, target_col_sums, locked_cells=None,
        tol: float = 1e-9, max_iter: int = 10_000):
    """Biproportional RAS with locked cells, as MVP_0.1 §7 specifies it.

    Kept because the spec defines it and because it is the readable form of the
    algorithm. `balance()` does not call it by default. Locked cells are
    re-imposed after EVERY half-step, not only at the end, or the next iteration
    moves them again.

    Returns (Z, converged, iterations).
    """
    Z0 = np.asarray(Z0, float)
    if np.any(Z0 < 0):
        raise BalancingError("RAS requires a non-negative seed; use GRAS "
                             "(CORE_012 Box 11.3, p. 345)")
    tr = np.asarray(target_row_sums, float)
    tc = np.asarray(target_col_sums, float)

    Z = Z0.copy()
    locked = {(i, j): Z0[i, j] for (i, j) in (locked_cells or [])}

    converged, it = False, 0
    for it in range(1, max_iter + 1):
        rs = Z.sum(axis=1)
        Z = Z * (tr / np.where(rs == 0, 1.0, rs))[:, None]
        for (i, j), v in locked.items():
            Z[i, j] = v
        cs = Z.sum(axis=0)
        Z = Z * (tc / np.where(cs == 0, 1.0, cs))[None, :]
        for (i, j), v in locked.items():
            Z[i, j] = v

        if max(np.max(np.abs(Z.sum(axis=1) - tr)),
               np.max(np.abs(Z.sum(axis=0) - tc))) < tol:
            converged = True
            break
    return Z, converged, it


def balance(Z_seed, target_row_sums, target_col_sums, *, method: str = "GRAS",
            tol: float = 1e-9, max_iter: int = 10_000, locked_cells=None):
    """Balance `Z_seed` onto the given row and column totals.

    Returns (Z_balanced, info). `info` carries the method, the reason it was
    chosen, convergence, iterations, the achieved margin deviations, the margin
    imbalance `sum(rows) - sum(cols)`, and the sign census -- everything needed
    to reproduce and to judge the run.

    It also carries the tolerance the achieved deviations are to be JUDGED by,
    because that tolerance is a function of the request and only this call has
    the request in hand. `margin_imbalance` was recorded here from the first
    version and read by nothing: when it is non-zero the totals asked for are
    unsatisfiable and part of the residual below belongs to them, which is
    exactly what `margin_tolerance` now accounts for (OQ-B-02 v1.57).
    """
    Z_seed = np.asarray(Z_seed, float)
    tr = np.asarray(target_row_sums, float).ravel()
    tc = np.asarray(target_col_sums, float).ravel()

    chosen, reason = select_method(Z_seed, method)
    imbalance = float(tr.sum() - tc.sum())

    if locked_cells and chosen == "GRAS":
        # GRAS as UNH_18 specifies it takes row and column totals and nothing
        # else -- no predefined interior cells. That capability belongs to TRAS
        # and KRAS, neither of which any loaded source specifies. Saying so is
        # better than silently approximating it.
        raise BalancingError(
            "locked cells were requested with GRAS. GRAS as specified in "
            "UNH_18 ¶18.81, p. 569 accepts only row and column totals; "
            "predefined interior cells belong to TRAS (¶18.44, p. 560) and "
            "KRAS (¶18.49, p. 561), which no loaded source specifies. "
            "See D_open_questions.md OQ-B-01. Either drop the locks, or use "
            "method='RAS' if the matrix is non-negative."
        )

    if chosen == "RAS":
        Z, converged, iters = ras(Z_seed, tr, tc, locked_cells, tol, max_iter)
        step = float("nan")
    else:
        try:
            res = gras(Z_seed, tr, tc, eps=tol, max_iter=max_iter)
        except (DegenerateMarginError, SignInfeasibleError) as exc:
            raise BalancingError(str(exc)) from None
        Z, converged, iters, step = res.X, res.converged, res.iterations, res.max_s_step

    info = {
        "method": chosen,
        "reason": reason,
        "converged": bool(converged),
        "iterations": int(iters),
        "solver_step": step,
        "tolerance": tol,
        "max_row_dev": float(np.max(np.abs(Z.sum(axis=1) - tr))),
        "max_col_dev": float(np.max(np.abs(Z.sum(axis=0) - tc))),
        "margin_imbalance": imbalance,
        "margin_tolerance": float(solver_margin_tolerance(tr, tc)),
        "n_negative_seed": int((Z_seed < 0).sum()),
        "n_negative_result": int((Z < 0).sum()),
        "sign_changes": int(np.count_nonzero(np.sign(Z) != np.sign(Z_seed))),
    }
    return Z, info
