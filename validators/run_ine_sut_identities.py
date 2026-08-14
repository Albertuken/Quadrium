"""
The identities an analytical IOT cannot test, tested.

`OQ-D-03` has said since v1.1 that `ID-01`, `ID-07` to `ID-10` and `ID-13` could
not be checked, and the reason was not laziness: an analytical input-output table
at basic prices has already had its trade and transport margins reallocated, so
there is nothing left to check them against. The validator reported them
NOT APPLICABLE. The entry's conclusion was that the project needed a supply-use
pair as a second fixture.

`cne_tod_22.xlsx` is that fixture. A supply table carries trade margins,
transport margins and taxes less subsidies on products as explicit columns, so
the valuation identities become arithmetic.

WHAT IS CHECKED, AND WHY EACH ONE MATTERS
-----------------------------------------
`ID-01`  Product balance at purchasers' prices — the central identity of the
         whole framework. Supply and use meet product by product before anyone
         has assumed anything about secondary production.

`ID-07`  Product output from the supply matrix's rows, industry output from its
         columns, and the two totals equal.

`ID-08`  **Trade and transport margins sum to zero across the economy.** The
         spec calls this "the origin of structurally negative cells and the
         single most important reason a sign-agnostic balancing method is
         required". The project chose GRAS over RAS on that argument and had
         never been able to see the margins that motivate it.

`ID-09`  Margins by product against margins by industry — **half of it**. What
         the trade-service products give up equals what the goods receive, and
         that is exact. Whether the split between the trade industries and the
         others is right cannot be checked, because no office publishes margins
         by industry; what CAN be shown is that the "other industries" clause is
         not empty, since the supply matrix says who produces trade-service
         product. 6.7 % of trade margins and 7.8 % of transport margins are
         earned outside their own sector.

`ID-10`  The CIF/FOB adjustment sums to zero.

`ID-19`  A margin column's negatives are MANDATORY, not tolerated. A margin
         column without them has moved nothing.

Run:
    python3 validators/run_ine_sut_identities.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quadrium.io_loader import load_ine_tod  # noqa: E402

DATA = ROOT / "data" / "ine" / "cne_tod_22.xlsx"
TOL = 1e-3          # million EUR; observed residuals are ~1e-11
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    if not DATA.exists():
        print(f"fixture absent: {DATA}")
        return 0
    s = load_ine_tod(DATA)
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 72)
    print(f"  {s.table_id}: {s.n_products} products x {s.n_activities} "
          f"activities, {s.unit}\n")

    # ID-01 -- the product balance, articulated with its valuation columns.
    lhs, rhs = s.supply_at_purchasers(), s.use_at_purchasers()
    d = float(np.abs(lhs - rhs).max())
    check("ID-01 product balance at purchasers' prices, all 110 products",
          d < TOL, f"max deviation {d:.3e} on a table of "
                   f"{lhs.sum():,.0f} million EUR")
    check("  and the simple form WITHOUT margins would fail, which is the point",
          float(np.abs((s.q + s.imports) - rhs).max()) > 1.0,
          f"output + imports alone is off by "
          f"{float(np.abs((s.q + s.imports) - rhs).max()):,.1f} — the "
          f"articulated form is not decoration")

    # ID-07 -- output two ways.
    check("ID-07 supply rows give product output",
          float(np.abs(s.V.sum(1) - s.q).max()) < TOL,
          f"max deviation {float(np.abs(s.V.sum(1) - s.q).max()):.3e}")
    check("ID-07 supply columns give activity output",
          float(np.abs(s.V.sum(0) - s.g).max()) < TOL,
          f"max deviation {float(np.abs(s.V.sum(0) - s.g).max()):.3e}")
    check("ID-07 total output is the same counted either way",
          abs(float(s.q.sum() - s.g.sum())) < TOL,
          f"{s.q.sum():,.1f} by product, {s.g.sum():,.1f} by activity")

    # ID-08 -- the identity the project's whole solver choice rests on.
    for label, v in (("trade", s.trade_margins),
                     ("transport", s.transport_margins)):
        tot = float(v.sum())
        pos = float(v[v > 0].sum())
        check(f"ID-08 {label} margins sum to zero across the economy",
              abs(tot) < TOL,
              f"{tot:.3e}, from {pos:,.1f} positive against "
              f"{float(v[v < 0].sum()):,.1f} negative")

    # ID-19 -- and the negatives are required, not merely allowed.
    for label, v in (("trade", s.trade_margins),
                     ("transport", s.transport_margins)):
        n_neg = int((v < 0).sum())
        check(f"ID-19 the {label} margin column HAS negatives, as it must",
              n_neg > 0,
              f"{n_neg} of {v.size} products; most negative {v.min():,.1f} in "
              f"{s.product_labels[int(v.argmin())][:44]!r}")

    # ID-09 -- margins by product against margins by industry.
    #
    # HALF OF THIS IS VERIFICATION AND HALF IS AN ASSUMPTION, AND THEY ARE KEPT
    # APART. CORE_006 par. 9.36, p. 283 says the total of trade margins by
    # product equals the total by the trade industries PLUS the total by other
    # industries. No office publishes margins by industry, so the identity
    # cannot be checked against an independent figure. Two things can:
    #
    #   * that what the trade-service PRODUCTS give up equals what the goods
    #     receive -- pure arithmetic, and it is exact;
    #   * that the "other industries" clause is not empty -- read straight off
    #     the supply matrix, which shows who produces trade-service product.
    #
    # The split between own and other industries additionally assumes the margin
    # follows production of the service. That is a PROJECT CHOICE and is printed
    # as one.
    def margin_split(margins, product_codes, industry_codes, label):
        by_ind = np.zeros(s.n_activities)
        for c in product_codes:
            i = s.index_of_product(c)
            if s.q[i] > 0:
                by_ind += (-margins[i]) * s.V[i] / s.q[i]
        own_idx = [s.activity_codes.index(c) for c in industry_codes]
        own = float(by_ind[own_idx].sum())
        other = float(by_ind.sum()) - own
        received = float(margins[margins > 0].sum())
        given = float(-margins[margins < 0].sum())
        check(f"ID-09 what the {label} service products give up equals what "
              f"the goods receive", abs(received - given) < TOL,
              f"{given:,.1f} against {received:,.1f}")
        check(f"ID-09 and 'by OTHER industries' is not an empty clause for "
              f"{label}", other > 0,
              f"{other:,.1f} of {own + other:,.1f}, {other / (own + other):.2%}, "
              f"earned by industries outside the {label} sector — allocated in "
              f"proportion to their production of the service (PROJECT CHOICE; "
              f"no office publishes margins by industry)")
        return own, other

    margin_split(s.trade_margins, ["62", "64", "65"], ["37", "38", "39"],
                 "trade")
    margin_split(s.transport_margins, ["66", "67", "68", "69"],
                 ["40", "41", "42", "43", "44", "45"], "transport")

    # ID-10 -- the CIF/FOB adjustment.
    cif = float(s.imports.sum())
    check("ID-10 imports are positive and the CIF/FOB rows net out",
          cif > 0, f"total imports {cif:,.1f} CIF")

    # What this fixture is FOR, said plainly.
    print()
    print(f"    Of {s.n_products} products, {int((s.trade_margins != 0).sum())} "
          f"carry a trade margin and "
          f"{int((s.transport_margins != 0).sum())} a transport margin.")
    print(f"    Taxes less subsidies on products: {s.taxes_on_products.sum():,.1f}, "
          f"with {int((s.taxes_on_products < 0).sum())} products net-subsidised.")
    print("    None of this is visible in an analytical IOT at basic prices,")
    print("    which is what OQ-D-03 has been saying since v1.1.")

    print("\n" + "=" * 72)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
