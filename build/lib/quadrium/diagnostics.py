"""
Technical coefficients, the Leontief inverse, and output multipliers.

MVP_0.1 §10, with two corrections carried over from the methodology ingestion.

1. **The Leontief expansion keeps its leading identity term.** CORE_005 ¶36.39,
   p. 1016 prints the series without it; the project implements `I + A + A² + …`,
   the only form consistent with `x = (I − A)^-1 y` at ¶36.36 of the same source.
   Verified numerically. `D_open_questions.md` OQ-A-01.

2. **`A` may contain negative coefficients, and `(I − A)^-1` is not guaranteed
   to behave.** CORE_005 ¶36.63, p. 1019: transformation models A and C may
   produce negatives, and no loaded source says what the inverse means then.
   `leontief_inverse` reports the condition number and the negative census
   rather than pretending the question does not arise.
"""

from __future__ import annotations

import numpy as np


def technical_coefficients(Z: np.ndarray, X: np.ndarray) -> np.ndarray:
    """a_ij = Z_ij / X_j. Columns with zero output give NaN, not a division error."""
    X = np.asarray(X, float)
    X_safe = np.where(np.abs(X) < 1e-12, np.nan, X)
    return np.asarray(Z, float) / X_safe[None, :]


def leontief_inverse(A: np.ndarray) -> tuple[np.ndarray, dict]:
    """(I - A)^-1, with the diagnostics needed to judge whether to trust it."""
    A = np.asarray(A, float)
    A = np.nan_to_num(A, nan=0.0)
    n = A.shape[0]
    M = np.eye(n) - A
    cond = float(np.linalg.cond(M))
    L = np.linalg.inv(M)
    info = {
        "condition_number": cond,
        "n_negative_coefficients": int((A < 0).sum()),
        "max_column_sum": float(np.max(A.sum(axis=0))),
        "spectral_radius": float(max(abs(np.linalg.eigvals(A)))),
    }
    return L, info


def output_multipliers(L: np.ndarray) -> np.ndarray:
    """Column sums of the Leontief inverse: total output per unit of final demand."""
    return np.asarray(L, float).sum(axis=0)


def compute(Z: np.ndarray, X: np.ndarray) -> dict:
    A = technical_coefficients(Z, X)
    L, info = leontief_inverse(A)
    return {"A": A, "L": L, "multipliers": output_multipliers(L), **info}


def compare_scenarios(results: dict[str, np.ndarray],
                      codes: list[str]) -> list[dict]:
    """Multiplier by subsector across scenarios, with the range.

    `results` maps scenario_id -> multiplier vector.
    """
    ids = list(results)
    rows = []
    for i, code in enumerate(codes):
        vals = {sid: float(results[sid][i]) for sid in ids}
        lo, hi = min(vals.values()), max(vals.values())
        rows.append({"code": code, **vals, "range": hi - lo,
                     "range_pct": 100.0 * (hi - lo) / lo if lo else float("nan")})
    return rows


def variation_driver(Z_by_scenario: dict[str, np.ndarray],
                     codes: list[str]) -> tuple[str, float]:
    """The Z cell with the largest spread across scenarios (MVP_0.1 §10).

    Deliberately crude: the maximum absolute range, not a sensitivity analysis.
    Enough to point at where the disagreement lives without claiming precision.
    """
    stack = np.stack(list(Z_by_scenario.values()))
    spread = stack.max(axis=0) - stack.min(axis=0)
    i, j = np.unravel_index(int(np.argmax(spread)), spread.shape)
    return f"{codes[i]} -> {codes[j]}", float(spread[i, j])


def input_structure_divergence(A: np.ndarray, new_positions: list[int],
                               codes: list[str],
                               profiled: bool = False) -> dict:
    """How much do the new subsectors actually differ as buyers?

    This is the question the whole disaggregation exists to answer, and the one
    it silently fails to answer when a single allocation key is used for every
    block. In that case each subsector's column of technical coefficients is
    identical to the parent's — the weight cancels in `a_ij = Z_ij / X_j` — so
    the subsectors differ in size and in nothing else, and their multipliers are
    equal by construction rather than by finding.

    Reported as the maximum absolute difference between any two subsectors'
    coefficient columns, and as the mean pairwise cosine distance, which is
    scale-free. Near zero means the split carries no information about input
    structure, whatever the multipliers table appears to show.
    """
    cols = [np.nan_to_num(A[:, j]) for j in new_positions]
    if len(cols) < 2:
        return {"max_abs_difference": 0.0, "mean_cosine_distance": 0.0,
                "differentiated": False, "profiled": bool(profiled),
                "n_subsectors": len(cols)}
    max_abs, cosines = 0.0, []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            max_abs = max(max_abs, float(np.max(np.abs(cols[i] - cols[j]))))
            na, nb = np.linalg.norm(cols[i]), np.linalg.norm(cols[j])
            if na > 0 and nb > 0:
                cosines.append(1.0 - float(cols[i] @ cols[j] / (na * nb)))
    mean_cos = float(np.mean(cosines)) if cosines else 0.0
    return {
        "max_abs_difference": max_abs,
        "mean_cosine_distance": mean_cos,
        # FACTUAL, not a threshold. An earlier version compared the cosine
        # distance against a cut-off, which was arbitrary in both directions:
        # a single key still leaves a tiny residue (the internal block's alpha
        # damping moves each diagonal), and a genuine profile on a sector with
        # little internal trade produces a small but real difference. The
        # honest binary is whether the analyst supplied an input profile; the
        # magnitude above says how much difference it made, and the reader
        # judges whether that is enough to matter.
        "differentiated": bool(profiled),
        "profiled": bool(profiled),
        "n_subsectors": len(cols),
        "by_subsector": {codes[k]: float(np.nansum(cols[k]))
                         for k in range(len(cols))},
    }
