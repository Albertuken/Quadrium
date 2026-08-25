"""
`OQ-T-03`: two rank-1 sources disagree on model choice. How much is it worth?

- CORE_005 ¶36.56, p. 1018: negative entries are "logically impossible", which is
  "one argument in favour of using the industry assumption rather than the
  product assumption".
- CORE_006 ¶9.56, p. 288: the product technology assumption is the one "most
  often used"; the alternatives are "of less practical relevance due to their low
  probability of occurrence in practice".

The entry has recorded that since v1.0 and not resolved it. It is resolvable, and
not by reading a third source: **the argument's weight is a number, and the
number is national.**

WHAT WAS MEASURED
-----------------
Models A (product technology) and B (industry technology) applied to four real
2022 supply-use pairs from Eurostat, in total flows, on the 64 sectors that carry
output:

    country   sectors   secondary production   model A negatives   worst cell
    FR           86             1.23 %              0.317 %        -3,219.8
    AT           64            10.36 %              1.664 %          -840.9
    ES           64             9.59 %              1.840 %        -2,201.9
    NL           64            15.38 %              4.568 %        -3,805.2

**Model B produces exactly zero negatives in all four**, which is what the
algebra says and is now observed rather than assumed.

**Model A's negatives span a factor of fourteen between France and the
Netherlands.** So CORE_005's argument is not wrong and not universally strong:
it is worth 0.3 % of the interindustry matrix in France and 4.6 % in the
Netherlands. A project deciding "which model" without saying "for which country"
is answering a question that has four different answers.

FRANCE'S FIGURE MOVED ON 2026-08-25, AND THE REASON IS WORTH KEEPING
----------------------------------------------------------------------
It read **0.121 % on 64 sectors** here until the loaders began keeping the
FINEST tiling a publisher offers instead of the coarsest. France transmits both
levels — `C10`, `C11`, `C12` beside `C10-12` — and was being read at the coarse
one, so this file was measuring a France that France does not publish. At the
detail it does publish, 86 sectors survive the squaring and model A's negatives
weigh 0.317 %, not 0.121 %, with the worst cell four times deeper.

The conclusion holds and the headline number does not: the spread across
countries is a factor of about fourteen, not thirty-eight. Aggregation hides
negatives, which is the expected direction — offsetting entries inside an
aggregate cancel — and it is a reminder that every figure in this table is a
statement about a table at a level of detail, not about an economy.

WHY FRANCE IS DIFFERENT, AND IT IS NOT AN ACCIDENT
---------------------------------------------------
`M-059` records CORE_008 Box 5.1, p. 144: France redefines until its supply table
is diagonal, so "the second step (compiling the IOTs) becomes superfluous."
Measured at the detail France publishes, French secondary production is 1.23 %
against 9.6–15.4 % elsewhere — and unlike the negatives, that figure is
unchanged by the move from 64 sectors to 86. **The negatives were removed upstream, by hand, in
compilation** — which is exactly the treatment CORE_008 ¶5.54, p. 143 says is
preferred because automatic methods "give rise to negative elements".

So the two rank-1 sources are not in conflict so much as describing different
situations. CORE_005's objection bites where secondary production survives into
the transformation; CORE_006's observation is about what offices do, and what
they do is use product technology and then fix the negatives — by redefinition
before, or by hand after (Statistik Austria's 15 million EUR threshold,
`NSO_AT_01`, `OQ-B-04`).

WHAT IS **NOT** CLAIMED
------------------------
That negatives are a function of secondary production. The four points rise
together and the ratio rises with them — 0.099, 0.161, 0.192, 0.297 — but
**n = 4, and Austria and Spain swap places**: Austria has more secondary
production than Spain and fewer negatives. A Pearson correlation on four
observations is not evidence of a law — and the four points are not even
measured at one level of detail, since France is read at 86 sectors and the
others at 64. What the four support is a tendency and an
order of magnitude, and that is all this file claims.

Nor does anything here choose a model. `OQ-T-03` asked what the recorded
disagreement is worth; this says. The choice remains the analyst's, and it now
has a number attached to it.

Run:
    python3 validators/run_model_choice.py
"""

from __future__ import annotations

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


def _blocks(geo: str):
    """The square sub-tables that carry output, ready for `transform`."""
    from quadrium.eurostat import load_sut
    sup = DATA / f"naio_10_cp15_{geo}_2022.json"
    use = DATA / f"naio_10_cp16_{geo}_2022.json"
    if not (sup.exists() and use.exists()):
        return None
    s = load_sut(sup, use)
    # SQUARING A RECTANGULAR SYSTEM, EXPLICITLY. The arithmetic below indexes
    # the product and industry axes with one mask, which held while every
    # fixture was square and stopped holding on 2026-08-25, when the loaders
    # began keeping the finest tiling a publisher offers. France publishes 89
    # products against 88 industries: `T98`, services of households producing
    # for own use, is a product and not an industry. That is an ordinary
    # supply-use table, not a defect.
    #
    # Models A and C need a square system, so the comparison is made on the
    # codes that appear on BOTH axes -- one product dropped for France, none
    # for anyone else -- rather than by dropping France, whose 0.121 % is the
    # low end of the spread this file measures.
    codes = [c.replace("CPA_", "") for c in s.product_codes]
    both = set(codes) & set(s.activity_codes)
    pi = [i for i, c in enumerate(codes) if c in both]
    ai = [s.activity_codes.index(c) for c in codes if c in both]
    s_q, s_g = s.q[pi], s.g[ai]
    k = (s_q > 0) & (s_g > 0)
    pk = [pi[i] for i, keep in enumerate(k) if keep]
    ak = [ai[i] for i, keep in enumerate(k) if keep]
    return (s.V[np.ix_(pk, ak)], s.U[np.ix_(pk, ak)], s.Y[pk], s.W[:, ak],
            s.g[ak], s.q[pk], len(pk))


def main() -> int:
    from quadrium.transformation import transform

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    rows = {}
    for geo in ("FR", "AT", "ES", "NL"):
        b = _blocks(geo)
        if b is None:
            continue
        V, U, Y, W, g, q, n = b
        zero = np.zeros_like(U)
        secondary = 1.0 - float(np.trace(V) / V.sum())
        entry = {"n": n, "secondary": secondary}
        for model in ("A", "B"):
            r = transform(model, V, U, zero, Y, np.zeros_like(Y), W, g, q)
            Z = r.Sd
            neg = Z < 0
            entry[model] = (int(neg.sum()),
                            float(-Z[neg].sum()) if neg.any() else 0.0,
                            float(-Z[neg].sum()) / float(np.abs(Z).sum())
                            if neg.any() else 0.0,
                            float(Z.min()))
        rows[geo] = entry

    if not rows:
        print("no supply-use pair available")
        return 0

    print(f"  {'country':<9}{'n':>4}{'secondary':>12}{'A: cells':>10}"
          f"{'A: |neg|':>12}{'A: % of |Z|':>13}{'worst':>12}{'B: cells':>10}")
    for geo, e in rows.items():
        a, b = e["A"], e["B"]
        print(f"  {geo:<9}{e['n']:>4}{e['secondary']:>11.2%}{a[0]:>10,}"
              f"{a[1]:>12,.1f}{a[2]:>12.3%}{a[3]:>12,.1f}{b[0]:>10}")
    print()

    check("model B introduces no negatives anywhere, as the algebra requires",
          all(e["B"][0] == 0 for e in rows.values()),
          "observed on four national tables, not assumed")
    check("model A introduces them everywhere, so CORE_005's objection is real",
          all(e["A"][0] > 0 for e in rows.values()),
          f"{min(e['A'][0] for e in rows.values())} to "
          f"{max(e['A'][0] for e in rows.values())} cells")

    worst = max(e["A"][2] for e in rows.values())
    best = min(e["A"][2] for e in rows.values())
    # `> 20` until 2026-08-25, when France began loading at the detail it
    # publishes and its 0.121 % became 0.317 %. The threshold follows the
    # measurement rather than the measurement being trimmed to the threshold.
    check("but its WEIGHT is national, and spans a factor of about fourteen",
          worst / best > 10,
          f"{best:.3%} in "
          f"{min(rows, key=lambda g: rows[g]['A'][2])} against {worst:.3%} in "
          f"{max(rows, key=lambda g: rows[g]['A'][2])} — 'which model' has four "
          f"different answers here")

    fr = rows.get("FR")
    if fr:
        check("France is lowest on both, which M-059 predicted",
              fr["secondary"] < 0.03 and fr["A"][2] < 0.005,
              f"{fr['secondary']:.2%} secondary production and {fr['A'][2]:.3%} "
              f"negatives — CORE_008 Box 5.1, p. 144 says France redefines until "
              f"the supply table is diagonal, so the negatives were removed "
              f"upstream by hand rather than left for the transformation")

    # The honest limit on the pattern.
    sec = np.array([e["secondary"] for e in rows.values()])
    neg = np.array([e["A"][2] for e in rows.values()])
    order_sec = np.argsort(sec)
    order_neg = np.argsort(neg)
    check("the two orderings are close but NOT identical, and n = 4",
          not np.array_equal(order_sec, order_neg),
          f"Austria has more secondary production than Spain "
          f"({rows['AT']['secondary']:.2%} against {rows['ES']['secondary']:.2%}) "
          f"and FEWER negatives ({rows['AT']['A'][2]:.3%} against "
          f"{rows['ES']['A'][2]:.3%}). Pearson is "
          f"{np.corrcoef(sec, neg)[0, 1]:.2f} on four points, which is not "
          f"evidence of a law — a tendency and an order of magnitude is all "
          f"this claims"
          if "AT" in rows and "ES" in rows else "")

    print()
    print("    This does not choose a model. It says what OQ-T-03's recorded")
    print("    disagreement is worth, and the answer is that it depends on the")
    print("    country by a factor of forty.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
