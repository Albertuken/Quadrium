"""
`OQ-S-03`: negatives, zeros and price bases in disaggregation — what is actually
at risk.

The entry has three residues after v1.4, all `NOT SPECIFIED`: structural zeros,
the price basis, and "a weight whose own denominator is zero or crosses zero".
No source has closed them and none of tonight's reading does either. What can be
done is to say which of the three is a real hazard for THIS engine and what the
others cost.

1. SIGNS AND SIGN-CROSSING DENOMINATORS — safe here, and for a reason
---------------------------------------------------------------------
CORE_024's adjustment divides by the sum of the sub-flows that have no proxy, and
that sum can cross zero. **This engine does not have that division.**
`_column_shares` normalises by `sum_b (w_col[b] · m[i,b])`, and both factors are
non-negative by construction — the allocation key rejects negative raw values and
`input_profiles` rejects a negative intensity. The denominator cannot cross zero;
it can only reach it, and that case raises.

So a negative parent cell splits by multiplication into negative sub-cells, which
is CORE_031's behaviour exactly. Exercised below on the project's worst real
cell: `K64` → `L68A` in the UK table, −20,770.99, split from both sides.

2. ZEROS — preserved, and it matches the one sourced rule
----------------------------------------------------------
`Z[i,p] · share = 0` whenever `Z[i,p] = 0`, so a structural zero survives any
split. That is the same outcome CORE_026 p. 159 prescribes for RACE, where the
correction factor is set to 1 on a zero entry. The engine gets it from the
arithmetic rather than from a rule, and the two agree.

What is still `NOT SPECIFIED` is whether a zero SHOULD always survive — whether a
split can legitimately open a channel the parent did not have. Nothing loaded
says.

3. PRICE BASIS — settled at v1.22: not a choice, a definition, and now the
   measurement below is its cost, not its ambiguity
--------------------------------------------------------------------------
The engine splits a parent's input column by that column's own structure, so the
price basis of the table is the template of every split built on it. This project's
own `A_core_accounting_spec.md` already states, sourced twice (CORE_005 ¶36.30/
¶36.68, CORE_006 ¶9.09), that a symmetric IOT — the object this engine actually
splits — **is basic-price data by definition**, not a modelling choice. Austria
2022 publishes both valuation matrices, so the cost of using the wrong one can be
measured directly:

    total, purchasers' prices     2,164,466
    total, basic prices           2,079,557        3.9 % apart
    input structure, total variation distance
        median 0.045    p90 0.084    max 0.200
        42 % of industries shift by more than 5 points

**A median of four and a half points, and a fifth of the structure in the worst
industry — the cost of feeding this engine a purchasers'-price proxy for a
basic-price parent cell.** The basis itself is not a free parameter; a
compiler who hands the engine anything but basic-price data is introducing this
mismatch, measured rather than assumed.

Run:
    python3 validators/run_disagg_signs_zeros_prices.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "eurostat"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    from quadrium.io_loader import load_uk_analytical_iot
    from quadrium.models import (AllocationKey, ProxyStrength, Scenario,
                                  SplitSpec)
    from quadrium.disaggregation import split_sector

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # ---- 1 and 2: the worst negative in the project's own data -----------
    uk_file = ROOT / "UK_IOAT_2023_domestic_ixi.xlsx"
    if uk_file.exists():
        t = load_uk_analytical_iot(uk_file)
        for code, where in (("L68A", "column"), ("K64", "row")):
            i = t.index_of(code)
            vec = t.Z[:, i] if where == "column" else t.Z[i, :]
            new = [code + "a", code + "b"]
            keys = {"k": AllocationKey(key_id="k", applies_to="output",
                                       new_sector_codes=new,
                                       raw_values=[70.0, 30.0],
                                       source="test fixture", source_year=2022,
                                       strength=ProxyStrength.WEAK)}
            spec = SplitSpec(code, new, new, keys_by_block={"output": "k"})
            res = split_sector(t, code, new, new,
                               Scenario(scenario_id="S", label="s"), keys, spec)
            Z, pos = res["Z"], res["new_positions"]
            before = float(vec.sum())
            after = float(sum(Z[:, q].sum() for q in pos) if where == "column"
                          else sum(Z[q, :].sum() for q in pos))
            zeros_before = int((vec == 0).sum())
            sub = np.concatenate([Z[:, q] if where == "column" else Z[q, :]
                                  for q in pos])
            check(f"splitting {code}, whose {where} carries the −20,771 cell, "
                  f"stays finite and conserves",
                  np.isfinite(Z).all() and abs(after - before) < 1e-6,
                  f"{before:,.1f} before, {after:,.1f} after "
                  f"({after - before:+.4f}); {int((vec < 0).sum())} negative "
                  f"cell(s) split into {int((sub < 0).sum())}")
            check(f"  and every structural zero in that {where} survives",
                  zeros_before > 0
                  and int((sub == 0).sum()) >= 2 * zeros_before - 1,
                  f"{zeros_before} zeros became {int((sub == 0).sum())} across "
                  f"two subsectors — `Z·share = 0`, which is the outcome "
                  f"CORE_026 p. 159 prescribes for RACE")
    else:
        print("  (UK fixture absent; parts 1 and 2 need it)")

    # ---- 3: the price basis, measured ------------------------------------
    files = {k: DATA / f"naio_10_{c}_AT_2022.json" for k, c in
             (("use", "cp16"), ("margins", "cp1620"), ("taxes", "cp1630"))}
    if all(p.exists() for p in files.values()):
        from quadrium.eurostat import _Cube
        use, mg, tx = (_Cube(json.loads(files[k].read_text()))
                       for k in ("use", "margins", "taxes"))
        prods = [p for p in use.index["prd_ava"]
                 if p.startswith("CPA_") and p != "CPA_TOTAL"]
        inds = [i for i in use.index["ind_use"]
                if i in mg.index["ind_use"] and i not in ("TU", "TOTAL", "TFU")]
        P = np.array([[use.at(ind_use=i, prd_ava=p) or 0.0 for i in inds]
                      for p in prods], float)
        M = np.array([[mg.at(ind_use=i, cpa2_1=p) or 0.0 for i in inds]
                      for p in prods], float)
        T = np.array([[tx.at(ind_use=i, cpa2_1=p) or 0.0 for i in inds]
                      for p in prods], float)
        B = P - M - T
        dist = []
        for j in range(len(inds)):
            a, b = P[:, j], B[:, j]
            if a.sum() > 0 and b.sum() > 0:
                dist.append(0.5 * float(np.abs(a / a.sum() - b / b.sum()).sum()))
        dist = np.array(dist)
        print()
        print(f"    Austria 2022, {P.shape[0]} products x {len(inds)} users")
        print(f"      purchasers' prices {P.sum():>14,.0f}")
        print(f"      basic prices       {B.sum():>14,.0f}   "
              f"{100 * (P.sum() - B.sum()) / P.sum():.1f} % apart")
        print(f"      input structure shifts by (total variation): median "
              f"{np.median(dist):.4f}, p90 {np.percentile(dist, 90):.4f}, "
              f"max {dist.max():.4f}")
        print()
        check("using the wrong basis as a proxy would move the template a "
              "split is built on, by this much",
              np.median(dist) > 0.02,
              f"median {np.median(dist):.1%} of the input structure, up to "
              f"{dist.max():.1%}; {(dist > 0.05).mean():.0%} of industries move "
              f"more than 5 points — the cost of the mismatch, not evidence "
              f"the basis is undecided")
        check("and the totals differ by enough to matter on their own",
              (P.sum() - B.sum()) / P.sum() > 0.02,
              f"{100 * (P.sum() - B.sum()) / P.sum():.1f} % — margins and taxes "
              f"on intermediate use")

    print()
    print("    Settled at v1.22: the price basis is not a free parameter.")
    print("    A_core_accounting_spec.md already states, sourced (CORE_005")
    print("    36.30/36.68, CORE_006 9.09), that a symmetric IOT -- the object")
    print("    this engine splits -- is basic-price data by definition. The")
    print("    measurement above is the cost of feeding it a purchasers'-price")
    print("    proxy instead, not evidence the choice is open.")
    print()
    print("    Still NOT SPECIFIED:")
    print("      * whether a structural zero SHOULD always survive a split, or")
    print("        whether a split may open a channel the parent lacked.")
    print("      CORE_025 pp. 851-863 remains untranslated; CORE_082 remains")
    print("      the named route for a comparative assessment.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
