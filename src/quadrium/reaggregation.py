"""
Reaggregation Guarantee (MVP_0.1 §8).

Sum the new subsectors back to the original dimension. Everything except the
split sector must come back EXACTLY — that is a test, not a diagnostic, because
those cells were copied and never touched. Only the split sector's row, column
and diagonal can move, and only within tolerance.
"""

from __future__ import annotations

import numpy as np


def reaggregate(Z_expanded: np.ndarray, mapping: list[int],
                n_original: int) -> np.ndarray:
    """Sum rows and columns of the new subsectors back to original dimensions."""
    Z_expanded = np.asarray(Z_expanded, float)
    M = np.zeros((n_original, len(mapping)))
    for i_new, i_orig in enumerate(mapping):
        M[i_orig, i_new] = 1.0
    return M @ Z_expanded @ M.T


def reaggregate_vector(v_expanded: np.ndarray, mapping: list[int],
                       n_original: int) -> np.ndarray:
    out = np.zeros(n_original)
    for i_new, i_orig in enumerate(mapping):
        out[i_orig] += v_expanded[i_new]
    return out


def reaggregation_error(Z_original: np.ndarray, Z_reagg: np.ndarray,
                        split_indices: list[int] | int | None = None) -> dict:
    """Compare the reaggregated table with the original.

    `untouched_max_abs_error` is the sharp test: cells not involving the split
    sector were copied verbatim, so anything above floating-point noise there is
    an indexing bug, not an estimation error.
    """
    Z_original = np.asarray(Z_original, float)
    Z_reagg = np.asarray(Z_reagg, float)
    diff = Z_reagg - Z_original

    with np.errstate(divide="ignore", invalid="ignore"):
        denom = np.where(Z_original == 0, np.nan, Z_original)
        pct = np.abs(diff / denom) * 100.0
    max_pct = float(np.nanmax(pct)) if np.any(~np.isnan(pct)) else None

    out = {
        "max_abs_error": float(np.max(np.abs(diff))),
        "max_pct_error": max_pct,
        "total_original": float(Z_original.sum()),
        "total_reaggregated": float(Z_reagg.sum()),
        "total_abs_error": float(abs(Z_reagg.sum() - Z_original.sum())),
    }

    if split_indices is not None:
        idx = ([split_indices] if isinstance(split_indices, (int, np.integer))
               else list(split_indices))
        mask = np.ones_like(diff, dtype=bool)
        for s in idx:
            mask[s, :] = False
            mask[:, s] = False
        out["untouched_max_abs_error"] = (float(np.max(np.abs(diff[mask])))
                                          if mask.any() else 0.0)
        out["split_row_abs_error"] = float(np.max(np.abs(diff[idx, :])))
        out["split_col_abs_error"] = float(np.max(np.abs(diff[:, idx])))
    return out
