"""
"How wrong is this if my key is wrong?" — answered exactly, not simulated.

THE QUESTION EVERY USER ASKS SECOND
-------------------------------------
The first is "can I split this sector". The second, on seeing the answer, is
"and how much of that depends on the proxy I made up". The report said the
spread between scenarios was "the crude measure of MVP_0.1 §10 — the widest
cell, not a sensitivity analysis", and stopped there.

The obvious next move was a perturbation study: jitter the key, re-run, measure
the spread. It would have been wasted work, and measuring first is what showed
why.

WHAT THE KEY ACTUALLY MOVES
-----------------------------
Splitting `I56` on the UK table and moving the key from 50/50 to 80/20:

    key I561     mult I561    mult I562       X I561       X I562
          50       1.84800      1.84800       47,405       47,405
          60       1.84800      1.84800       56,886       37,924
          70       1.84800      1.84800       66,367       28,443
          80       1.84800      1.84800       75,848       18,962

**The multiplier does not move. At all.** Not approximately, not within a
tolerance — 1.84800 at every weight, to as many decimals as anyone cares to
print. The levels move one for one: 60/40 puts 60 % of the parent's output in
the first subsector, and 80/20 puts 80 %.

That is algebra, not a coincidence of this fixture. The weight scales `Z_ij`
and `X_j` together and cancels in `a_ij = Z_ij / X_j`, so the coefficient
columns are identical whatever the key says, and so are the multipliers.

SO THE ERROR BAR IS ARITHMETIC
-------------------------------
One per cent of error in the key is one per cent of error in the subsector's
size and ZERO in its multiplier. No simulation can improve on that, and a
perturbation study would have reported a spread of zero and been mistaken for a
finding about robustness. The report now states it per subsector, in the
table's own units, so it can be read rather than derived.

AND WHAT DOES MOVE A MULTIPLIER
---------------------------------
The `profiles` sheet, and barely. On the same fixture:

    intensity on one supplier    mult I561    mult I562
    none                           1.84800      1.84800
    1.0  (the average)             1.84800      1.84800
    1.1                            1.84899      1.84652
    2.0                            1.85455      1.83816

Doubling one supplier's intensity moves the multiplier by 0.35 %. An intensity
of exactly 1.0 reproduces the unprofiled run to the last digit, which is what
"1.0 means the average" has to mean if it means anything.

Run:
    python3 validators/run_key_sensitivity.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def split_run(weight: float, intensity=None):
    """Split `I56` two ways at `weight`/(100-weight); return multipliers and X."""
    from quadrium.config import build_config
    from quadrium.project import IOProject

    profiles = ([] if intensity is None else
                [{"scenario_id": "S1", "subsector_code": "I561",
                  "supplier_code": "C101", "intensity": intensity}])
    cfg = build_config(
        {"project_id": "s", "table_kind": "uk_analytical",
         "table_path": "UK_IOAT_2023_domestic_ixi.xlsx", "title": "t"},
        {"splits": [{"sector_code": "I56", "new_code": c, "new_label": c,
                     "key_id": "k"} for c in ("I561", "I562")],
         "keys": [{"key_id": "k", "new_sector_code": c, "value": v,
                   "source": "synthetic", "source_year": 2023,
                   "strength": "weak"}
                  for c, v in (("I561", weight), ("I562", 100 - weight))],
         "scenarios": [{"scenario_id": "S1", "label": "S1"}],
         "profiles": profiles},
        base_dir=ROOT)
    with tempfile.TemporaryDirectory() as tmp:
        p = IOProject(project_id="s", table=cfg["table"], splits=cfg["splits"],
                      scenarios=cfg["scenarios"], keys=cfg["keys"],
                      ledger=cfg["ledger"], title="t", source_file="—",
                      root=Path(tmp))
        p.run()
        t = p.results[0].table
        A = np.where(t.X != 0, t.Z / t.X[None, :], 0.0)
        L = np.linalg.inv(np.eye(t.n) - A)
        i = [t.sector_codes.index(c) for c in ("I561", "I562")]
        return L[:, i].sum(axis=0), t.X[i], t.VA[:, i].sum(axis=0)


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    weights = (50, 60, 70, 80)
    runs = {w: split_run(w) for w in weights}

    print(f"    {'key I561':>10}{'mult I561':>12}{'mult I562':>12}"
          f"{'X I561':>13}{'X I562':>13}")
    for w in weights:
        m, x, _ = runs[w]
        print(f"    {w:>10}{m[0]:>12.5f}{m[1]:>12.5f}{x[0]:>13,.0f}"
              f"{x[1]:>13,.0f}")

    mults = np.array([runs[w][0] for w in weights])
    spread = float(np.abs(mults - mults[0]).max())
    check("the multiplier is invariant to the allocation key, exactly",
          spread < 1e-9,
          f"across weights {weights[0]}/{100 - weights[0]} to "
          f"{weights[-1]}/{100 - weights[-1]} the multipliers move "
          f"{spread:.3g} — not within a tolerance, but because the weight "
          f"cancels in a_ij = Z_ij / X_j")

    # 2 -- and the levels move one for one.
    total = float(sum(runs[50][1]))
    ratios = [float(runs[w][1][0]) / total * 100 for w in weights]
    check("and the levels move one for one with it",
          all(abs(r - w) < 1e-6 for r, w in zip(ratios, weights)),
          "a key of " + ", ".join(f"{w}%" for w in weights)
          + " puts " + ", ".join(f"{r:.4f}%" for r in ratios)
          + " of the parent's output in the first subsector — the same number, "
            "not a number near it")

    va = [float(runs[w][2][0]) / float(sum(runs[50][2])) * 100
          for w in weights]
    check("value added too, by the same weights",
          all(abs(v - w) < 1e-6 for v, w in zip(va, weights)),
          ", ".join(f"{v:.4f}%" for v in va))

    # 3 -- so the error bar is arithmetic, and the report can state it.
    x0 = float(runs[60][1][0])
    check("so one per cent of key error is one per cent of size error",
          abs((float(split_run(60.6)[1][0]) - x0) / x0 - 0.01) < 1e-6,
          f"moving the key from 60 % to 60.6 % — one per cent of 60 — moves "
          f"that subsector's output by exactly 1 %, or {x0 / 100:,.0f} of the "
          f"table's units. A perturbation study would have reported a "
          f"multiplier spread of zero and been read as evidence of robustness")

    # 4 -- what does move a multiplier, and how little.
    print()
    print(f"    {'intensity':>12}{'mult I561':>12}{'mult I562':>12}")
    base = runs[60][0]
    print(f"    {'none':>12}{base[0]:>12.5f}{base[1]:>12.5f}")
    seen = {}
    for x in (1.0, 1.1, 2.0):
        m, _, _ = split_run(60, intensity=x)
        seen[x] = m
        print(f"    {x:>12.1f}{m[0]:>12.5f}{m[1]:>12.5f}")

    check("an intensity of 1.0 reproduces the unprofiled run exactly",
          float(np.abs(seen[1.0] - base).max()) < 1e-12,
          "'1.0 means the parent's average' is either exact or it is a "
          "slogan; it is exact")
    move = float(seen[2.0][0] / base[0] - 1)
    check("and doubling one supplier's intensity moves it by a third of a "
          "per cent", 0.001 < move < 0.01,
          f"{move:+.2%}. Multipliers are dominated by the parent's overall "
          f"input intensity; redistributing the mix within a similar total "
          f"moves them at the margin. That is the lever, and it is short")

    print()
    print("    The obvious move was a perturbation study. Measuring first is")
    print("    what showed it would have reported a spread of zero, and been")
    print("    mistaken for evidence of robustness.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
