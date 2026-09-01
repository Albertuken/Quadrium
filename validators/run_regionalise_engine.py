"""
The regionalisation the engine ships agrees with the one the validators measured.

WHY THIS FILE
---------------
`M-070` was specified from `CORE_039` and `CORE_034`, and every number this
project has about the location quotient family came from implementations living
inside validators. `src/quadrium/regionalise.py` is now the shipped one. Two
implementations of the same method are two chances to be wrong, so this checks
they are the same method: the engine function is put through the published
example the validators reproduce, and through the Catalan fit that produced
`OQ-R-02`'s answer.

It also exercises the refusals, because a method whose limits are documented and
not enforced has limits only in the documentation.

WHAT THE FUNCTION RETURNS BESIDES A MATRIX
--------------------------------------------
`Regionalisation.report()` carries the measured cost of the choices the caller
did not make — the family's multiplier bias, the price of a blind delta, the
cross-hauling it does not reproduce. `CORE_036` p. 35 is the argument for that:
the responsibility for a table is the analyst's, and a function returning a bare
matrix invites the refuge in mechanically produced figures that the source warns
against. The check below is that the caveats are actually populated and name
numbers, not that they read well.

Run:
    python3 validators/run_regionalise_engine.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CAT = ROOT / "data" / "idescat" / "mioc2021ts64.xlsx"
ES = ROOT / "data" / "ine" / "cne_tio_21.xlsx"
FAIL: list[str] = []

# CORE_039 pp. 291-295, Tables 4 to 7 -- the same fixture as
# run_lq_crosshauling_structure.py, so the two files can disagree.
Z_NAT = np.array([[40.0, 5, 5], [5, 15, 10], [5, 5, 25]])
X_NAT = np.array([100.0, 50, 80])
Q_REG = np.array([[70.0, 20, 10], [30.0, 30, 70]])
PUB_A = {
    "SLQ": [np.array([[0.400, 0.100, 0.063], [0.046, 0.276, 0.115],
                      [0.014, 0.029, 0.090]]),
            np.array([[0.212, 0.053, 0.033], [0.050, 0.300, 0.125],
                      [0.050, 0.100, 0.313]])],
    "CILQ": [np.array([[0.400, 0.100, 0.063], [0.029, 0.276, 0.125],
                       [0.009, 0.031, 0.090]]),
             np.array([[0.212, 0.050, 0.021], [0.050, 0.300, 0.086],
                       [0.050, 0.100, 0.313]])],
    "RLQ": [np.array([[0.400, 0.100, 0.063], [0.033, 0.276, 0.125],
                      [0.010, 0.031, 0.090]]),
            np.array([[0.212, 0.051, 0.025], [0.050, 0.300, 0.098],
                      [0.050, 0.100, 0.313]])],
}
PUB_IMPORTS = {
    "SLQ": np.array([[0.000, 0.860, 6.145], [9.091, 0.000, 0.000]]),
    "CILQ": np.array([[0.000, 1.980, 6.477], [10.006, 2.750, 0.000]]),
    "RLQ": np.array([[0.000, 1.653, 6.389], [9.759, 1.867, 0.000]]),
}
CAT_DELTA = 0.20          # OQ-R-02, fitted against IDESCAT's published table


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def refuses(fragment, fn):
    try:
        fn()
    except ValueError as exc:
        return fragment in str(exc)
    return False


def main() -> int:
    warnings.filterwarnings("ignore")
    from quadrium.regionalise import EVIDENCE, regionalise

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    AN = Z_NAT / X_NAT
    QN = Q_REG.sum(axis=0)

    # ---- the published example, through the shipped function
    worst_A = worst_m = 0.0
    for method in ("SLQ", "CILQ", "RLQ"):
        for r in range(2):
            res = regionalise(AN, Q_REG[r], QN, method=method)
            worst_A = max(worst_A, float(np.abs(res.A - PUB_A[method][r]).max()))
            worst_m = max(worst_m, abs(float(res.implicit_imports.sum())
                                       - PUB_IMPORTS[method][r].sum()))
    check("the shipped function reproduces CORE_039's published example",
          worst_A < 6e-4 and worst_m < 6e-3,
          f"six regional coefficient matrices within {worst_A:.1e} of the "
          f"figures printed to three decimals, and the interregional imports "
          f"beside them within {worst_m:.1e}")

    # ---- FLQ collapses onto CILQ at delta = 0, as CORE_034 says
    a = regionalise(AN, Q_REG[0], QN, method="FLQ", delta=0.0)
    b = regionalise(AN, Q_REG[0], QN, method="CILQ")
    check("at delta = 0 the FLQ lands on CILQ, through the same entry point",
          np.allclose(a.A, b.A, atol=1e-12) and abs(a.lam - 1.0) < 1e-12,
          f"max difference {np.abs(a.A - b.A).max():.1e}, lambda = {a.lam:.6f}")

    # ---- the refusals the card documents
    print()
    bad = AN.copy(); bad[0, 1] = -0.1
    cases = [
        ("a negative national coefficient",
         "is negative", lambda: regionalise(bad, Q_REG[0], QN, method="SLQ")),
        ("the FLQ without a delta",
         "no defensible default",
         lambda: regionalise(AN, Q_REG[0], QN, method="FLQ")),
        ("a delta outside [0, 1)",
         "0 <= delta < 1",
         lambda: regionalise(AN, Q_REG[0], QN, method="FLQ", delta=1.4)),
        ("mismatched classifications",
         "align the classifications",
         lambda: regionalise(AN, Q_REG[0], QN[:2], method="SLQ")),
        ("an unknown method",
         "unknown method", lambda: regionalise(AN, Q_REG[0], QN, method="XLQ")),
        ("regional activity where there is none nationally",
         "classification error upstream",
         lambda: regionalise(AN, np.array([1.0, 1.0, 1.0]),
                             np.array([1.0, 1.0, 0.0]), method="SLQ")),
    ]
    fired = [name for name, frag, fn in cases if refuses(frag, fn)]
    check("every refusal M-070 documents actually fires",
          len(fired) == len(cases),
          f"{len(fired)} of {len(cases)}: " + "; ".join(fired))

    # ---- the costs travel with the result
    res = regionalise(AN, Q_REG[0], QN, method="FLQ", delta=0.25)
    text = res.report()
    check("and the measured costs travel with the answer",
          "0.25" in text and "28.3" in text
          and f"{EVIDENCE['regions_measured']}" in text and len(res.caveats) >= 3,
          f"{len(res.caveats)} lines naming the blind-delta cost, the family's "
          f"multiplier bias and the cross-hauling it does not reproduce — the "
          f"position CORE_036 p. 35 argues for")

    # ---- and it lands where OQ-R-02 said, on the real pair
    if CAT.exists() and ES.exists():
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from run_es_cat_bridge import to_catalan_products as fold

        from quadrium.io_loader import load_idescat_mioc, load_ine_tio
        es = load_ine_tio(ES, variant="interior")
        cat = load_idescat_mioc(CAT)
        x_es = fold(es.X)
        Z = np.array([fold(c) for c in np.array([fold(r) for r in es.Z.T]).T])
        with np.errstate(divide="ignore", invalid="ignore"):
            A_es = np.where(x_es > 0, Z / x_es, 0.0)
            A_true = np.where(cat.X > 0, cat.Z / cat.X, 0.0)

        def mu1(A):
            m = np.linalg.inv(np.eye(len(A)) - A).sum(0)
            t = np.linalg.inv(np.eye(len(A_true)) - A_true).sum(0)
            o = t > 0
            return float(100 / len(t) * np.sum((m[o] - t[o]) / t[o]))

        got = regionalise(A_es, cat.X, x_es, method="FLQ", delta=CAT_DELTA)
        print()
        print(f"    {'Catalonia through the shipped function, delta = 0.20':<54}"
              f"mu1 {mu1(got.A):+.2f} %")
        print(f"    {'the same table under SLQ':<54}"
              f"mu1 {mu1(regionalise(A_es, cat.X, x_es, method='SLQ').A):+.2f} %")
        check("the engine reproduces OQ-R-02's answer on the real pair",
              abs(mu1(got.A)) < 1.0,
              f"mu1 = {mu1(got.A):+.2f} % against the table IDESCAT published, "
              f"which is what run_flq_delta.py measured with its own "
              f"implementation. Two implementations, one number")
    else:
        print("\n    -- the Spanish and Catalan tables are private and absent "
              "here;\n       the published example above stands on its own.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
