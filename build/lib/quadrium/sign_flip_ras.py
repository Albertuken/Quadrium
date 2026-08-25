"""
Non-sign-preserving RAS, as specified in Lenzen, Moran, Geschke and Kanemoto
(2014), "A non-sign-preserving RAS variant", Economic Systems Research 26(2),
pp. 197-208.

This is `OQ-B-09`'s remaining half. `run_sign_change.py` and CORE_016 already
settled the INFEASIBLE case: a forced sign change is a diagnosis of ill-posed
inputs, and the engine should refuse and name the conflict. This module is the
other half — cells that LEGITIMATELY need to flip, such as changes in
inventories crossing zero between one year and the next, which is not an error
in the data, it is business cycles (Kitchin, 1923) doing what they do.

Acquired 2026-08-11: an open-access, author-hosted copy (Daniel Moran's page at
NILU), not the paywalled Taylor & Francis version. Equations 5 and 6 and Table 1
were transcribed from a page render, not from the text extraction, because
`pypdf`'s column-table extraction badly mangled the original — the same failure
mode this project already documented for UNH_18's mathematics. The formula below
was independently re-derived and verified against all eight of Table 1's printed
cases before being trusted; see `run_sign_flip_ras.py`.

THE MECHANISM
--------------
Standard KRAS (Lenzen and others 2009, eq. 5 here) scales element `a_j` by

    a_j^(n) = a_j^(n-1) * [r^(n)]^Sgn(a_j^(n-1) * G_ij)

Raising a POSITIVE scaler to a power of +1 or -1 can never change a's sign —
that exponent trick is *why* KRAS preserves sign. Equation 6 below computes the
same kind of quadratic-root scaler as GRAS/KRAS, but the update this module
applies is **plain multiplication**, `a_j^(n) = a_j^(n-1) * r^(n)`, with no
sign-locking exponent. That is the entire mechanism: drop the trick that
prevents the flip, not invent a new kind of scaler.

    r^(n) = Sgn(sum_j G_ij a_j^(n-1)) * c_i / (P + N)

    P = sum over j with a_j*G_ij > 0 of  G_ij * a_j^(n-1)      (>= 0)
    N = sum over j with a_j*G_ij < 0 of  -G_ij * a_j^(n-1)     (>= 0)

Verified against all eight combinations in the paper's Table 1, p. 202 —
G in {+1,-1}, a_prev in {+1,-1}, c in {+2,-2} — including the four that require
a sign flip. All eight match exactly; see `run_sign_flip_ras.py`.

WHAT THIS DOES AND DOES NOT COVER
------------------------------------
The paper's own scope note: Table 1 covers the case where a constraint is
"either (a) only positive elements added or negative elements subtracted, or
(b) only positive elements subtracted or negative elements added" — i.e. P=0 or
N=0. The "trivial case" where both P>0 and N>0 uses the ordinary KRAS scaler
(equation 5's non-degenerate form) and needs no sign flip; this module does not
implement general KRAS, only the flip mechanism, and callers needing the full
iterative solver should compose this with `gras.mras`/`gras.gras` rather than
treat this as a replacement.

**Which elements are allowed to flip is a modelling decision, not something the
formula supplies.** The paper (p. 203): "the implementation of this approach
must ensure that sign-flip procedures are only applied to those elements that
are allowed to undergo sign changes ... by setting up two additional a-sized
vectors l and u containing lower and upper bounds for each element ... Elements
with [l,u]=[0,inf] or [l,u]=[-inf,0] would then be excluded from any sign
flips." `sign_flip_allowed()` below implements exactly that gate.

THE EMPIRICAL CASE FOR NEEDING THIS AT ALL
----------------------------------------------
Brazilian supply-use tables, 2000-2008, changes in inventories, 89 goods: "in
every year between 2000 and 2008, at least 20% and mostly more than 30% of all
goods underwent reversals in stock trends" — the same order of magnitude as
this project's own measurement of up to 42% of products flipping sign year on
year (`run_sign_change.py`), from an independent country. Applying conventional
GRAS instead of the sign-flip variant to that same Brazilian series "is affected
by 245 errors" out of 990 elements. Taxes less subsidies flipped only once in
the same window — rare, but not impossible, consistent with `OQ-B-11`'s
correction of "on production" to "on products" for this exact row.

Run:
    python3 library/validators/run_sign_flip_ras.py
"""

from __future__ import annotations

import numpy as np


def sign_flip_scaler(G: np.ndarray, a_prev: np.ndarray, c: float) -> float:
    """Equation 6. `G` and `a_prev` are same-length 1-D arrays for one
    constraint `G . a = c`; returns the scaler `r` for that constraint.

    Degenerate at `sum(G * a_prev) == 0` -- the sign term has nothing to key
    off. The paper does not cover this case (P=0 and N=0 together is only
    possible when every participating a_prev is already zero); raise rather
    than guess.
    """
    G = np.asarray(G, dtype=float)
    a_prev = np.asarray(a_prev, dtype=float)
    if G.shape != a_prev.shape:
        raise ValueError(f"shape mismatch: G is {G.shape}, a_prev is {a_prev.shape}")
    ga = G * a_prev
    P = float(ga[ga > 0].sum())
    N = float(-ga[ga < 0].sum())
    total = float(ga.sum())
    if P == 0.0 and N == 0.0:
        raise ValueError("degenerate: every participating element is zero; "
                         "equation 6 has no sign to key off")
    sgn = np.sign(total) if total != 0 else np.sign(c)
    if sgn == 0:
        sgn = 1.0
    return sgn * c / (P + N)


def apply_sign_flip(G: np.ndarray, a_prev: np.ndarray, c: float) -> np.ndarray:
    """One constraint's worth of the update: `a_j^(n) = a_j^(n-1) * r^(n)`,
    plain multiplication -- the mechanism that lets the sign move. Elements
    with `a_prev == 0` and `G == 0` stay zero (0 * r = 0 regardless of r)."""
    r = sign_flip_scaler(G, a_prev, c)
    return np.asarray(a_prev, dtype=float) * r


def sign_flip_allowed(labels: list[str], flippable: set[str]) -> np.ndarray:
    """The l/u gate the paper requires (p. 203) but does not hand you a data
    structure for. `flippable` names the rows/cells this project has sourced
    reasons to expect sign changes in -- e.g. changes in inventories, taxes
    less subsidies -- everything else is excluded regardless of what the
    arithmetic would produce, because a category the source gives no reason to
    expect a flip in should not silently receive one.
    """
    return np.array([lbl in flippable for lbl in labels], dtype=bool)
