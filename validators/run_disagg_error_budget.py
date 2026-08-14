"""
`OQ-S-02`/`OQ-S-03`: what a split costs in accuracy, and when the margins are
worth chasing.

CORE_025 (Jeong 2022, in Korean) has been dismissed in this file since v1.4 as
"untranslatable here". **It is not.** It is readable, it is 16 KB, and it is a
1,000-replication Monte Carlo of exactly this engine's operation: one sector of a
20-sector table split into two, estimated, and scored cell by cell against the
truth. The project has been guessing at a number that a source in its own library
measures.

WHAT CORE_025 REPORTS
-----------------------
Its Table 2, p. 862 — mean absolute percentage error over the 441 cells of the
21-sector input-coefficient matrix, averaged over 1,000 replications:

    this paper's method   11.2250 %   (s.d. 1.6642)
    RAS                   11.3016 %   (s.d. 1.6046)

The paper's point is the comparison, not the level. Its method never uses the
**intermediate-demand totals** — the row sums of the new subsectors, which RAS
requires and which the text says "많은 경우에 … 확보하기 어렵다", are in many
cases hard to obtain. Doing without them costs nothing measurable: 11.2250
against 11.3016.

THIS FILE IS **NOT** A REPLICATION OF THAT, AND SAYS SO
--------------------------------------------------------
An independent implementation of the setup as described — 21 sectors, `Z ~
U[50,250]`, value-added ratios `~ U[0.4,0.6]`, merge sectors 2 and 3, re-split —
lands at **≈5 %**, not ≈11 %. A factor of 2.3.

**That gap is not reconciled here and no attempt was made to close it.** Tuning
an implementation until it matches a published number is how a validator becomes
a way of agreeing with itself; the difference is reported and left standing. It
means the setup below is not Jeong's in some detail the paper's Korean does not
pin down for me — most likely which matrix RAS is applied to, coefficients or
flows, and what the starting point is.

So the absolute levels below carry no authority. What they measure is a
**comparison inside one consistent setup**, which is the same shape of question
Jeong asks, and the answer is sharper than his because it varies the one thing he
holds fixed.

WHAT THE MEASUREMENT SAYS, AND IT REFINES THE PAPER
-----------------------------------------------------
Jeong compares "with margins" against "without margins" using a good key. Vary
the key instead:

    key bias        key alone     + true margins      gain
    exact             5.29 %          5.00 %        0.29 pp
    +10 %             5.57 %          5.02 %        0.55 pp
    +25 %             6.75 %          5.02 %        1.73 pp
    +41 %             8.76 %          4.93 %        3.84 pp

**The margins repair the key.** With true row and column sums the error sits at
5.0 % whatever the key does; without them the key's bias passes straight through.
So the value of the intermediate-demand totals is **not** a constant worth ~0.1
points, as Jeong's single comparison suggests — it is conditional on key quality,
and it grows fast.

**+41 % is not an arbitrary row.** It is the Spanish pilot's real key error:
33.73 % estimated against 23.95 % true (`OQ-S-05`), which is +41 % in relative
terms. On this synthetic geometry, obtaining the margins for that split would
have roughly halved the coefficient error. That is the concrete argument for the
data request `OQ-S-05` leaves open, and it is the first time this project can put
a number on what that request is worth.

WHAT THIS DOES NOT ESTABLISH
------------------------------
The design is synthetic and structureless: uniform draws give a dense matrix with
no zeros, no skew and no block structure, where a real 65-sector table is sparse
and heavily skewed. **Absolute error levels do not transfer to real data** and
none is claimed. The comparative shape — margins dominate a bad key, and add
little to a good one — is what the design can support, and it is what is
reported.

Run:
    python3 validators/run_disagg_error_budget.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

EXTRACTED = ROOT / "library" / "extracted"
REPLICATIONS = 400
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def trial(rng: np.random.Generator, key_bias: float) -> tuple[float, float]:
    """One replication. Returns (error with the key alone, error after RAS)."""
    from quadrium.gras import gras

    n = 21
    Z = rng.uniform(50, 250, (n, n))
    va = rng.uniform(0.4, 0.6, n)
    X = Z.sum(0) / (1 - va)
    A = Z / X

    # merge sectors 2 and 3 into the 20-sector table the compiler would hold
    M = np.zeros((20, n))
    M[0, 0] = 1
    M[1, 1] = M[1, 2] = 1
    for k, j in enumerate(range(3, n)):
        M[2 + k, j] = 1
    Z20 = M @ Z @ M.T

    # split it back with an output key, biased by `key_bias`
    w0 = X[1] / (X[1] + X[2])
    w = np.array([min(w0 * (1 + key_bias), 0.99), 0.0])
    w[1] = 1 - w[0]
    P = np.zeros((n, 20))
    P[0, 0] = 1
    P[1, 1], P[2, 1] = w
    for k, j in enumerate(range(3, n)):
        P[j, 2 + k] = 1
    Z_key = P @ Z20 @ P.T

    err_key = float(np.mean(np.abs(Z_key / X - A) / A) * 100)
    r = gras(Z_key, Z.sum(1), Z.sum(0), eps=1e-9, max_iter=2000)
    err_ras = float(np.mean(np.abs(r.X / X - A) / A) * 100)
    return err_key, err_ras


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # ---- the source is readable, which the entry denies -------------------
    c25 = EXTRACTED / "CORE_025_Jeong2022_Disaggregated_Sector.txt"
    if c25.exists():
        text = c25.read_text()
        flat = re.sub(r"\s+", " ", text)
        check("CORE_025 is readable and reports the numbers the entries needed",
              "11.2250" in flat and "11.3016" in flat,
              "Table 2, p. 862: the method without intermediate-demand totals "
              "scores 11.2250 % against RAS's 11.3016 % over 1,000 "
              "replications. The entries called this source 'untranslatable "
              "here' and it has sat in library/extracted since v1.4")
        check("and its central claim is about data availability, not accuracy",
              "중간수요계" in text,
              "the intermediate-demand totals RAS requires are, in the "
              "abstract's words, hard to obtain in many cases — so a method "
              "that does without them is worth having even at equal accuracy")

    # ---- the measurement --------------------------------------------------
    rng = np.random.default_rng(11)
    rows = []
    for bias in (0.0, 0.10, 0.25, 0.41):
        res = np.array([trial(rng, bias) for _ in range(REPLICATIONS)])
        rows.append((bias, res[:, 0].mean(), res[:, 1].mean()))

    print()
    print(f"    one sector of 20 split in two, {REPLICATIONS} replications,")
    print(f"    mean absolute error on the 441 input coefficients")
    print(f"    {'key bias':<12}{'key alone':>12}{'+ margins':>12}{'gain':>10}")
    for bias, ek, er in rows:
        note = "   <- the ES pilot's real error" if bias == 0.41 else ""
        print(f"    {bias:>8.0%}    {ek:>11.2f}%{er:>11.2f}%{ek - er:>9.2f} pp"
              f"{note}")

    exact, worst = rows[0], rows[-1]
    check("with true margins the error is flat, whatever the key does",
          max(abs(r[2] - rows[0][2]) for r in rows) < 0.3,
          f"{min(r[2] for r in rows):.2f}–{max(r[2] for r in rows):.2f} % "
          f"across a key bias running from 0 to 41 %. The margins repair the "
          f"key")
    check("but without them the key's bias passes straight through",
          worst[1] > 1.5 * exact[1],
          f"{exact[1]:.2f} % at an exact key against {worst[1]:.2f} % at "
          f"+41 % — the error grows with the bias because nothing corrects it")
    check("so the value of the margins is conditional on key quality, which "
          "refines CORE_025",
          (worst[1] - worst[2]) > 5 * (exact[1] - exact[2]),
          f"{exact[1] - exact[2]:.2f} pp at an exact key against "
          f"{worst[1] - worst[2]:.2f} pp at +41 %, a factor of "
          f"{(worst[1] - worst[2]) / (exact[1] - exact[2]):.0f}. Jeong "
          f"compares with-margins against without-margins at ONE key quality "
          f"and concludes they are equivalent; that holds only where he "
          f"measured")
    check("and at the Spanish pilot's real key error the margins roughly halve "
          "the error",
          worst[2] < 0.65 * worst[1],
          f"{worst[1]:.2f} % down to {worst[2]:.2f} %. The pilot estimated "
          f"33.73 % against a true 23.95 % (OQ-S-05) — +41 % in relative "
          f"terms. This is what the data request OQ-S-05 leaves open is worth")

    print()
    print("    NOT a replication of CORE_025: this implementation lands near")
    print(f"    {exact[2]:.0f} % where Jeong reports 11.30 %, a factor of 2.3, and the")
    print("    difference is left standing rather than tuned away. Absolute")
    print("    levels here carry no authority — the design is uniform draws")
    print("    with no zeros, no skew and no block structure. The comparison")
    print("    inside one consistent setup is what it can support.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
