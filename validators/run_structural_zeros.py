"""
`OQ-S-03`'s last residue: may a split open a channel the parent did not have?

WHAT WAS LEFT
--------------
Three residues, two already resolved for this engine. The sign-crossing
denominator does not exist here (v1.21) and the price basis turned out to be
sourced and merely unconnected (v1.22). What survived, in the entry's own words:

    `Z[i,p] · share = 0` whenever the parent cell is zero, which is the outcome
    CORE_026 p. 159 prescribes for RACE. **What remains NOT SPECIFIED is whether
    a zero SHOULD always survive** — whether a split may legitimately open a
    channel the parent did not have. Nothing loaded says.

No source will say. But the question has an observable form, and published
tables answer it: **aggregate two real sectors and ask whether a zero in the
aggregate ever conceals a live channel in the detail underneath it.** That is
the engine's operation run backwards, on data where the detail is known — the
same setup `OQ-S-04` used at v1.12 to measure the internal block.

THE ARITHMETIC SAYS IT CAN HAPPEN
-----------------------------------
For non-negative cells a zero sum forces zero parts, so the interesting case is
the one this project has spent five entries on: **negatives**. `a + b = 0` with
`a = −b ≠ 0` is a zero aggregate over a live channel, and an engine that
preserves the zero would then destroy two real flows. The hazard is genuine and
cannot be argued away — only counted.

WHAT THE COUNT SHOWS
----------------------
1,403 sibling pairs across three published tables — Italy 65, Spain 65, the UK
104 — and every off-block row cell, column cell and 2x2 internal block they
generate:

    table            pairs   aggregated cells   zero      concealing a channel
    Italy ixi 65       219             27,813   1,266 (4.6 %)              0
    Spain pxp 65       219             27,813   2,197 (7.9 %)              0
    UK pxp 104         965            197,825   3,121 (1.6 %)              0

**253,451 aggregated cells, 6,584 of them zero, and not one conceals a non-zero
component.** The offsetting-negatives case does not occur once.

So preserving a structural zero through a split is not merely the sourced
behaviour (CORE_026 p. 159) and not merely what the arithmetic does — on every
published table this project holds, it is also what the detailed data does.

WHAT THIS DOES NOT SETTLE
---------------------------
Two things, and they are worth stating because the measurement looks stronger
than it is.

1. **A published zero is not necessarily a structural zero.** It may be a
   suppressed cell, a rounded-to-zero flow, or a genuinely absent channel, and
   these tables do not distinguish them. What is measured is that the zero is
   consistent all the way down, not that the channel is impossible.
2. **Aggregating two published sectors is not the same act as splitting one.**
   The parent this engine splits is a sector nobody published detail for; the
   parents here are pairs whose detail happens to exist. That is the same
   limitation `OQ-S-04` v1.12 carries, and for the same reason it is the best
   evidence available rather than an ideal one.

Run:
    python3 validators/run_structural_zeros.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def scan(Z: np.ndarray, pairs) -> tuple[int, int, int, int]:
    """(cells, zero aggregates, zeros concealing a channel, of which signed)."""
    n = Z.shape[0]
    cells = zeros = concealing = signed = 0
    for i, j in pairs:
        others = [k for k in range(n) if k not in (i, j)]
        for k in others:
            for a, b in ((Z[i, k], Z[j, k]), (Z[k, i], Z[k, j])):
                cells += 1
                if a + b == 0:
                    zeros += 1
                    if a != 0 or b != 0:
                        concealing += 1
                        signed += (a < 0 or b < 0)
        block = (Z[i, i], Z[i, j], Z[j, i], Z[j, j])
        cells += 1
        if sum(block) == 0:
            zeros += 1
            if any(v != 0 for v in block):
                concealing += 1
                signed += any(v < 0 for v in block)
    return cells, zeros, concealing, signed


def main() -> int:
    import run_internal_block as IB

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    tables = IB._tables()
    if not tables:
        print("no fixture available")
        return 0

    print(f"\n    {'table':<16}{'pairs':>7}{'aggregated cells':>19}"
          f"{'zero':>10}{'concealing':>13}")
    tot_cells = tot_zero = tot_conceal = tot_signed = 0
    for label, Z, x, codes in tables:
        pairs = IB._sibling_pairs(codes, Z, x)
        cells, zeros, concealing, signed = scan(np.asarray(Z, float), pairs)
        tot_cells += cells
        tot_zero += zeros
        tot_conceal += concealing
        tot_signed += signed
        print(f"    {label:<16}{len(pairs):>7}{cells:>19,}"
              f"{zeros:>10,}{concealing:>13,}"
              f"   ({zeros / cells:.1%} zero)")

    check("no zero aggregate anywhere conceals a live channel",
          tot_conceal == 0,
          f"{tot_conceal} in {tot_cells:,} aggregated cells, of which "
          f"{tot_zero:,} are zero — so preserving a structural zero through a "
          f"split destroys nothing that these tables contain")

    check("and the arithmetic hazard that would allow it does not occur",
          tot_signed == 0,
          f"the only way a zero aggregate can cover a live channel is "
          f"offsetting signs, and there are {tot_signed} such cases — in the "
          f"tables that gave this project five distinct kinds of negative")

    check("the rule is not vacuous: it decides a real share of the table",
          tot_zero > 0.01 * tot_cells,
          f"{tot_zero:,} zero aggregates, {tot_zero / tot_cells:.1%} of all "
          f"cells — 1.6 % of the UK table and 7.9 % of the Spanish one, so "
          f"'zeros survive' is a rule that fires often, not an edge case")

    print()
    print("    NOT settled: a published zero may be suppressed or rounded")
    print("    rather than structural, and these tables cannot tell those")
    print("    apart; and aggregating two published sectors is not the same")
    print("    act as splitting one nobody published detail for. Same limits")
    print("    as OQ-S-04 v1.12, and the same reason for accepting them.")
    print("    D_open_questions.md OQ-S-03.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
