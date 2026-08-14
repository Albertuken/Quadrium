"""
`OQ-C-04`, supply half: what a compiler actually does, and one claim it makes.

CORE_008 is the UN Handbook chapter on compiling the supply table. It was
extracted and unread — the twelfth such file found this way, after CORE_001
closed `OQ-C-02` the same way. Written up as `B_method_cards/M-059`.

THE CLAIM THIS FILE TESTS
--------------------------
CORE_008 Box 5.1, p. 144: "In France, the first step (redefinition) is based on
enterprise units and is carried out to an extent that **the supply table becomes
diagonal**. The use tables thereby also form the IOTs, and the second step
(compiling the IOTs) becomes superfluous."

Redefinition is the compiler moving secondary production, and the inputs that
produced it, into the industry where that product is primary (Miller and Blair
2009, p. 141, quoted in Box 5.1). Do it far enough and there is no secondary
production left to reallocate, so the transformation models A–E have nothing to
do. That is a strong claim about a real country and it can be checked against
Eurostat `naio_10_cp15`.

WHAT WAS FOUND, AND WHAT WAS NOT
---------------------------------
**The France claim holds and is not close.** 98.4 % of the French supply matrix
lies on the diagonal, against 84.6 %–93.6 % for the five comparators. French
secondary production is six times smaller than Spanish.

**Box 5.1's other three countries do NOT line up, and the first draft of `M-059`
claimed they did.** That claim was wrong and is recorded rather than removed.
Denmark, which Box 5.1 says uses the redefinition method, is 89.3 % diagonal;
Norway, which it calls "more of the case 1 type" — no redefinitions — is 93.6 %,
*more* diagonal than Denmark and than Spain. The Netherlands, placed "somewhere
between case 1 and case 2", is the least diagonal of the six.

Three readings fit and the data chooses none: practices may have changed since
2018; diagonality may be a poor proxy for redefinition effort, since a country
with genuinely little secondary production needs no redefinitions to look
diagonal; or Box 5.1's remarks on those three may concern how their
industry-by-industry IOTs are built rather than their supply tables.
`NOT SPECIFIED`.

WHY THE NUMBER MATTERS BEYOND FRANCE
-------------------------------------
Off-diagonal supply is the only thing a transformation model can move. Its share
is therefore an **upper bound on how much the choice between models A, B, C, D
and E can change the answer** — 1.6 % for France, 15.4 % for the Netherlands.
`OQ-T-03` records two rank-1 sources disagreeing about model choice; this says
what that disagreement is worth, and it is not one number.

Run:
    python3 validators/run_supply_compilation.py
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

# Rows of `ind_impv` that are valuation or total columns, not industries.
_NOT_INDUSTRY = {"TOTAL", "OTTM", "D21X31", "TS_BP", "P1", "IMP"}


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def diagonality(geo: str, year: int = 2022):
    """Share of the supply matrix sitting on its own product/industry pairing."""
    from quadrium.eurostat import _Cube
    p = DATA / f"naio_10_cp15_{geo}_{year}.json"
    if not p.exists():
        return None
    cube = _Cube(json.loads(p.read_text()))
    prods = [c for c in cube.index["prd_amo"]
             if c.startswith("CPA_") and c != "CPA_TOTAL"]
    inds = {c for c in cube.index["ind_impv"]
            if not c.startswith("CPA_") and c not in _NOT_INDUSTRY}
    pairs = [(p_, p_[4:]) for p_ in prods if p_[4:] in inds]
    if len(pairs) < 20:
        return None
    V = np.array([[cube.at(ind_impv=i, prd_amo=p_) or 0.0 for _, i in pairs]
                  for p_, _ in pairs], float)
    total = V.sum()
    if total <= 0:
        return None
    return len(pairs), float(np.trace(V) / total), total


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    results = {}
    for geo in ("FR", "NO", "ES", "AT", "DK", "NL"):
        r = diagonality(geo)
        if r:
            results[geo] = r
    if not results:
        print("no `naio_10_cp15` fixture available")
        return 0

    print(f"  {'country':<9}{'pairs':>7}{'on diagonal':>14}"
          f"{'secondary':>12}{'supply, M EUR':>16}")
    for geo, (n, d, tot) in sorted(results.items(), key=lambda kv: -kv[1][1]):
        print(f"  {geo:<9}{n:>7}{d:>13.2%}{1 - d:>12.2%}{tot:>16,.0f}")
    print()

    fr = results.get("FR")
    check("Box 5.1's France claim holds on published data",
          fr is not None and fr[1] > 0.97,
          f"{fr[1]:.2%} of the French supply matrix is on the diagonal, "
          f"leaving {1 - fr[1]:.2%} secondary production"
          if fr else "FR fixture absent")
    others = {g: v[1] for g, v in results.items() if g != "FR"}
    check("and France is clear of the whole field, not marginally ahead",
          fr is not None and fr[1] > max(others.values()) + 0.04,
          f"next is {max(others, key=others.get)} at "
          f"{max(others.values()):.2%}; the field spans "
          f"{min(others.values()):.2%}–{max(others.values()):.2%}")
    es = results.get("ES")
    check("French secondary production is ~6x smaller than Spanish",
          fr and es and 4 < (1 - es[1]) / (1 - fr[1]) < 8,
          f"{(1 - fr[1]):.2%} against {(1 - es[1]):.2%}, a factor of "
          f"{(1 - es[1]) / (1 - fr[1]):.1f}")

    # The negative finding, kept as a check so it cannot quietly disappear.
    dk, no_ = results.get("DK"), results.get("NO")
    if dk and no_:
        check("Box 5.1's OTHER countries do not line up, and M-059 first said "
              "they did",
              no_[1] > dk[1],
              f"Denmark is said to use redefinitions and measures {dk[1]:.2%}; "
              f"Norway is called 'case 1' — no redefinitions — and measures "
              f"{no_[1]:.2%}, MORE diagonal. Either practice changed since "
              f"2018, or diagonality is a poor proxy for redefinition effort, "
              f"or Box 5.1 is describing their IOTs rather than their supply "
              f"tables. NOT SPECIFIED")

    # The bound, which is the reusable part.
    print()
    print("    Upper bound on what the transformation model can move")
    print("    (nothing off the diagonal, nothing to reallocate):")
    for geo, (_, d, _) in sorted(results.items(), key=lambda kv: kv[1][1]):
        print(f"      {geo}  at most {1 - d:.2%} of supply")
    spread = max(1 - v[1] for v in results.values()) / \
        min(1 - v[1] for v in results.values())
    check("that ceiling varies by an order of magnitude between publishers",
          spread > 8,
          f"{spread:.0f}x between the widest and the narrowest — so 'which "
          f"transformation model' is a question worth very different amounts "
          f"in different countries (OQ-T-03)")

    print()
    print("    Also in CORE_008 and not testable here:")
    print("      ¶5.54, p. 143 — redefinitions are done BY HAND on purpose,")
    print("        because automatic methods 'give rise to negative elements'.")
    print("        Second rank-1 source to say so; NSO_AT_01 was the first.")
    print("      ¶5.52, p. 143 — with enterprise-based source data it may be")
    print("        decided 'to compile SUTs alone and not IOTs'.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
