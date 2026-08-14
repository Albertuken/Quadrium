"""
`OQ-C-04`, use half: the engine had two of the compiler's three steps swapped.

CORE_009 ¶6.36, p. 164 states how the intermediate consumption block is filled,
and the order carries the method:

  1. estimate total intermediate consumption by industry;
  2. enter known values of intermediate consumption by product and industry;
  3. use cost structures to estimate **all other values**.

Step 3 applies to what step 2 left. A known cell reduces the amount the structure
has to distribute; it does not sit on top of a distribution that already spent
the whole total.

**The engine did steps 2 and 3 the other way round.** `split_sector` filled every
cell from the structure against the full column total and then wrote
`user_constraints` over the top. The remaining cells absorbed nothing, so the
column total moved by exactly the amount pinned away — silently, into a balancing
step that has no way to know which cell was authoritative.

Measured before the fix, on the Spanish table: pinning one cell of `H51` at half
its value took that column from 4,280.520 to 3,904.200, losing 376.320.

WHAT THE FIX DELIBERATELY DOES NOT DO
--------------------------------------
A pin ABOVE the column's own total is left alone. That is a real capability of
this engine — the analyst asserts a figure the allocation key disagrees with, the
balancer reconciles it, and the provenance machinery is required to stop calling
the cell "pinned" once the solver has moved it. **The first draft of this fix
raised an error there and removed that path**;
`test_a_pinned_cell_the_solver_moved_stops_claiming_to_be_pinned` caught it
immediately. Recorded because the near-miss is the point: a fix derived from a
source can still break a capability the source says nothing about.

A SECOND ERROR THIS FLUSHED OUT, FROM THE NIGHT BEFORE
-------------------------------------------------------
Running the suite after the fix also failed `test_project_folder_is_reproducible`
with `MarginImbalanceError`: margins summing to 12 and 12, differing by 2.7e-14,
against a floor of 1.2e-14. That floor came from `assertable_tolerance`'s float64
branch, added for `OQ-B-02`.

**It was overreaching and could not be repaired by widening it.** That branch
bounds the error of summing the vector it is handed; a margin that is itself a
row or column sum arrives already carrying error no bound on the last operation
can see. Even the textbook `(n-1)·u·Σ|x|` comes out below the observed residual.
The precision floor is sound for PUBLISHED data, which is what it was derived
for. For computed margins `gras.py` now uses `PROJECT_COMPUTED_MARGIN_REL`, a
relative bound labelled as the project choice it is.

Run:
    python3 validators/run_use_compilation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    fixture = ROOT / "data" / "eurostat" / "naio_10_cp1700_ES_2022.json"
    if not fixture.exists():
        print(f"fixture absent: {fixture.name}")
        return 0

    from quadrium.eurostat import load_iot
    from quadrium.models import AllocationKey, ProxyStrength, Scenario, SplitSpec
    from quadrium.disaggregation import split_sector
    from quadrium.models import CellLabel

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    table = load_iot(fixture, variant="domestic")
    code, new = "H51", ["H51a", "H51b"]
    keys = {"k": AllocationKey(key_id="k", applies_to="output",
                               new_sector_codes=new, raw_values=[60.0, 40.0],
                               source="test fixture", source_year=2022,
                               strength=ProxyStrength.WEAK)}
    spec = SplitSpec(code, new, ["a", "b"], keys_by_block={"output": "k"})

    def run(constraints=None):
        sc = Scenario(scenario_id="S", label="s",
                      user_constraints=constraints or {})
        return split_sector(table, code, new, ["a", "b"], sc, keys, spec)

    base = run()
    j = base["new_positions"][0]
    Z0 = base["Z"]
    total_before = float(Z0[:, j].sum())
    i = int(np.argmax(Z0[:, j]))
    original = float(Z0[i, j])
    pinned = original * 0.5

    con = run({f"{i},{j}": pinned})
    Z1 = con["Z"]
    total_after = float(Z1[:, j].sum())

    print(f"    splitting {code} into {new[0]} / {new[1]}, then pinning the "
          f"largest\n    cell of {new[0]}'s input column at half its value:")
    print(f"      column total, no pin  {total_before:>12,.3f}")
    print(f"      cell {i:>3} before        {original:>12,.3f}")
    print(f"      cell {i:>3} pinned to     {pinned:>12,.3f}")
    print(f"      column total, pinned  {total_after:>12,.3f}")
    print()

    check("the pinned value is honoured exactly",
          abs(Z1[i, j] - pinned) < 1e-9,
          f"{Z1[i, j]:,.3f}")
    check("and it is labelled as the analyst's own",
          con["provenance"][i, j] == CellLabel.USER_CONSTRAINT,
          con["provenance"][i, j].name)
    check("CORE_009 ¶6.36 step 3: the column total survives the pin",
          abs(total_after - total_before) < 1e-9,
          f"{total_after:,.3f} against {total_before:,.3f}; before the fix it "
          f"fell to 3,904.200, losing exactly the {original - pinned:,.3f} "
          f"pinned away")

    free = [r for r in range(Z0.shape[0]) if r != i and Z0[r, j] > 1e-9]
    ratios = np.array([Z1[r, j] / Z0[r, j] for r in free])
    check("the other cells absorb it, and all by the same factor",
          ratios.size > 2 and float(ratios.std()) < 1e-9,
          f"every free cell scaled by {ratios.mean():.4f} — the cost structure "
          f"applied to what was left, not to the whole")

    # The capability the first draft of the fix destroyed.
    over = run({f"{i},{j}": total_before * 2})
    check("a pin ABOVE the column total still goes through, not refused",
          abs(over["Z"][i, j] - total_before * 2) < 1e-6,
          "the analyst may assert a figure the key disagrees with; the balancer "
          "reconciles it and the provenance machinery stops calling it pinned "
          "once moved. The first draft raised here and broke that path")

    print()
    print("    Not testable here, and worth reading anyway:")
    print("      CORE_009 ¶6.46, p. 166 — small establishments' input structures are")
    print("        'probably unlike' the surveyed ones, so giving a small")
    print("        subsector its parent's structure has a known bias of")
    print("        unknown sign. That is what input_profiles are for.")
    print("      CORE_009 ¶6.132, p. 191 — changes in inventories are entries LESS")
    print("        withdrawals less losses, a net difference of two gross")
    print("        flows. That is why OQ-B-09 measured 18-42 % of products")
    print("        changing its sign year on year: structural, not noise.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
