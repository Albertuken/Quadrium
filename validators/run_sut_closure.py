"""
What "off by 0.8000" was hiding — three findings from one refused pair.

Following the adviser's own advice pointed the engine at Belgium's 2022
supply-use pair, and `load_sut` refused it with a maximum and nothing else:

    failed (as rebuilt): intermediate consumption plus value added equals output
    off by 0.8000 (tolerance 0.46, 0.005 x 92 summed cells at two decimals)

The refusal is correct and stays. Everything else about that message was
wrong or missing.

1. THE RESIDUE IS TWO CELLS, EQUAL AND OPPOSITE
    L68A  imputed rents of owner-occupied dwellings   +0.800
    L68B  other real estate services                  -0.800
    the other 87                                       0.000
Sum exactly +0.000. Not a table that fails to add up: a BOUNDARY between two
halves of one sector. `L68A` is the same sector that produces all 19 negative
cells in the UK analytical table's Leontief inverse, and the subject of
`OQ-D-02`. "off by 0.8000" and "+0.8 on L68A, -0.8 on L68B, cancelling" are
the same number and completely different findings.

2. THE BOUND WAS ASSUMED, NOT DERIVED -- THE FIFTH INSTANCE
`0.005 * n_terms` hard-codes two decimals for every publisher, while
`load_iot`, `io_loader._assert_balances` and `validation.validate_original` all
derive it (`OQ-B-02`). It errs TIGHT, which is the direction that refuses valid
tables:

    NL, integers      derived 34.500   applied 0.345   100x too tight
    ES, 1 decimal     derived  3.450   applied 0.345    10x too tight
    AT BE FR, 2 dp    derived  0.465   applied 0.465   right by accident

3. AUSTRIA'S RESIDUES DO NOT CANCEL, AND NOTHING SAID SO
Austria passes every per-industry test with residues summing to +1.86 in one
direction. A systematic lean was invisible, because the check only ever looked
at the maximum. It is now reported on every load, failure or not.

AND ONE BUG THE FIX ITSELF EXPOSED
------------------------------------
`to_iot` drops products with no domestic output, because no domestic industry
makes them and every model divides by that output. Belgium has some: `B06`,
crude petroleum and natural gas, with ZERO domestic output and 20,342 of
imports, of which 20,238 goes to `C19`, refining. Belgium imports all its crude
and refines it. Masked away, C19's column lost 20,210.

A product nobody makes at home is still bought. Its imported use now stays in
the imported-use row -- and how it gets there depends on the model's axis,
because the two families apply `T` from opposite sides:

    A, B, E   Sm = Um @ T   ->  sum over products, THEN transform
    C, D      Sm = T @ Um   ->  T is market shares, whose columns sum to 1, so
                                the transformation preserves column totals and
                                the plain sum is already the answer

Applying `@ T` on the industry axis put 3,175 into Spain's column residues, a
table that closes to 0.0000 when it is right.

Run:
    python3 validators/run_sut_closure.py
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


def files(geo: str, year: int = 2022):
    return (DATA / f"naio_10_cp15_{geo}_{year}.json",
            DATA / f"naio_10_cp16_{geo}_{year}.json",
            DATA / f"naio_10_cp1610_{geo}_{year}.json")


def main() -> int:
    from quadrium.eurostat import EurostatError, load_sut
    from quadrium.transformation import TransformationError

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # 1 -- the refusal, and what it now says.
    sup, use, basic = files("BE")
    try:
        load_sut(sup, use)
        msg = ""
    except EurostatError as exc:
        msg = str(exc)
    check("Belgium is still refused by default", bool(msg),
          "an identity beyond the source's own precision stops the load, as "
          "it does everywhere else in this engine")
    check("and the message names the industries, not just the maximum",
          "L68A" in msg and "L68B" in msg and "+0.800" in msg,
          "; ".join(ln.strip() for ln in msg.splitlines()
                    if "L68" in ln))
    check("and says the residues cancel, which is the whole finding",
          "CANCEL" in msg and "+0.000" in msg,
          "a boundary between two halves of one sector, not a table that "
          "fails to add up")
    check("and names the way in, rather than leaving it to be discovered",
          "sut_unbalanced: cancelling" in msg,
          msg.splitlines()[-1].strip()[:80])

    # 2 -- the opt-in admits that case and records what it admitted.
    s = load_sut(sup, use, basic, unbalanced="cancelling")
    check("`cancelling` admits it and carries the residue on the pair",
          abs(s.admitted_residue - 0.8) < 1e-6
          and "ADMITTED" in (s.notes or ""),
          f"admitted_residue = {s.admitted_residue:.3f}, and the note names "
          f"L68A and L68B and their sum")

    t = s.to_iot("D")
    check("and the table it produces inherits it, so the gates account for it",
          abs(t.inherited_residue - 0.8) < 1e-6,
          f"{t.inherited_residue:.3f} carried into `IOTable.inherited_residue` "
          f"— a transformed table cannot be measured for this, because the "
          f"transformation has already redistributed the residue")

    # 3 -- the bound is derived, and the difference is a hundredfold.
    print()
    from quadrium.precision import assertable_tolerance, printed_decimals
    import json
    print(f"    {'geo':>4}{'decimals':>10}{'derived':>10}{'assumed':>10}")
    facts = {}
    for geo in ("ES", "AT", "BE"):
        vals = [v for v in json.loads(files(geo)[0].read_text())["value"].values()
                if isinstance(v, (int, float))]
        d = printed_decimals(vals)
        n = 69
        derived = assertable_tolerance(vals, n)
        facts[geo] = (d, derived, 0.005 * n)
        print(f"    {geo:>4}{str(d):>10}{derived:>10.3f}{0.005 * n:>10.3f}")
    check("a one-decimal publisher was being held to a two-decimal bound",
          facts["ES"][1] > facts["ES"][2] * 9,
          f"Spain's own precision allows {facts['ES'][1]:.3f} and the assumed "
          f"constant applied {facts['ES'][2]:.3f} — it passed on being "
          f"internally exact, not on the bound being right")

    # 4 -- the lean that nothing reported.
    at = load_sut(*files("AT"))
    check("a source whose residues lean rather than cancel says so on load",
          "CLOSURE" in (at.notes or "") and "lean" in (at.notes or ""),
          (at.notes or "").split("CLOSURE:")[-1].strip()[:96])

    # 5 -- the wholly imported product, and the axis it is carried on.
    print()
    dead = [c for c, q in zip(s.product_codes, s.q) if q <= 0]
    imp = {c: float(s.imports[i]) for i, c in enumerate(s.product_codes)
           if s.q[i] <= 0}
    check("Belgium has products with no domestic output and real imports",
          "B06" in dead and imp["B06"] > 20_000,
          f"{', '.join(dead)} — B06, crude petroleum and natural gas, is "
          f"{imp['B06']:,.0f} of imports and no domestic output at all")

    for model in ("B", "D"):
        try:
            it = s.to_iot(model)
        except (TransformationError, ValueError):
            continue
        col = float(np.abs(it.Z.sum(0) + it.VA.sum(0) - it.X).max())
        check(f"and model {model} still closes its column identity",
              col < 1.0,
              f"{col:.4f} on {it.n} sectors — 20,210 before the imported use "
              f"of a dropped product was carried, which is C19's entire crude "
              f"oil input")

    # 6 -- and the country that has none of these problems is untouched.
    es = load_sut(*files("ES"))
    worst = 0.0
    for model in "ABCD":
        it = es.to_iot(model)
        worst = max(worst, float(np.abs(it.Z.sum(0) + it.VA.sum(0)
                                        - it.X).max()))
    check("Spain, which has no wholly imported product, is exact on all four",
          worst < 1e-6,
          f"{worst:.3g} — the check that none of this loosened anything")

    print()
    print("    A maximum is not a diagnosis. Two cells at ±0.8 and eighty-nine")
    print("    at 0.03 give the same number and call for opposite decisions.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
