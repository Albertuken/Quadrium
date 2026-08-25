"""
Cholette-Dagum GLS reconciliation, as specified in Stanger, M. (2018), "An
Algorithm to Balance Supply and Use Tables," IMF Technical Notes and Manuals
18/03, §V.

This is `OQ-B-01`'s `restricted` residue. v1.25 found that CORE_004 ¶19.80
names the weighted / conflicting-data operation and calls it judgement, and
that CORE_021 p. 209 reports full automation was tried and abandoned — and
concluded the residue "is not an equation at all". **That was half right.**
Setting the reliability weights IS judgement, and no source gives a rule for
it. But once weights are set, applying them to reconcile an unbalanced system
is not judgement — it is generalised least squares, and Stanger writes the
closed form out completely.

THE MODEL (Cholette & Dagum 2006, as reduced by Stanger §V)
----------------------------------------------------------------
    s = I*theta + e,   E(e)=0, E(ee')=Ve          -- the unbalanced estimates
    g = G*theta + eps, E(eps)=0, E(eps eps')=Veps  -- the accounting constraints

`s` is what was observed; `theta` is the balanced table being solved for; `G`
encodes the accounting identities (e.g. one row per product: supply - use = 0);
`Ve` is the reliability of each observation -- LOW variance means HIGH
confidence, and the GLS solution moves low-confidence entries more.

Byron's (1978) approximation gives the feasible closed form (Stanger eq. 5):

    theta_hat = s + Ve @ G' @ inv(G @ Ve @ G' + Veps) @ (g - G @ s)

`Veps = 0` makes the constraint binding -- theta_hat satisfies `G @ theta_hat
= g` exactly, verified in `run_gls_reconcile.py` alongside a qualitative check
that a low-variance (trusted) entry barely moves while a high-variance
(untrusted) one absorbs nearly the whole correction.

WHAT THIS DOES NOT SUPPLY, AND M-061/M-062 STILL SAY WHY THAT IS RIGHT
---------------------------------------------------------------------------
`Ve` itself. CORE_004 ¶19.80 calls choosing it "informed judgement", and
nothing in this source or any other loaded one gives a rule for turning
"how much do I trust this row" into a number. That is unchanged from v1.25 --
what changes is that "no algorithm" becomes "no algorithm for the ONE input a
human still has to supply", which is a materially smaller gap than the entry
recorded.

Run:
    python3 library/validators/run_gls_reconcile.py
"""

from __future__ import annotations

import numpy as np


def gls_reconcile(s: np.ndarray, G: np.ndarray, g: np.ndarray,
                  Ve: np.ndarray, Veps: np.ndarray | float = 0.0
                  ) -> np.ndarray:
    """Stanger eq. 5. `s` the unbalanced estimates, `G` the constraint matrix
    (one row per accounting identity), `g` the constraints' targets, `Ve` the
    covariance of the estimates (reliability), `Veps` the covariance of the
    constraints themselves (0 for a binding/exact identity).
    """
    s = np.asarray(s, dtype=float)
    G = np.atleast_2d(np.asarray(G, dtype=float))
    g = np.asarray(g, dtype=float).ravel()
    Ve = np.asarray(Ve, dtype=float)
    if G.shape[1] != s.size:
        raise ValueError(f"G has {G.shape[1]} columns but s has {s.size} "
                         f"elements")
    if G.shape[0] != g.size:
        raise ValueError(f"G has {G.shape[0]} rows but g has {g.size} "
                         f"elements")
    d = g - G @ s
    inner = G @ Ve @ G.T + Veps
    F = Ve @ G.T @ np.linalg.inv(inner)
    return s + F @ d
