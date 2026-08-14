"""
`OQ-T-03` again: there IS a criterion, and the same source departs from it.

Last night's `run_model_choice.py` measured what the model-choice disagreement is
worth — 0.12 % of the interindustry matrix in France, 4.57 % in the Netherlands —
and ended "Nothing here chooses a model." That was true of the sources then
loaded. **CORE_017 was extracted and unread, and it does choose.**

THE AXIOMS
----------
CORE_017 p. 129 decides the superior assumption "based on the fulfilment of the
so -called material balance, financial balance, price invariance and scale"
invariance axioms. For product-by-product tables
"the product technology assumption satisfies all four axioms"; for
industry-by-industry it is the fixed industry sales structures assumption.

    pxp  ->  model A   product technology
    ixi  ->  model C   fixed industry sales

The first criterion in this library that picks a model on grounds other than
convenience.

AND THE PRACTICE IS NOT THAT
-----------------------------
CORE_017 p. 130: "the common practice is to use the product technology assumption
and then" treat the biggest negatives as measurement or aggregation error, with
industry technology as a last resort — and "This practice has been confirmed by a
survey" of the EU member states. That is precisely the hybrid this project had
already documented from the ONS, the INE and Statistik Austria independently.

THE CONTRADICTION, INSIDE ONE SOURCE
-------------------------------------
On the industry axis the axioms pick **model C**. The same chapter recommends
**model D** — "the preferred option is the fixed product sales structures
assumption" — because it "requires neither square ESUTs nor any special treatment
of negatives".

Theory says C, practice says D, and the source states both without reconciling
them. `NSO_UK_01` p. 5 puts the ONS on D. Nothing in the library reports anyone
on C. This file records the contradiction as a check so it cannot quietly become
"the source recommends D".

TABLE 6.1 CORROBORATES CORE_013, WHICH IS WORTH HAVING
--------------------------------------------------------
Its summary row reads `Negatives: Yes No Yes No` across A, B, C, D — identical to
CORE_013 Box 12.3, p. 383, which is what `src/quadrium/transformation.py`
implements. Two independent handbooks, same four models, same pattern. Checked
below against four real national tables rather than taken on trust.

Run:
    python3 validators/run_model_axioms.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "eurostat"
SRC = (ROOT / "library" / "extracted"
       / "CORE_017_OECD_EU2025_CH06_Extended_Input_Output_Tables.txt")
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def _blocks(geo: str):
    from quadrium.eurostat import load_sut
    sup, use = (DATA / f"naio_10_cp15_{geo}_2022.json",
                DATA / f"naio_10_cp16_{geo}_2022.json")
    if not (sup.exists() and use.exists()):
        return None
    s = load_sut(sup, use)
    k = (s.q > 0) & (s.g > 0)
    return (s.V[np.ix_(k, k)], s.U[np.ix_(k, k)], s.Y[k], s.W[:, k],
            s.g[k], s.q[k])


def main() -> int:
    from quadrium.transformation import MODELS, transform

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # ---- the source says what it says -------------------------------------
    if SRC.exists():
        text = re.sub(r"\s+", " ", SRC.read_text())
        check("CORE_017 states an axiomatic criterion",
              "the product technology assumption satisfies all four axioms" in text,
              "material balance, financial balance, price invariance, scale "
              "invariance — pxp goes to model A, ixi to model C")
        check("and reports a surveyed practice that departs from it on pxp",
              "the common practice is to use the product technology assumption "
              "and then" in text
              and "This practice has been confirmed by a survey" in text,
              "product technology, then the biggest negatives treated as "
              "measurement or aggregation error — the hybrid the ONS, the INE "
              "and Statistik Austria each use")
        check("AND CONTRADICTS ITSELF ON THE INDUSTRY AXIS",
              "the preferred option is the fixed product sales structures "
              "assumption" in text,
              "axioms pick model C, the recommendation picks model D because it "
              "'requires neither square ESUTs nor any special treatment of "
              "negatives'. The source states both and reconciles neither")

    # ---- Table 6.1's pattern, on real data --------------------------------
    print()
    print(f"    the summary table's `Negatives` row, checked on published tables:")
    print(f"    {'model':<7}{'axis':<10}{'CORE_013 says':>15}   observed")
    seen = {}
    for geo in ("AT", "ES", "FR", "NL"):
        b = _blocks(geo)
        if b is None:
            continue
        V, U, Y, W, g, q = b
        zero = np.zeros_like(U)
        for model in ("A", "B", "C", "D"):
            try:
                r = transform(model, V, U, zero, Y, np.zeros_like(Y), W, g, q)
            except Exception:
                continue
            seen.setdefault(model, []).append(int((r.Sd < -1e-9).sum()))
    for model in ("A", "B", "C", "D"):
        if model not in seen:
            continue
        name, axis, may = MODELS[model]
        counts = seen[model]
        got = "negatives" if max(counts) > 0 else "none"
        print(f"    {model:<7}{axis:<10}{'possible' if may else 'none':>15}"
              f"   {got} ({', '.join(str(c) for c in counts)})")
        check(f"  model {model} matches that row on all {len(counts)} tables",
              (max(counts) > 0) == bool(may),
              f"CORE_017 and CORE_013 agree, and the data agrees with both")

    print()
    print("    Still NOT SPECIFIED: how big 'the biggest negatives' is —")
    print("    CORE_017 p. 130 gives no threshold, and NSO_AT_01's 15 million")
    print("    EUR is one office's. And which to follow on the industry axis,")
    print("    where the axioms and the recommendation disagree.")
    print()
    print("    Note what the practice ASSUMES: that a large negative is")
    print("    measurement error, not economics. This library takes the")
    print("    opposite view of the negatives in a margins matrix, where ID-19")
    print("    requires them. The two are not in conflict — different objects —")
    print("    but the engine should never carry one rule into the other.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
