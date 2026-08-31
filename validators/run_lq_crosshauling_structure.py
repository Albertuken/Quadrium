"""
What the location-quotient family actually does with cross-hauling.

WHY THIS EXISTS
-----------------
`OQ-R-01` was opened on 2026-08-30 on the strength of one sentence in `CORE_033`
(Szabó 2015, p. 51):

    "The interregional trade can be accounted for as a net export since LQ tends
    to underestimate interregional trade. Thus, an industry is only able to
    export or import. Simultaneous export and import (cross-hauling) is not
    allowed in this framework."

That sentence was taken to cover the whole family, and `CORE_03` was recorded as
unclosable because the one source written about cross-hauling (`CORE_037`,
Kronenberg's CHARM) is held as a DOI link only.

`CORE_039` (Torój 2024, *(Inter)regional Input-Output Table Estimation: from
Surveys to Spatial Econometrics*, CEJEME 16: 285-322) says otherwise, p. 316:

    "Simple Location Quotients (SLQ) preclude cross-hauling (simultaneous
    imports and exports of the same commodity) ... The issue is not fully solved
    by Cross-Industry Location Quotients (CILQ) or closely related Round's
    Location Quotients (RLQ), although they generate some cross-hauling. The
    dominant approach, Flegg's Location Quotient (FLQ), substantially increases
    the value of interregional trade and cross-hauling by using a calibrated
    convexity parameter."

So the prohibition belongs to SLQ, not to the family. This file settles which
account is right by arithmetic rather than by choosing a sentence, using Torój's
own published worked example as the fixture.

THE FIXTURE — Torój pp. 291-295, Tables 4 to 7
------------------------------------------------
A 3-sector, 2-region economy. Every printed figure of Tables 5, 6 and 7 is
recomputed here from Table 4 alone and compared against what the paper prints.
The published tables also report, per region and commodity, the implicit
interregional imports Sum_j (a^N_ij - a^r_ij) * x^r_j, which is what makes
cross-hauling visible: a commodity is cross-hauled when two regions both import
it.

    SLQ    q^r_ij = min(SLQ^r_i, 1)                                 eq. (2)
           SLQ^r_i = (Q^r_i / Q^r) / (Q^N_i / Q^N)                  eq. (3)
    CILQ   q^r_ij = min(SLQ^r_i, 1) on the diagonal,                eq. (4)
                    min(CILQ^r_ij, 1) off it
           CILQ^r_ij = SLQ^r_i / SLQ^r_j                            eq. (5)
    RLQ    RLQ^r_ij = SLQ^r_i / log2(1 + SLQ^r_j), used in eq. (4)  eq. (6)

TWO RESULTS THAT ARE NOT IN THE PAPER
---------------------------------------
Torój demonstrates cross-hauling under CILQ in one 3x2 example. Neither of the
following is stated there; both are derived here and checked numerically,
and they are the reason the correction to `OQ-R-01` is a rewrite and not a
footnote.

1. SLQ precludes cross-hauling ONLY FOR TWO REGIONS. The identity is that the
   region-share-weighted mean of SLQ is exactly one for every commodity,

       Sum_r (Q^r / Q^N) * SLQ^r_i = Sum_r Q^r_i / Q^N_i = 1,

   so with two regions one of them must sit at or above 1 and therefore export.
   With three or more, two regions can both sit below 1 and both import. The
   no-cross-hauling property is an artefact of the two-region case, and Szabó's
   sentence is stated without that condition.

2. CILQ cross-hauls at least S - R commodities, always. Region r imports
   commodity i whenever some j has SLQ^r_i < SLQ^r_j, i.e. whenever i is not the
   SLQ-argmax of region r. At most R commodities can be an argmax anywhere, so
   at least S - R are imported by EVERY region. With 64 sectors and 2 regions
   that is 62 commodities cross-hauled by construction, whatever the data.

Together: no member of the family reproduces a measured cross-hauling pattern,
but only SLQ-on-two-regions forbids it. The rest produce it as a side effect of
their scaling rule, in an amount nobody chose.

Run:
    python3 validators/run_lq_crosshauling_structure.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TOROJ = ROOT / "library" / "extracted" / \
    "CORE_039_Toroj_Interregional_IOT_Estimation_Review.txt"
FAIL: list[str] = []

# Torój p. 292, Table 4a and 4b — the whole input to the example.
Z_NAT = np.array([[40.0, 5, 5], [5, 15, 10], [5, 5, 25]])
X_NAT = np.array([100.0, 50, 80])
Q_REG = np.array([[70.0, 20, 10], [30.0, 30, 70]])       # region x sector

# Torój pp. 292-295, printed to three decimals. The extraction drops the
# diagonal entry of every row of Tables 6a and 7a, so the quotients below are
# recorded off-diagonal only, exactly as the pages print them.
PUB_SLQ = np.array([[1.610, 0.920, 0.288], [0.531, 1.062, 1.548]])
PUB_IMPORTS = {                                          # region -> per commodity
    "SLQ":  np.array([[0.000, 0.860, 6.145], [9.091, 0.000, 0.000]]),
    "CILQ": np.array([[0.000, 1.980, 6.477], [10.006, 2.750, 0.000]]),
    "RLQ":  np.array([[0.000, 1.653, 6.389], [9.759, 1.867, 0.000]]),
}
PUB_OFFDIAG = {
    "CILQ": {(0, 0): [1.750, 5.600], (0, 1): [0.571, 3.200], (0, 2): [0.179, 0.313],
             (1, 0): [0.500, 0.343], (1, 1): [2.000, 0.686], (1, 2): [2.917, 1.458]},
    "RLQ":  {(0, 0): [1.711, 4.416], (0, 1): [0.665, 2.524], (0, 2): [0.208, 0.305],
             (1, 0): [0.509, 0.393], (1, 1): [1.728, 0.787], (1, 2): [2.520, 1.483]},
}
PUB_A = {                                                # Tables 5b, 6b, 7b
    "SLQ":  [np.array([[0.400, 0.100, 0.063], [0.046, 0.276, 0.115],
                       [0.014, 0.029, 0.090]]),
             np.array([[0.212, 0.053, 0.033], [0.050, 0.300, 0.125],
                       [0.050, 0.100, 0.313]])],
    "CILQ": [np.array([[0.400, 0.100, 0.063], [0.029, 0.276, 0.125],
                       [0.009, 0.031, 0.090]]),
             np.array([[0.212, 0.050, 0.021], [0.050, 0.300, 0.086],
                       [0.050, 0.100, 0.313]])],
    "RLQ":  [np.array([[0.400, 0.100, 0.063], [0.033, 0.276, 0.125],
                       [0.010, 0.031, 0.090]]),
             np.array([[0.212, 0.051, 0.025], [0.050, 0.300, 0.098],
                       [0.050, 0.100, 0.313]])],
}


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def slq(Q: np.ndarray) -> np.ndarray:
    """Torój eq. (3), for every region at once."""
    return (Q / Q.sum(1, keepdims=True)) / (Q.sum(0) / Q.sum())


def quotients(s: np.ndarray, method: str) -> np.ndarray:
    """Torój eqs. (2), (4)-(5), (6). `s` is one region's SLQ vector."""
    n = len(s)
    if method == "SLQ":
        return np.minimum(s, 1.0)[:, None] * np.ones((n, n))
    raw = (s[:, None] / s[None, :] if method == "CILQ"
           else s[:, None] / np.log2(1.0 + s)[None, :])
    q = np.minimum(raw, 1.0)
    np.fill_diagonal(q, np.minimum(s, 1.0))              # eq. (4), diagonal
    return q


def imports(AN: np.ndarray, s: np.ndarray, xr: np.ndarray, method: str):
    """Regional coefficients, and the implicit interregional imports beside them."""
    Ar = AN * quotients(s, method)
    return Ar, ((AN - Ar) * xr).sum(1)


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if TOROJ.exists():
        text = TOROJ.read_text()
        check("the source that says the family is not uniform is on disk",
              "although they generate some cross-hauling" in text,
              "Torój p. 316, quoted above — so what is being tested is the "
              "source's own claim and not a paraphrase of it")
    else:
        print("  --   Torój's extraction is private and absent here; the "
              "arithmetic below stands on its own.")

    AN = Z_NAT / X_NAT
    S = slq(Q_REG)
    check("SLQ reproduces Torój's Table 5a to the printed precision",
          np.allclose(S, PUB_SLQ, atol=6e-4),
          f"max deviation {np.abs(S - PUB_SLQ).max():.1e} on figures printed to 3 dp")

    print()
    imp = {}
    for method in ("SLQ", "CILQ", "RLQ"):
        got_A, got_imp = [], []
        for r in range(2):
            Ar, m = imports(AN, S[r], Q_REG[r], method)
            got_A.append(Ar)
            got_imp.append(m)
        imp[method] = np.array(got_imp)

        ok_A = all(np.allclose(got_A[r], PUB_A[method][r], atol=6e-4)
                   for r in range(2))
        ok_m = np.allclose(imp[method], PUB_IMPORTS[method], atol=6e-3)
        dev = max(np.abs(got_A[r] - PUB_A[method][r]).max() for r in range(2))
        check(f"{method:<4} reproduces the published regional coefficients and "
              f"the imports beside them", ok_A and ok_m,
              f"A^r within {dev:.1e}, imports within "
              f"{np.abs(imp[method] - PUB_IMPORTS[method]).max():.1e}")

        if method in PUB_OFFDIAG:
            worst, bad = 0.0, 0
            for r in range(2):
                q_raw = (S[r][:, None] / S[r][None, :] if method == "CILQ"
                         else S[r][:, None] / np.log2(1.0 + S[r])[None, :])
                for i in range(3):
                    off = [q_raw[i, j] for j in range(3) if j != i]
                    for a, b in zip(off, PUB_OFFDIAG[method][(r, i)]):
                        worst = max(worst, abs(a - b))
                        bad += abs(a - b) > 6e-3
            check(f"     and its 12 printed off-diagonal quotients", bad == 0,
                  f"max deviation {worst:.1e}")

    print()
    print("    cross-hauled commodities (both regions importing), 2 regions:")
    for method in ("SLQ", "CILQ", "RLQ"):
        which = [i + 1 for i in range(3) if (imp[method][:, i] > 1e-9).sum() >= 2]
        print(f"      {method:<5} {which if which else 'none'}")

    check("SLQ produces none, on two regions",
          (imp["SLQ"] > 1e-9).sum(0).max() < 2,
          "every commodity has exactly one importing region — the prohibition "
          "in Szabó p. 51 is real here")
    check("CILQ and RLQ both produce it, in commodity 2",
          (imp["CILQ"][:, 1] > 1e-9).all() and (imp["RLQ"][:, 1] > 1e-9).all(),
          f"CILQ {imp['CILQ'][0,1]:.3f} and {imp['CILQ'][1,1]:.3f}; "
          f"RLQ {imp['RLQ'][0,1]:.3f} and {imp['RLQ'][1,1]:.3f} — so the "
          "family is not uniform and OQ-R-01's premise was too strong")

    # ---- result 1: the two-region case is special, and provably so
    print()
    w = Q_REG.sum(1) / Q_REG.sum()
    check("the weighted mean of SLQ is exactly 1 for every commodity",
          np.allclose(w @ S, 1.0, atol=1e-12),
          f"max |w'SLQ - 1| = {np.abs(w @ S - 1).max():.1e}. This is what makes "
          "two regions a special case: both cannot fall below 1")

    rng = np.random.default_rng(11)
    seen = {2: 0, 3: 0}
    for R in (2, 3):
        for _ in range(400):
            Qr = rng.random((R, 4)) * 100
            s_all = slq(Qr)
            m = np.array([imports(AN[:3, :3], s_all[r][:3], Qr[r][:3], "SLQ")[1]
                          for r in range(R)])
            seen[R] += int(((m > 1e-9).sum(0) >= 2).any())
    check("and SLQ starts cross-hauling as soon as a third region exists",
          seen[2] == 0 and seen[3] > 0,
          f"0 of 400 random two-region economies, {seen[3]} of 400 with three. "
          "Szabó's sentence is stated without that condition")

    # ---- result 2: the S - R floor under CILQ
    print()
    print("    CILQ, commodities cross-hauled out of S, against the S-R floor:")
    worst = 10 ** 9
    for S_n, R in ((3, 2), (10, 2), (20, 4), (64, 2), (64, 17)):
        counts = []
        for _ in range(25):
            A = rng.random((S_n, S_n)) * 0.3
            Qr = rng.random((R, S_n)) * 100
            s_all = slq(Qr)
            m = np.array([imports(A, s_all[r], Qr[r], "CILQ")[1] for r in range(R)])
            counts.append(int(((m > 1e-12).sum(0) >= 2).sum()))
        floor = max(S_n - R, 0)
        worst = min(worst, min(counts) - floor)
        print(f"      S={S_n:<3} R={R:<3} cross-hauled {min(counts)}-{max(counts)}"
              f"   floor S-R = {floor}")
    check("CILQ never falls below the S - R floor",
          worst >= 0,
          f"smallest margin over the floor across all sizes: {worst:+d}. At 64 "
          "sectors and 2 regions that is 62 commodities cross-hauled by "
          "construction, in an amount the method never chose")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
