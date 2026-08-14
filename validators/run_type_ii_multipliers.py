"""
`OQ-T-05` closed: the Handbook has a whole chapter on multipliers, and it was
never extracted.

At v1.26 this project recovered the Type I formulas from the ONS's published
sheets and reproduced 1,434 figures to 7.11e-15 — an official *implementation*,
with the entry recording that no loaded methodological source defined them and
that the induced effect had no procedure anywhere.

**Chapter 20, "Modelling applications of IOTs", is 38 pages on exactly this.** It
was never among the extracted chapters and nothing pointed at it, because the
entry was looking for the topic under "multipliers" in the balancing and
transformation chapters where it does not live. Extracted now, publication pages
603–640, 37/37 pages agreeing.

WHAT IT SETTLES
-----------------
**The Type I formulas are now normative, not just observed practice.**

    ¶20.90, eq. (45)   O_j = Σ_i α_ij           the output multiplier is the
                                                column sum of the Leontief
                                                inverse — word for word what the
                                                ONS sheets do, verified here at
                                                2.7e-15
    ¶20.94, eq. (46)   Z = B(I − A)^-1          B the vector of input
                                                coefficients for wages. That is
                                                `M-067`'s general effect formula
                                                `e = (v ⊘ x)ᵀ L`, with the source
                                                naming wages as the case in point

So `M-067` moves from "this is what one office does" to "this is what the
Handbook specifies and one office does". Its authority rank improves and its
content does not change.

**And the type II closure is specified.** ¶20.88: "In the type I multiplier
analysis, household final consumption expenditure and, consequently, private
household activities are exogenous. A more refined type II multiplier analysis
for wages and private consumption is designed to include the household sector as
an endogenous activity. It is assumed that, to a large extent, the income earned
by private households **from wages and salaries** is spent as household final
consumption expenditure. This additional income induces higher incomes, which
again induce more household final consumption expenditure until a new equilibrium
is reached."

That names the income concept — **wages and salaries** — the spending, and the
mechanism. Box 20.4 prints both `A` matrices side by side for Germany 2009.

THE GERMAN EXAMPLE CANNOT VALIDATE ITSELF, AND THAT IS `OQ-T-06` AGAIN
-----------------------------------------------------------------------
Box 20.4 prints the IOT in **whole billions of euros** and Table 20.11 prints the
Leontief inverse to four decimals. Rebuilding `A` from the printed table and
inverting reproduces Table 20.11 to **0.0148**, and the output multipliers to
**0.0080** on values near 1.87.

That is not a defect in either number — it is the arithmetic of an integer-rounded
input. Agriculture's first cell is 3, so its true value lies anywhere in [2.5,
3.5), a ±17 % band, and 3/42 = 0.0714 against the box's printed 0.0692. **A table
printed to whole units cannot reproduce its own derived matrices to four
decimals**, which is `OQ-T-06`'s finding arriving in a third chapter.

So the example is used here as a **bound**, not as a fixture: agreement to 0.4 %
is what integer inputs support, and that is what is checked.

TYPE II ON REAL DATA, AND ONE THING THE SOURCE DOES NOT SETTLE
----------------------------------------------------------------
Implementing ¶20.88 on the UK fixture — augment `A` with a wage-coefficient row
and a household-consumption column, then invert:

    type I    mean 1.7173   median 1.6762
    type II   mean 2.6681   median 2.6950
    ratio     mean 1.573    range 1.017 – 3.102

**This corrects a claim of mine.** `M-067` and `OQ-T-05` said induced effects
"typically add a third again to a type I multiplier". That was an unsourced
generalisation written from memory. On this table it is **57 %**, not 33 %, and
the per-industry range runs from 2 % to 210 %.

**And the source specifies the concept but not the normalisation.** ¶20.88 says
wage income is spent as household consumption; it does not say what to divide the
consumption column by when household consumption is not funded by wages alone.
Here UK household consumption is 89 % of wage income, so the choice is live:

    closed on wages and salaries alone   ratio 1.573   range 1.02 – 3.10
    closed on wages + surplus and mixed  ratio 1.614   range 1.20 – 2.31
    closed on all of value added         ratio 1.612   range 1.21 – 2.30

**The economy-wide uplift is robust — about 1.6× however it is closed — and the
industry ranking is not.** The spread nearly halves between the first row and the
others. So a report giving an aggregate induced effect stands on firm ground; one
ranking industries by their type II multiplier is resting on a choice the
Handbook does not make. `NOT SPECIFIED`, and it is the residue of this question.

Run:
    python3 validators/run_type_ii_multipliers.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

EXTRACTED = ROOT / "library" / "extracted"
FIXTURE = ROOT / "UK_IOAT_2023_domestic_ixi.xlsx"
FAIL: list[str] = []

# Box 20.4, Germany 2009, billion euros: the intermediate block and industry
# output. Printed to whole units, which is the point of the bound below.
DE_Z = np.array([
    [3,  20,  0,   0,   0,   1],
    [7, 394, 48,  56,  11,  30],
    [1,  11, 18,   8,  28,  10],
    [4, 139, 17, 181,  38,  40],
    [6, 131, 30, 124, 261,  51],
    [0,  18,  3,  12,  17,  47]], float)
DE_X = np.array([42, 1451, 234, 907, 1010, 721], float)
# Table 20.11 row (7), as printed
DE_MULT = np.array([1.8679, 1.8704, 1.8695, 1.7074, 1.5648, 1.4029])


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # ---- the source says it ----------------------------------------------
    ch20 = EXTRACTED / "UNH_20_UN2018_CH20_Modelling_Applications_of_IOTs.txt"
    if not ch20.exists():
        print("UNH_20 absent")
        return 0
    flat = re.sub(r"\s+", " ", ch20.read_text())

    check("¶20.90 makes the output multiplier the column sum of the Leontief "
          "inverse",
          "corresponds to the column sum of the Leontief inverse" in flat,
          "word for word what M-067 recovered from the ONS sheets and verified "
          "at 2.7e-15. The formula is now normative as well as observed")
    check("and ¶20.94 gives the general effect formula M-067 states",
          "vector of input coefficients for wages" in flat,
          "Z = B(I − A)^-1 — M-067's e = (v ⊘ x)ᵀ L, with wages as the case in "
          "point. The card's authority improves; its content does not change")
    check("and ¶20.88 specifies the type II closure, which nothing loaded did",
          "include the household sector as an endogenous activity" in flat
          and "from wages and salaries is spent as household final consumption "
              "expenditure" in flat,
          "the income concept (wages and salaries), the spending (household "
          "final consumption) and the mechanism (iterate to a new "
          "equilibrium). OQ-T-05's remaining half")

    # ---- the German example, as a bound ----------------------------------
    A_de = DE_Z / DE_X
    L_de = np.linalg.inv(np.eye(6) - A_de)
    err = float(np.abs(L_de.sum(0) - DE_MULT).max())
    print()
    print(f"    Box 20.4 rebuilt: multipliers {np.round(L_de.sum(0), 4)}")
    print(f"    Table 20.11 as printed:       {DE_MULT}")
    check("the printed example agrees only to the precision its own rounding "
          "supports",
          0.001 < err < 0.05,
          f"max error {err:.4f} on values near 1.87 — 0.4 %. The IOT is printed "
          f"in whole billions, so agriculture's cell of 3 carries a ±17 % band "
          f"and 3/42 = 0.0714 against the box's own printed 0.0692. Used as a "
          f"bound, not as a fixture — OQ-T-06 in a third chapter")

    # ---- type II on the UK fixture ---------------------------------------
    if not FIXTURE.exists():
        print("\nfixture absent; source checks only")
        return 1 if FAIL else 0

    from quadrium.io_loader import load_uk_analytical_iot

    t = load_uk_analytical_iot(FIXTURE)
    X = np.asarray(t.X, float)
    Z = np.asarray(t.Z, float)
    VA = np.asarray(t.VA, float)
    n = len(X)
    safe = np.where(X > 0, X, 1.0)
    A = Z / safe
    hh = np.asarray(t.Y, float)[:, list(t.Y_labels).index("P3 S14")]
    live = X > 0
    m1 = np.linalg.inv(np.eye(n) - A).sum(0)

    def type_ii(rows: list[int]) -> np.ndarray:
        income = sum(VA[i] for i in rows)
        star = np.zeros((n + 1, n + 1))
        star[:n, :n] = A
        star[n, :n] = income / safe                 # wage row
        star[:n, n] = hh / income.sum()             # consumption column
        return np.linalg.inv(np.eye(n + 1) - star)[:n, :n].sum(0)

    m2 = type_ii([2])
    ratio = (m2 / m1)[live]
    print()
    print(f"    UK 2023, {int(live.sum())} industries")
    print(f"      type I    mean {m1[live].mean():.4f}   "
          f"median {np.median(m1[live]):.4f}")
    print(f"      type II   mean {m2[live].mean():.4f}   "
          f"median {np.median(m2[live]):.4f}")

    check("the type II closure runs and every multiplier grows",
          bool((m2[live] >= m1[live] - 1e-9).all()),
          f"as it must — endogenising households adds a channel, it removes "
          f"none. Mean ratio {ratio.mean():.3f}")

    check("and it is 57 % on this table, not the 'third again' I wrote from "
          "memory",
          1.45 < ratio.mean() < 1.75,
          f"mean {ratio.mean():.3f}, range {ratio.min():.3f}–{ratio.max():.3f}. "
          f"M-067 and OQ-T-05 said induced effects 'typically add a third "
          f"again'; that was an unsourced generalisation and it understated "
          f"this table by two thirds")

    # ---- the normalisation the source does not fix ------------------------
    print()
    variants = {
        "wages and salaries alone (¶20.88)": [2],
        "wages + surplus and mixed income": [2, 3],
        "all of value added": [2, 3, 4],
    }
    stats = {}
    for label, rows in variants.items():
        r = (type_ii(rows) / m1)[live]
        stats[label] = (r.mean(), r.min(), r.max())
        print(f"    {label:<36} ratio {r.mean():.3f}   "
              f"range {r.min():.2f}–{r.max():.2f}")

    means = [v[0] for v in stats.values()]
    spreads = [v[2] - v[1] for v in stats.values()]
    check("the aggregate uplift is robust to the income concept",
          max(means) - min(means) < 0.06,
          f"{min(means):.3f} to {max(means):.3f} across three closures — a "
          f"report giving an economy-wide induced effect stands on firm ground")
    check("but the industry ranking is NOT, and the source does not choose",
          max(spreads) > 1.4 * min(spreads),
          f"the spread runs {min(spreads):.2f} to {max(spreads):.2f} — it "
          f"nearly halves between closing on wages alone and closing on wages "
          f"plus surplus. ¶20.88 names the income concept but not what to "
          f"divide the consumption column by when household consumption is not "
          f"funded by wages alone; here UK consumption is 89 % of wage income, "
          f"so the choice bites. NOT SPECIFIED, and it is this question's "
          f"residue")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
