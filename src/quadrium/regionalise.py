"""Regionalising a national table with the location quotient family.

The method is `library/specs/B_method_cards/M-070_flq_regionalisation.md`, which
is the contract this module implements. Sources: `CORE_039` (Torój 2024) for the
family in one notation, `CORE_034` (Flegg & Tohmo) for the FLQ's calibration,
`CORE_033` (Szabó 2015) for the map.

WHAT THIS RETURNS BESIDES A MATRIX
------------------------------------
A `Regionalisation` carries the coefficients, the scaling factors actually
applied, the interregional imports the scaling implies, and **the measured cost
of the choices the caller did not make**. That last part is not decoration.
`CORE_036` p. 35 argues the ultimate responsibility for a table sits with the
analyst and that there should be no refuge in mechanically produced figures; a
function that returns a matrix and nothing else invites exactly that refuge.

The costs are measurements, not opinions, and each is checked by a validator:

    the whole family overstates local multipliers      SLQ +6.9 % to +20.0 %
                                                       (10 regions, 2 countries)
    using delta = 0.25 blind, against a fitted value   mean 2.2 points, worst 6.8
    cross-hauling the family does not reproduce        28.3 % of Catalonia's
                                                       interregional trade

See `run_flq_delta.py`, `run_delta_across_regions.py` and
`run_regionalisation_crosshauling.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

METHODS = ("SLQ", "CILQ", "RLQ", "FLQ")

# Measured, not assumed. Sources named in the module docstring.
EVIDENCE = {
    "slq_multiplier_bias_pct": (6.9, 20.0),
    "blind_delta_cost_points": {"mean": 2.2, "median": 1.4, "worst": 6.8},
    "fitted_delta_range": (0.14, 0.60),
    "fitted_delta_median": 0.26,
    "regions_measured": 10,
    "countries_measured": 2,
}


@dataclass
class Regionalisation:
    """The regional coefficients, and what the caller should know about them."""

    A: np.ndarray                       # regional domestic coefficients, n x n
    q: np.ndarray                       # the scaling factors applied
    method: str
    delta: Optional[float]
    lam: Optional[float]                # FLQ's lambda, None for the others
    slq: np.ndarray
    implicit_imports: np.ndarray        # by product, CORE_039 p. 292
    caveats: list[str] = field(default_factory=list)

    def report(self) -> str:
        """The costs, as a block a caller can print beside the numbers."""
        return "\n".join(self.caveats)


def _quotients(slq: np.ndarray, method: str, lam: float) -> np.ndarray:
    """CORE_039 eqs. (2)-(8). See M-070 for the numbering."""
    n = len(slq)
    if method == "SLQ":
        return np.minimum(slq, 1.0)[:, None] * np.ones((n, n))
    if method == "CILQ":
        raw = slq[:, None] / slq[None, :]
    elif method == "RLQ":
        raw = slq[:, None] / np.log2(1.0 + slq)[None, :]
    else:                                                   # FLQ
        raw = (slq[:, None] / slq[None, :]) * lam
    q = np.minimum(raw, 1.0)
    np.fill_diagonal(q, np.minimum(slq * (lam if method == "FLQ" else 1.0), 1.0))
    return q


def regionalise(A_national: np.ndarray,
                Q_region: np.ndarray,
                Q_national: np.ndarray,
                *,
                method: str = "FLQ",
                delta: Optional[float] = None,
                X_region: Optional[np.ndarray] = None) -> Regionalisation:
    """Estimate a region's domestic coefficients from the national table.

    `A_national` must be the **domestic** matrix. Feeding it a total-flow matrix
    regionalises the country's imports as though they were domestic supply, and
    nothing downstream catches it -- see M-070's DOMESTIC_IMPORT_TREATMENT and
    `run_regional_truth_survey.py`, which shows what that looks like when it
    happens.

    `X_region` is only needed for `implicit_imports`; it defaults to `Q_region`,
    which is right when activity is measured as output.
    """
    A_national = np.asarray(A_national, float)
    Q_region = np.asarray(Q_region, float).ravel()
    Q_national = np.asarray(Q_national, float).ravel()

    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}; expected one of "
                         f"{', '.join(METHODS)}")
    n = len(Q_region)
    if A_national.shape != (n, n):
        raise ValueError(f"A_national must be {n}x{n} to match the {n} sectors "
                         f"of Q_region, got {A_national.shape}")
    if len(Q_national) != n:
        raise ValueError(f"Q_national has {len(Q_national)} sectors against "
                         f"Q_region's {n}; align the classifications first, do "
                         f"not pad")
    if not np.isfinite(A_national).all():
        raise ValueError("A_national carries non-finite entries")
    neg = np.argwhere(A_national < 0)
    if neg.size:
        i, j = neg[0]
        raise ValueError(
            f"A_national[{i}, {j}] = {A_national[i, j]:.6g} is negative. The "
            f"quotient rule applies min(q, 1) to scale a coefficient DOWN, "
            f"which moves a negative one up; M-070 does not admit them")
    if Q_region.sum() <= 0 or Q_national.sum() <= 0:
        raise ValueError("regional and national activity must both be positive")
    bad = np.argwhere((Q_national <= 0) & (Q_region > 0))
    if bad.size:
        raise ValueError(
            f"sector {int(bad[0][0])} has positive regional activity and none "
            f"nationally, so its quotient is undefined. That is a "
            f"classification error upstream, not a value to substitute")

    if method == "FLQ":
        if delta is None:
            raise ValueError(
                "the FLQ needs a delta and there is no defensible default: "
                "measured across 10 regions in 2 countries it runs from "
                f"{EVIDENCE['fitted_delta_range'][0]} to "
                f"{EVIDENCE['fitted_delta_range'][1]} with a median of "
                f"{EVIDENCE['fitted_delta_median']}. Pass one and read the "
                "caveats, or choose CILQ and accept its bias. See OQ-R-02")
        if not 0.0 <= delta < 1.0:
            raise ValueError(f"delta must satisfy 0 <= delta < 1, got {delta}")
        lam = float(np.log2(1.0 + Q_region.sum() / Q_national.sum()) ** delta)
    else:
        lam = 1.0

    with np.errstate(divide="ignore", invalid="ignore"):
        slq = (Q_region / Q_region.sum()) / (Q_national / Q_national.sum())
    slq = np.where(np.isfinite(slq) & (slq > 0), slq, 0.0)

    q = _quotients(slq, method, lam)
    A = A_national * q
    x = Q_region if X_region is None else np.asarray(X_region, float).ravel()
    implicit = ((A_national - A) * x).sum(axis=1)

    lo, hi = EVIDENCE["slq_multiplier_bias_pct"]
    cost = EVIDENCE["blind_delta_cost_points"]
    caveats = [
        f"Measured on {EVIDENCE['regions_measured']} regions across "
        f"{EVIDENCE['countries_measured']} countries:",
        f"  - the quotient family overstates local output multipliers; SLQ by "
        f"{lo:.1f} % to {hi:.1f} %",
        f"  - cross-hauling is not reproduced in any amount anyone chose; it is "
        f"28.3 % of Catalonia's interregional trade",
    ]
    if method == "FLQ":
        caveats.insert(1, f"  - delta = {delta:g} was supplied, not derived. A "
                          f"blind 0.25 costs a mean {cost['mean']:.1f} points of "
                          f"multiplier bias, worst {cost['worst']:.1f}")
    else:
        caveats.insert(1, f"  - {method} has no calibration at all; the FLQ at a "
                          f"fitted delta is roughly an order of magnitude closer")
    return Regionalisation(A=A, q=q, method=method, delta=delta,
                           lam=lam if method == "FLQ" else None,
                           slq=slq, implicit_imports=implicit, caveats=caveats)
