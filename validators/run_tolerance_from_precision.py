"""
`OQ-B-02`, measured on every fixture the project holds.

The question — what discrepancy in an accounting identity is acceptable — has
been open since v1.1 and has refused three candidates, all of them convergence
thresholds on dimensionless multipliers or stopping rules for an iteration. This
file does not close it. It establishes the **floor underneath it**, which is a
different quantity and is derivable without any source stating it:

    a table published to `d` decimals cannot have an `n`-term identity checked
    more tightly than `0.5·10^-d·n`, even when the unrounded accounts balance
    exactly.

Below that line, "balanced" and "not balanced" are the same observation. Any
tolerance tighter than it is measuring the publisher's rounding, not the
accounts. This is arithmetic on the source's own stated precision — not a
project choice — and it is a floor no acceptance criterion may go below. The
acceptance threshold ABOVE the floor stays unsourced and stays a project choice.

WHY THIS WAS NOT NOTICED FOR NINE VERSIONS
-------------------------------------------
`ABS_TOL = 1e-6` has been right the whole time, by accident. The project's
founding fixture is the ONS table, and **the ONS publishes unrounded** — only
1 % of its cells are whole numbers. A flat absolute tolerance in currency units
is very nearly correct for a source that does not round, and wrong for every
source that does. Spain then balanced its own rounded figures to 1e-11, so it
did not object either. Italy is the first fixture to publish rounded figures
that were rounded AFTER balancing, and it is off by 0.08.

THE FINDING WORTH CARRYING PAST THIS QUESTION
----------------------------------------------
Whether a published table balances at its own printed precision is **a property
of the office, not of the framework**. Spain and Italy publish the same dataset,
under the same regulation, on the same methodology, through the same API. Spain
balances to 1e-11; Italy balances only to rounding. Nothing in ESA 2010 requires
either, and an engine that assumes the Spanish behaviour will reject Italy as
defective.

Run:
    python3 validators/run_tolerance_from_precision.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

from quadrium.precision import (  # noqa: E402
    assertable_tolerance, printed_decimals,
)

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def _fixtures():
    """Every table the project can load, with the row identity it promises."""
    out = []

    from quadrium.eurostat import load_iot
    from quadrium.io_loader import load_ine_tio, load_ine_tod

    for label, fname in (("Eurostat ES pxp", "naio_10_cp1700_ES_2022.json"),
                         ("Eurostat IT ixi", "naio_10_cp1750_IT_2022.json")):
        p = ROOT / "data" / "eurostat" / fname
        if not p.exists():
            continue
        t = load_iot(p, variant="domestic")
        out.append((label, np.concatenate([t.Z.ravel(), t.Y.ravel(), t.X]),
                    t.n + t.Y.shape[1],
                    float(np.abs(t.Z.sum(1) + t.Y.sum(1) - t.X).max())))

    p = ROOT / "data" / "ine" / "cne_tio_22.xlsx"
    if p.exists():
        t = load_ine_tio(p, unbalanced="residual_column")
        out.append(("INE TIO ES", np.concatenate([t.Z.ravel(), t.Y.ravel(), t.X]),
                    t.n + t.Y.shape[1],
                    float(np.abs(t.Z.sum(1) + t.Y.sum(1) - t.X).max())))

    p = ROOT / "data" / "ine" / "cne_tod_22.xlsx"
    if p.exists():
        s = load_ine_tod(p)
        out.append(("INE TOD ES", np.concatenate([s.V.ravel(), s.q, s.g]),
                    s.n_activities, float(np.abs(s.V.sum(1) - s.q).max())))

    p = ROOT / "UK_IOAT_2023_domestic_ixi.xlsx"
    if p.exists():
        import run_uk_iot as uk
        t = uk.load_iot(p)
        Z, x = t["Z"], t["x"]
        # `P3 S1` is the S13+S14+S15 subtotal; including it double counts.
        FD = np.column_stack([v for k, v in t["FD"].items() if k != "P3 S1"])
        out.append(("ONS UK pxp", np.concatenate([Z.ravel(), FD.ravel(), x]),
                    Z.shape[1] + FD.shape[1],
                    float(np.nanmax(np.abs(Z.sum(1) + FD.sum(1) - x)))))
    return out


def main() -> int:
    fixtures = _fixtures()
    if not fixtures:
        print("no fixture available")
        return 0

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)
    print(f"  {'fixture':<18}{'decimals':>10}{'n':>5}{'residual':>12}"
          f"{'floor':>12}   flat 1e-6")
    rounded, unrounded, rejected = [], [], []
    for label, values, n, resid in fixtures:
        d = printed_decimals(values)
        floor = assertable_tolerance(values, n)
        (rounded if d is not None else unrounded).append(label)
        if resid > 1e-6:
            rejected.append(label)
        print(f"  {label:<18}{('unrounded' if d is None else d):>10}{n:>5}"
              f"{resid:>12.3g}{floor:>12.4g}   "
              f"{'accepts' if resid <= 1e-6 else 'REJECTS'}")
    print()

    # 1 -- every fixture sits inside its own floor. This is the claim.
    for label, values, n, resid in fixtures:
        floor = assertable_tolerance(values, n)
        check(f"{label} balances as tightly as its precision permits",
              resid <= floor,
              f"{resid:.3g} against a floor of {floor:.4g}")

    # 2 -- and the flat tolerance does not survive that, on real published data.
    check("the flat ABS_TOL = 1e-6 rejects a correctly published table",
          len(rejected) == 1 and rejected[0].startswith("Eurostat IT"),
          f"{', '.join(rejected)} — 0.08 across 73 cells rounded to two "
          f"decimals, which is inside what that source can distinguish")

    # 3 -- why it went unnoticed: the founding fixture does not round.
    check("the fixture the tolerance was written against is unrounded",
          any(l.startswith("ONS") for l in unrounded),
          f"unrounded: {', '.join(unrounded) or 'none'} — a flat absolute "
          f"tolerance is nearly right for a source that does not round, and "
          f"wrong for every source that does")

    # 4 -- precision varies WITHIN one dataset, so it cannot be configured
    #      per-source and must be read off the values.
    es = next((v for l, v, _, _ in fixtures if l == "Eurostat ES pxp"), None)
    it = next((v for l, v, _, _ in fixtures if l == "Eurostat IT ixi"), None)
    if es is not None and it is not None:
        check("Eurostat publishes Spain and Italy at DIFFERENT precisions",
              printed_decimals(es) != printed_decimals(it),
              f"{printed_decimals(es)} decimal for ES, {printed_decimals(it)} "
              f"for IT — same dataset family, same regulation, so the precision "
              f"cannot be a per-dataset constant and must be read off the data")

        # 5 -- and the residual is NOT predicted by the floor. The floor is a
        #      ceiling on what can be asserted, not an expectation.
        es_r = next(r for l, _, _, r in fixtures if l == "Eurostat ES pxp")
        it_r = next(r for l, _, _, r in fixtures if l == "Eurostat IT ixi")
        check("balancing at printed precision is the office's choice, not ESA's",
              es_r < 1e-9 < it_r,
              f"Spain {es_r:.3g}, Italy {it_r:.3g} — the INE balanced its "
              f"rounded figures; Istat rounded its balanced ones. Both are "
              f"correct and an engine that assumes the first rejects the second")

    # 6 -- what this does NOT settle, stated so it is not read as closed.
    print()
    print("    What this does not answer: how far an identity may be out and")
    print("    still be accepted. That number is above the floor, no loaded")
    print("    source states it, and it stays a PROJECT CHOICE — as does the")
    print("    handover threshold, which is a third quantity again (`M-039`).")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
