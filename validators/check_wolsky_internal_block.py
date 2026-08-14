"""
Does the engine's internal block agree with the only sourced rule for it?

WHY THIS FILE EXISTS
--------------------
`src/quadrium/disaggregation.py` fills the block of cells where the new
subsectors trade with each other by double proportionality, damped on the
diagonal by `Scenario.internal_block_alpha`. Until CORE_031 was obtained, that
carried the comment "PROJECT CHOICE, no source" -- the weakest thing in the
MVP, and known to be so.

CORE_031 (Zhao 2014, implementing Wolsky 1984) states the rule. In flows, with
`N+1` the sector being split into `n` new ones and rho the input weights:

    z*_{N+k, N+k'} = rho_k  z_{N+1,N+1}  rho_k'                      (eq. 14)
    sum_k sum_k'  z*_{N+k, N+k'} = z_{N+1,N+1}                       (eq. 15)

That is exactly double proportionality with NO damping, and eq. (15) says it
conserves the parent cell by construction -- no balancing step required.

So this file checks two things that were previously only asserted:

  1. at alpha = 1.0 the engine reproduces eq. (14) cell by cell and eq. (15)
     exactly, which anchors the undamped case to a rank-5 source;
  2. at the project default alpha = 0.5 it does NOT, and by how much -- which
     is the honest statement of what the default costs.

It also checks Zhao's two margin identities on the off-block columns and rows,
eq. (8) and eq. (11), which the engine should satisfy by construction.

WHAT IT DOES NOT DO
-------------------
It does not claim alpha = 1.0 is right. Wolsky's rule assumes the new sectors
have identical technologies and sell to others in proportion to their weights;
an economist splitting hotels from restaurants may well believe a subsector
buys from itself less than proportionality implies, which is what the damping
expresses. The point is that the departure is now measurable against something,
instead of being a number with nothing behind it.

Run:
    python3 validators/check_wolsky_internal_block.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quadrium.disaggregation import split_sector          # noqa: E402
from quadrium.models import (AllocationKey, IOTable,       # noqa: E402
                              ProxyStrength, Scenario)

# CORE_031 p. 3 defines the weights as output shares summing to one; this
# fixture uses three unequal shares so that a bug that happens to work for
# equal weights cannot pass.
NEW = ["ACC1", "ACC2", "ACC3"]
RAW = [12500.0, 34200.0, 9100.0]


def fixture() -> tuple[IOTable, dict, int]:
    codes = ["AGR", "MAN", "ACC", "OTH"]
    Z = np.array([
        [20.0, 180.0,  60.0,  15.0],
        [35.0, 420.0, 110.0, 140.0],
        [ 2.0,  18.0,  12.0,  25.0],
        [25.0, 150.0,  -8.0, 220.0],     # a negative, on purpose
    ])
    Y = np.array([[90.0, 40.0], [380.0, 500.0], [300.0, 60.0], [700.0, 150.0]])
    VA = np.array([[150.0, 620.0, 140.0, 600.0]])
    X = Z.sum(axis=1) + Y.sum(axis=1)
    table = IOTable(table_id="wolsky-fixture", country="--", year=2022,
                    unit="units", classification="none",
                    sector_codes=codes, sector_labels=list(codes),
                    Z=Z, Y=Y, Y_labels=["HH", "EXP"],
                    VA=VA, VA_labels=["GVA"], X=X,
                    source="synthetic, this file")
    key = AllocationKey(key_id="k", applies_to="output", new_sector_codes=NEW,
                        raw_values=RAW, source="fixture", source_year=2022,
                        strength=ProxyStrength.STRONG)
    return table, {"k": key}, table.index_of("ACC")


def run(alpha: float):
    table, keys, p = fixture()
    sc = Scenario(scenario_id="w", label="Wolsky check",
                  keys_by_block={b: "k" for b in
                                 ("output", "final_demand", "value_added",
                                  "intermediate_rows", "intermediate_cols")},
                  internal_block_alpha=alpha)
    seed = split_sector(table, "ACC", NEW, NEW, sc, keys)
    pos = seed["new_positions"]
    return table, seed, seed["Z"][np.ix_(pos, pos)], p


def main() -> int:
    rho = np.array(RAW) / sum(RAW)
    bad = 0

    # ---- 1. alpha = 1.0 against Wolsky eq. (14) and (15) -----------------
    table, seed, block, p = run(1.0)
    z_pp = table.Z[p, p]
    wolsky = z_pp * np.outer(rho, rho)
    d14 = float(np.abs(block - wolsky).max())
    d15 = float(abs(block.sum() - z_pp))
    print("CORE_031 eq. (14)  z*_kk' = rho_k z_pp rho_k'   alpha=1.0")
    print(f"  max |engine - Wolsky| : {d14:.3e}   ({'OK' if d14 < 1e-12 else 'FAIL'})")
    print("CORE_031 eq. (15)  the block conserves the parent cell")
    print(f"  |sum - z_pp|          : {d15:.3e}   ({'OK' if d15 < 1e-12 else 'FAIL'})")
    bad += (d14 >= 1e-12) + (d15 >= 1e-12)

    # ---- 2. Zhao eq. (8) and (11) on the margins -------------------------
    # Every OTHER row/column of the split sector must still sum to what it was:
    # the engine splits them proportionally, which is Zhao's DIM and DOM.
    Z, pos = seed["Z"], seed["new_positions"]
    others = [i for i in range(Z.shape[0]) if i not in pos]
    col_res = max(abs(Z[i, pos].sum() - table.Z[table_i, p])
                  for i, table_i in zip(others, range(table.n)) if table_i != p)
    row_res = max(abs(Z[pos, j].sum() - table.Z[p, table_j])
                  for j, table_j in zip(others, range(table.n)) if table_j != p)
    print("CORE_031 eq. (8)   sum_k z*_{i,N+k} = z_{i,N+1}  (inputs, DIM)")
    print(f"  max residual          : {col_res:.3e}   ({'OK' if col_res < 1e-9 else 'FAIL'})")
    print("CORE_031 eq. (11)  sum_k z*_{N+k,i} = z_{N+1,i}  (outputs, DOM)")
    print(f"  max residual          : {row_res:.3e}   ({'OK' if row_res < 1e-9 else 'FAIL'})")
    bad += (col_res >= 1e-9) + (row_res >= 1e-9)

    # ---- 3. eq. (15) now holds at EVERY alpha, which it did not ----------
    # The old form scaled the diagonal and left the off-diagonal at 1.0, so any
    # alpha != 1 leaked. At the old default of 0.5 the block summed to 9.285
    # against a parent cell of 12.000, -22.6 %, and a balancing step that knows
    # nothing about the block had to repair it. The off-diagonal now pays for
    # the diagonal -- beta = (1 - alpha*d)/(1 - d) -- so the block conserves the
    # parent cell whatever alpha is. See OQ-S-04.
    print()
    print("CORE_031 eq. (15) across the alpha range, after the v1.12 fix")
    worst = 0.0
    for a in (0.5, 1.0, 1.5, 2.0):
        _, _, blk, _ = run(a)
        gap = blk.sum() - z_pp
        worst = max(worst, abs(gap))
        print(f"  alpha = {a:<4} block sum {blk.sum():>10.6f}   "
              f"parent {z_pp:.6f}   shortfall {gap:+.2e}")
    print(f"  worst |shortfall|     : {worst:.3e}   "
          f"({'OK' if worst < 1e-9 else 'FAIL'})")
    print("  The old form leaked -22.6 % of the parent cell at alpha = 0.5.")
    bad += worst >= 1e-9

    print()
    print("FAIL" if bad else "All checks passed.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
