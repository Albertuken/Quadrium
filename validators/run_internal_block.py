"""
`OQ-S-04`: what a split sector's internal block really looks like, measured.

The engine fills the block where the new subsectors trade with each other from
CORE_031 eq. (14), the outer product of the weights, with the diagonal scaled by
`Scenario.internal_block_alpha`. That parameter defaulted to **0.5** on the
stated intuition that "a subsector plausibly buys from itself LESS than
proportionality implies", and `OQ-S-04` recorded it as a deliberate but unsourced
departure costing 22.6 % of the parent cell.

No source settles it. Published data does, and it does not need to be asked
nicely: a two-sector block already exists in every table, for every pair of
sectors the classification happens to keep apart. Aggregate a pair, and the
outer product of their output weights is exactly what Wolsky would have
predicted for the block. Compare that with the block that is actually printed.

Define, for a pair with output weights ρ and parent cell `P = Σ block`:

    d = Σ_a ρ_a²                    alpha = (Σ_a Z_aa) / (d · P)
    o = 1 − d                       beta  = (Σ_{a≠b} Z_ab) / (o · P)

`alpha` and `beta` are the diagonal and off-diagonal multipliers on eq. (14)
that reproduce the observed block, and `alpha·d + beta·o = 1` identically, so
they conserve the parent cell by construction.

WHAT THE DATA SAYS, AND IT SAYS THE SAME THING THREE TIMES
-----------------------------------------------------------
    Italy   `cp1750` industry × industry, 65      219 pairs   alpha ~1.53
    Spain   `cp1700` product  × product,  65      219 pairs   alpha ~1.55
    UK      analytical IOT,             104      965 pairs   alpha ~1.47

A real two-sector block sits at roughly **1.5× the outer product on its
diagonal** and **0.1× off it**, in 96 % of pairs, across two countries, two axes
and two classifications. **The 0.5 default had the sign wrong**, and it was
wrong by a factor of three.

THE PILOT'S OWN PAIR, WHICH IS THE POINT
-----------------------------------------
The UK table separates I55 accommodation from I56 food service — the pair the
Spanish pilot splits. Its printed block, in £ million:

                        to I55      to I56
        from I55         887.3       101.3
        from I56         223.7     1,322.4

against an outer product of 208.4 / 518.4 / 518.4 / 1,289.5. Accommodation buys
**4.3× more from itself** than eq. (14) predicts and **5× less** from food
service. At the old default of 0.5 the engine would have put 104.2 in that
diagonal cell — eight and a half times too little.

WHAT IS NOT CLAIMED
-------------------
That alpha should be 1.5. That is this project's measurement, not a source, and
substituting it for eq. (14) would be the same error the 0.5 was. **The default
is now 1.0, the sourced rule**, and the measurement is recorded so that raising
alpha is a decision an analyst makes knowingly.

Nor is the mechanism claimed. The obvious explanation — that siblings are
technologically distinct, so each buys from itself — is TESTED BELOW AND FAILS:
sorting pairs by the cosine similarity of their input-coefficient columns leaves
alpha flat at ~1.5 in every quintile. It does not fall towards 1 as technologies
converge, which is what Wolsky's identical-technology assumption would predict.
Diagonal dominance appears to be a property of how industries are DELINEATED —
an industry groups activities that trade with each other — rather than of how
similar their technologies are. That is a finding, not an explanation, and it
touches `OQ-C-02`.

AND THE PARAMETER NO LONGER LEAKS
----------------------------------
The old form scaled the diagonal and left the off-diagonal at 1.0, so every
alpha ≠ 1 broke eq. (15) and left a shortfall for a balancing step that knows
nothing about the block. The off-diagonal now takes
`beta = (1 − alpha·d)/(1 − d)`, so the block conserves the parent cell for every
alpha, reduces exactly to eq. (14) at alpha = 1, and is bounded by beta = 0 at
alpha = 1/d.

Run:
    python3 validators/run_internal_block.py
"""

from __future__ import annotations

import itertools
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


def _alpha_beta(Z, x, i, j):
    P = Z[i, i] + Z[i, j] + Z[j, i] + Z[j, j]
    if P <= 0 or x[i] <= 0 or x[j] <= 0:
        return None
    r = np.array([x[i], x[j]], float)
    r /= r.sum()
    d = float(r[0] ** 2 + r[1] ** 2)
    o = 1.0 - d
    if d <= 0 or o <= 0:
        return None
    return ((Z[i, i] + Z[j, j]) / (d * P), (Z[i, j] + Z[j, i]) / (o * P), P, r)


def _sibling_pairs(codes, Z, x):
    sec = [str(c)[0] if c else "?" for c in codes]
    return [(i, j) for i, j in itertools.combinations(range(len(codes)), 2)
            if sec[i] == sec[j]]


def _tables():
    out = []
    from quadrium.eurostat import load_iot
    for fname, label in (("naio_10_cp1750_IT_2022.json", "Italy ixi 65"),
                         ("naio_10_cp1700_ES_2022.json", "Spain pxp 65")):
        p = ROOT / "data" / "eurostat" / fname
        if p.exists():
            t = load_iot(p, variant="domestic")
            out.append((label, t.Z, t.X, t.sector_codes))
    p = ROOT / "UK_IOAT_2023_domestic_ixi.xlsx"
    if p.exists():
        import run_uk_iot as uk
        t = uk.load_iot(p)
        out.append(("UK pxp 104", t["Z"], t["x"],
                    [str(c).strip() for c in t["codes"]]))
    return out


def main() -> int:
    tables = _tables()
    if not tables:
        print("no fixture available")
        return 0

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)
    print(f"  {'table':<16}{'pairs':>7}{'alpha med':>11}{'p25':>8}{'p75':>8}"
          f"{'beta med':>10}{'alpha<1':>9}")

    medians = {}
    for label, Z, x, codes in tables:
        A, B = [], []
        for i, j in _sibling_pairs(codes, Z, x):
            r = _alpha_beta(Z, x, i, j)
            if r and np.isfinite(r[0]) and np.isfinite(r[1]):
                A.append(r[0])
                B.append(r[1])
        A, B = np.array(A), np.array(B)
        if A.size == 0:
            continue
        medians[label] = (float(np.median(A)), float(np.median(B)), A.size)
        print(f"  {label:<16}{A.size:>7}{np.median(A):>11.3f}"
              f"{np.percentile(A, 25):>8.3f}{np.percentile(A, 75):>8.3f}"
              f"{np.median(B):>10.3f}{(A < 1).mean():>9.1%}")

    check("every table agrees the diagonal is ABOVE the outer product",
          all(m[0] > 1.3 for m in medians.values()),
          "medians " + ", ".join(f"{l} {m[0]:.2f}" for l, m in medians.items())
          + " — the 0.5 default had the sign wrong, by a factor of three")
    check("and the off-diagonal is well below it",
          all(m[1] < 0.5 for m in medians.values()),
          "medians " + ", ".join(f"{l} {m[1]:.2f}" for l, m in medians.items()))
    total = sum(m[2] for m in medians.values())
    check("the result is not one country's or one axis's artefact",
          len(medians) >= 3 and total > 1000,
          f"{total:,} sibling pairs across {len(medians)} tables, two "
          f"countries, product×product and industry×industry")

    # ---- the pilot's own pair --------------------------------------------
    uk = next((t for t in tables if t[0].startswith("UK")), None)
    if uk:
        _, Z, x, codes = uk
        try:
            i, j = codes.index("I55"), codes.index("I56")
        except ValueError:
            i = j = None
        if i is not None:
            a, b, P, r = _alpha_beta(Z, x, i, j)
            outer = np.outer(r, r) * P
            print()
            print(f"    UK I55 accommodation × I56 food service, the pilot's "
                  f"own pair (£m)")
            print(f"      printed        [[{Z[i,i]:>9,.1f} {Z[i,j]:>9,.1f}]"
                  f" [{Z[j,i]:>9,.1f} {Z[j,j]:>9,.1f}]]")
            print(f"      eq. (14)       [[{outer[0,0]:>9,.1f} {outer[0,1]:>9,.1f}]"
                  f" [{outer[1,0]:>9,.1f} {outer[1,1]:>9,.1f}]]")
            check("the pilot's own pair behaves like every other one",
                  1.3 < a < 1.7,
                  f"alpha {a:.3f}, beta {b:.3f} — against a cross-table median "
                  f"of ~1.5, so this is not a peculiarity of the split the "
                  f"project happens to care about")
            old = 0.5 * r[0] * r[0] * P
            check("and the OLD default would have been eight times too small "
                  "in that cell",
                  Z[i, i] / old > 8,
                  f"{old:,.1f} against a printed {Z[i,i]:,.1f}")

    # ---- the mechanism that would have explained it, and does not ---------
    it = next((t for t in tables if t[0].startswith("Italy")), None)
    if it:
        _, Z, x, codes = it
        A = Z / np.where(x > 0, x, 1.0)
        rows = []
        for i, j in itertools.combinations(range(len(codes)), 2):
            r = _alpha_beta(Z, x, i, j)
            if not r:
                continue
            u, w = A[:, i].copy(), A[:, j].copy()
            u[[i, j]] = w[[i, j]] = 0.0
            nu, nw = np.linalg.norm(u), np.linalg.norm(w)
            if nu == 0 or nw == 0:
                continue
            rows.append((float(u @ w / (nu * nw)), r[0]))
        arr = np.array(rows)
        arr = arr[np.argsort(arr[:, 0])]
        quints = np.array_split(arr, 5)
        print()
        print("    Does alpha fall to 1 as technologies converge, as Wolsky's")
        print("    identical-technology assumption implies? Italy, by quintile")
        print("    of cosine similarity between input-coefficient columns:")
        meds = []
        for k, g in enumerate(quints):
            m = float(np.median(g[:, 1]))
            meds.append(m)
            print(f"      Q{k+1}  cosine {g[:, 0].mean():.3f}   "
                  f"alpha median {m:.3f}   (n={len(g)})")
        check("it does not — the obvious explanation is refuted",
              abs(meds[-1] - meds[0]) < 0.15 and min(meds) > 1.3,
              f"flat at ~{np.mean(meds):.2f} from cosine "
              f"{quints[0][:, 0].mean():.2f} to {quints[-1][:, 0].mean():.2f}. "
              f"Diagonal dominance is a property of how industries are "
              f"DELINEATED, not of how alike they are — see OQ-C-02")

    # ---- and the engine now conserves the parent cell ---------------------
    print()
    for alpha in (0.5, 1.0, 1.5):
        w = np.array([0.287, 0.713])
        d = float((w * w).sum())
        beta = (1.0 - alpha * d) / (1.0 - d)
        blk = np.outer(w, w) * 12.0
        blk = blk * beta + np.diag(np.diag(blk)) * (alpha - beta)
        check(f"the block conserves the parent cell at alpha = {alpha}",
              abs(blk.sum() - 12.0) < 1e-12,
              f"beta = {beta:.3f}, block sum {blk.sum():.12f}"
              + (" — and this IS eq. (14)" if alpha == 1.0 else ""))

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
