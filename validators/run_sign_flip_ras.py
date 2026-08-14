"""
`OQ-B-09`'s legitimate-flip half: a real, sourced, verified algorithm, not
just a named gap anymore.

`run_sign_change.py` and CORE_016 settled the INFEASIBLE case at v1.37: a
forced sign flip is a diagnosis of ill-posed inputs, refuse and name the
conflict. What stayed unsolved was the other half — cells that legitimately
need to flip, such as changes in inventories crossing zero between years,
which the entry named specifically and which CORE_016 does not address at all.

Lenzen, Moran, Geschke and Kanemoto (2014), "A non-sign-preserving RAS
variant" (`Economic Systems Research` 26(2):197-208) is that algorithm.
Acquired 2026-08-11 from an open-access, author-hosted copy — not the
paywalled publisher version.

THE TRANSCRIPTION RISK, AND HOW IT WAS HANDLED
--------------------------------------------------
`pypdf`'s text extraction badly mangles the paper's equations and Table 1 —
columns run together, square-root signs vanish, subscripts merge with the
surrounding text. The same failure mode this project already documented for
UNH_18. Equations 5 and 6 and Table 1 were re-read from a 220 dpi page render
instead, and the formula in `quadrium/sign_flip_ras.py` was **independently
re-derived and checked against all eight of Table 1's printed cases before
being trusted** — including discovering, by testing rather than assuming, that
the update rule for this variant drops KRAS's usual sign-locking exponent in
favour of plain multiplication. That is the whole mechanism: KRAS scales by
`r^Sgn(...)`, which can never flip a sign because a positive number raised to
±1 stays positive; this variant scales by `r` directly.

Run:
    python3 validators/run_sign_flip_ras.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quadrium.sign_flip_ras import (apply_sign_flip, sign_flip_allowed,  # noqa: E402
                                     sign_flip_scaler)

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


# Table 1, p. 202, transcribed from the page render, not the garbled text
# extraction: (G, a_prev, c, sign-flip expected, a_next expected)
TABLE_1 = [
    (1, 1, 2, False, 2), (-1, -1, 2, False, -2),
    (1, -1, -2, False, -2), (-1, 1, -2, False, 2),
    (1, 1, -2, True, -2), (-1, -1, -2, True, 2),
    (1, -1, 2, True, 2), (-1, 1, 2, True, -2),
]


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    print(f"    {'G':>3}{'a_prev':>8}{'c':>5}{'r':>8}{'a_next':>9}{'flip':>7}"
          f"   table says")
    all_ok = True
    for G, a_prev, c, flip_expected, a_next_expected in TABLE_1:
        r = sign_flip_scaler(np.array([G]), np.array([a_prev]), c)
        a_next = float(apply_sign_flip(np.array([G]), np.array([a_prev]), c))
        flip_observed = np.sign(a_next) != np.sign(a_prev)
        row_ok = (abs(a_next - a_next_expected) < 1e-9
                  and flip_observed == flip_expected)
        all_ok &= row_ok
        print(f"    {G:>3}{a_prev:>8}{c:>5}{r:>8.2f}{a_next:>9.2f}"
              f"{'YES' if flip_observed else 'no':>7}   a_next={a_next_expected}, "
              f"flip={'YES' if flip_expected else 'no'}"
              f"   {'ok' if row_ok else 'FAIL'}")

    check("all eight combinations of Table 1 (p. 202) reproduce exactly",
          all_ok,
          "the four no-flip rows and the four flip rows, both signs of G, "
          "both signs of the prior estimate, both signs of the target")

    check("flip is required exactly where the achieved sign differs from the "
          "prior sign",
          all(flip_expected == (np.sign(a_next_expected) != np.sign(a_prev))
              for _, a_prev, _, flip_expected, a_next_expected in TABLE_1),
          "the table's own 'sign flip' column matches its own 'a_next' column "
          "in every row — an internal consistency check on the transcription, "
          "not a restatement of the paper's mechanism")

    # ---- degenerate input is refused, not guessed --------------------------
    print()
    try:
        sign_flip_scaler(np.array([1.0, -1.0]), np.array([0.0, 0.0]), 5.0)
        check("an all-zero participating vector is refused rather than guessed",
              False, "should have raised")
    except ValueError as e:
        check("an all-zero participating vector is refused rather than guessed",
              "degenerate" in str(e),
              str(e))

    # ---- multi-element case, still inside equation 6's own scope ----------
    print()
    # Five commodities' prior-year changes in inventories, ALL positive --
    # keeping P>0, N=0, i.e. still one of Table 1's two degenerate cases, just
    # with five elements sharing one constraint instead of one. A mix of
    # positive and negative a_prev (P>0 AND N>0) is the paper's own "trivial
    # case" and explicitly OUTSIDE equation 6's scope -- it says the ordinary
    # KRAS scaler (equation 5, already in gras.mras) applies there instead, so
    # testing that combination against equation 6 would be testing something
    # the paper never claims.
    G = np.array([1, 1, 1, 1, 1], dtype=float)
    a_prev = np.array([120.0, 80.0, 45.0, 30.0, 15.0])
    c = -200.0    # last year's inventories all built up; this year, a drawdown
    r = sign_flip_scaler(G, a_prev, c)
    a_next = apply_sign_flip(G, a_prev, c)
    check("with five elements sharing one constraint, it still hits the "
          "target exactly and flips every one",
          abs(float(G @ a_next) - c) < 1e-9 and bool((a_next < 0).all()),
          f"G.a_next = {float(G @ a_next):.6f} against target {c}; all five "
          f"commodities move from built-up stock to drawdown together, which "
          f"is what one shared constraint on 'changes in inventories' would "
          f"actually mean for a product group")

    # ---- the l/u gate ------------------------------------------------------
    print()
    labels = ["changes in inventories", "compensation of employees",
              "taxes less subsidies on products", "intermediate consumption"]
    flippable = {"changes in inventories", "taxes less subsidies on products"}
    gate = sign_flip_allowed(labels, flippable)
    check("the l/u gate the paper requires (p. 203) admits only sourced "
          "categories",
          gate.tolist() == [True, False, True, False],
          "changes in inventories and taxes less subsidies on products pass; "
          "compensation of employees and intermediate consumption do not — "
          "a category with no stated reason to flip does not get to, "
          "regardless of what one year's arithmetic would produce")

    # ---- the empirical case for needing this at all ------------------------
    print()
    print("    Brazilian SUTs, 2000-2008, changes in inventories, 89 goods:")
    print("    'at least 20% and mostly more than 30%' of goods reversed stock")
    print("    trends every year (Lenzen et al. 2014, p. 204) -- the same order")
    print("    of magnitude as this project's own measurement of up to 42% of")
    print("    products flipping sign year on year (run_sign_change.py), from")
    print("    an independent country. Conventional GRAS on that series 'is")
    print("    affected by 245 errors' out of 990 elements; the sign-flip")
    print("    variant 'exactly represents the original values in all updates'.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
