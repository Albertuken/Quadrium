"""
What the answer would have been under the other proxy — measured, on the one
split in this project where the truth is published.

WHAT THIS IS FOR
-----------------
`OQ-E-02`, opened by the owner on 2026-09-06 after using the engine himself:
the workbook demands an allocation key, never says where to get one, and never
said what turns on the answer. `key_sensitivity` now re-runs the split under
every other registered key and reports what came out.

The Spanish hospitality case is the place to check it, because the INE publishes
the answer. Product 36 is CPA 55-56, and the supply table at 110 products
separates accommodation from food service, so the split is a lookup rather than
an estimate. The eight survey keys registered beside it are what an analyst
would have had if that table did not exist.

WHY IT REPORTS LEVELS AND NOT ONLY MULTIPLIERS
-----------------------------------------------
Because `run_key_sensitivity.py` said to, and it said so first. That validator
established on the UK fixture that the key cancels out of `a_ij = Z_ij / X_j`,
so the multiplier is identical at every weight, and warned in terms that *"a
perturbation study would have reported a spread of zero and been mistaken for a
finding about robustness"*.

This file's first version compared multipliers alone and duly returned 0.00 %
across eight keys spanning a factor of five in subsector size. That would have
printed a robustness figure to a user who had varied nothing capable of moving
it. The warning was already in the tree; it was not read before the code was
written, which is its own small lesson about a project that documents this
well.

WHAT IT FINDS, AND IT IS NOT SMALL
------------------------------------
On levels the same eight keys span **423.8 %**. Against the published truth of
30,717.7 for accommodation they run from 13,514 to 70,785. The key an economist
would pick on conceptual grounds — production against output — is **+40.8 %**
out; the closest is employment, the loosest conceptual match of all, at
**-11.3 %**.

That is `OQ-E-03`'s argument in one table: an engine that ranked these by
plausibility would have picked one of the worst and called it founded.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "examples"))

FAIL = []


def check(label, ok, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    if detail:
        print(f"         {detail}")
    if not ok:
        FAIL.append(label)


def main():
    table_path = ROOT / "data" / "ine" / "cne_tio_22.xlsx"
    if not table_path.exists():
        print("  the Spanish table is absent; nothing to measure.")
        return 0

    import es_hosteleria as ex
    from quadrium.io_loader import load_ine_tio
    from quadrium.models import Scenario, SplitSpec
    from quadrium.scenarios import key_alternatives, run_scenario

    table = load_ine_tio(table_path, variant="interior",
                         unbalanced="residual_column")
    keys = ex.build_keys()
    va_rows = {table.VA_labels[0]: "k_compras",
               table.VA_labels[2]: "k_gastos_personal"}
    splits = [SplitSpec("36", ex.NEW, ex.LBL,
                        keys_by_block={"output": "k_tod_produccion"},
                        va_row_keys=va_rows,
                        va_residual_row=table.VA_labels[4])]
    sc = Scenario(scenario_id="S1", label="Solo tamano",
                  description="the base, no input profiles")

    actual = run_scenario(table, splits, sc, keys)
    s = key_alternatives(table, splits, sc, keys, actual)["36"]

    # 1 -- it ran the candidates it should have, and named the one it could not.
    ran = {r["key_id"] for r in s["runs"]}
    check("every output key that did not drive the split was re-run",
          len(ran) == 8 and "k_tod_produccion" not in ran,
          f"{len(ran)} runs: {', '.join(sorted(ran))}")
    check("and the key declared for one block only is named, not dropped",
          any(k["key_id"] == "k_vab" for k in s["skipped"]),
          str(s["skipped"])[:120])
    check("a weak key is included here, unlike in corroboration",
          "k_empresas" in ran,
          "corroborate_keys skips it because it cannot be EVIDENCE; this is "
          "not evidence, it is what the answer would have been")

    # 2 -- the multiplier does not move, and the record says why.
    check("the multiplier spread is zero",
          s["multiplier_spread_pct"] < 1e-9,
          f"{s['multiplier_spread_pct']:.6f} %")
    check("and the record says that is by construction, not agreement",
          s["multiplier_invariant_by_construction"] is True,
          "an unprofiled split cancels the key out of a_ij = Z_ij / X_j, so a "
          "reader who takes this zero for agreement has been misled")

    # 3 -- the level moves enormously, which is the number that was missing.
    check("the level spread is large and is reported",
          s["level_spread_pct"] > 100,
          f"{s['level_spread_pct']:.1f} % between the widest pair")

    # 4 -- against the published truth, the conceptual favourite loses.
    gap = {r["key_id"]: r["level_gap"][0] for r in s["runs"]}
    check("the conceptually best proxy is not the best answer",
          abs(gap["k_produccion"]) > abs(gap["k_empleo"]),
          f"production-against-output is {gap['k_produccion']*100:+.1f} % out; "
          f"employment, the loosest match, is {gap['k_empleo']*100:+.1f} %")
    check("and the truth is what drove the run, so the gaps are errors",
          s["driving"] == ["k_tod_produccion"],
          "k_tod_produccion is the INE's own supply table at 110 products, "
          "not a proxy — which is what makes this case checkable at all")

    print()
    print(f"    {'key':20s}{'36A level':>12s}{'against truth':>15s}")
    print(f"    {'(the truth)':20s}{s['actual_levels'][0]:12.1f}{'—':>15s}")
    for r in sorted(s["runs"], key=lambda r: r["level_gap"][0]):
        print(f"    {r['key_id']:20s}{r['levels'][0]:12.1f}"
              f"{r['level_gap'][0]*100:14.1f}%")
    print()
    print("    Eight proxies, a fivefold spread, and no way to tell from")
    print("    inside which one is right. That is the whole argument.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
