"""
The six-pack, and the four CORE_012 diagnostics that were waiting for it.

WHAT WAS MISSING
-----------------
`run_uk_diagnostics.py` reports **8 of 13** checks NOT APPLICABLE, and most of
them for one reason: they run on the **six-pack** — three price-period values
for every cell (CORE_012 ¶11.29 and Figure 11.2, p. 325):

    v[t, p_t]        year t at current prices
    v[t, p_{t-1}]    year t in the prices of t-1
    v[t-1, p_{t-1}]  year t-1 at current prices

The project held current prices for one year. Two of the three values did not
exist anywhere in its data, so `ID-16`, `D3`, `D5` and `D2d` could only ever
report that they had nothing to run on.

WHERE THE MISSING TWO CAME FROM
---------------------------------
Eurostat publishes **`naio_10_pyp16` — "Use table at purchasers' prices
(previous years prices)"**, the middle value, on the same API the project's
connector already speaks. With `naio_10_cp16` for `t` and for `t-1`, the
six-pack is complete. Fetched 2026-08-13 for **Austria and Spain, 2022 against
2021**; provenance in `data/eurostat/README.md`.

WHAT RUNS NOW
---------------
    ID-16  value index = price index x volume index / 100, cell by cell
    D3     volume change of output against volume change of intermediate
           consumption, by industry
    D5     price change dispersion across users, by product
    D2d    change in the GVA/output ratio against t-1

**ID-16 is arithmetic, and its content is the suppression rule.** Given three
stored values the identity cannot fail — `(a/c) = (a/b)·(b/c)` — so a PASS at
1e-13 says the data is a real six-pack, not that the accounts are right. What
the check is actually for is the quarter of cells where a base is zero or
negative and an index must be refused rather than printed: **CORE_012's own
Table A11.2, p. 354 prints 568.8 and −100.0** because the chapter applies no
such guard. Here 970 of 4,290 cells for Austria and 1,241 for Spain are
suppressed, and that is the finding.

THE PRECONDITION NOBODY CAN CHECK, RESTATED
---------------------------------------------
The identities hold in volume terms only under "the combination of the
Laspeyres volume index and Paasche price index formula" (CORE_012 ¶11.17,
p. 323). Nothing in the data says which pairing Eurostat's previous-years'-
prices tables use. `id16_six_pack` says the caller must verify it; **this caller
cannot**, and records that rather than assuming it.

WHAT IS STILL NOT APPLICABLE, AND ONE NEAR-MISS WORTH KEEPING
---------------------------------------------------------------
`ID-15` and `D2c` need the valuation matrices; `S4` needs the legal VAT rates.
Neither is in any table this project holds.

**`D4` (labour productivity) is still NOT APPLICABLE, and it nearly was not.**
The use table carries a row coded `LE`, and a first pass took it for labour
input and ran the check: 48 industries flagged for Spain, worst 284 %. `LE` is
**"Closing balance sheet"**. The flags were an artefact of joining a
balance-sheet row to a productivity formula, and the numbers looked plausible
enough to publish. Labour input needs a different dataset and a deliberate
decision about the statistical unit — which is exactly what CORE_012 ¶11.20,
p. 323 warns about and what `d4_labour_productivity`'s own docstring says the
function cannot check.

Run:
    python3 validators/run_six_pack.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

import diagnostics as dg  # noqa: E402
from quadrium.eurostat import _Cube, _coarsest_tiling  # noqa: E402

DATA = ROOT / "data" / "eurostat"
COUNTRIES = (("AT", "Austria"), ("ES", "Spain"))
YEAR, PRIOR = 2022, 2021

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def cube(name: str):
    path = DATA / name
    return _Cube(json.loads(path.read_text())) if path.exists() else None


def six_pack(geo: str):
    """(products, industries, U[t,p_t], U[t,p_{t-1}], U[t-1,p_{t-1}], rows)."""
    a = cube(f"naio_10_cp16_{geo}_{YEAR}.json")
    b = cube(f"naio_10_pyp16_{geo}_{YEAR}.json")
    c = cube(f"naio_10_cp16_{geo}_{PRIOR}.json")
    if not (a and b and c):
        return None

    products = [p for p in a.index["prd_ava"]
                if p.startswith("CPA_") and p != "CPA_TOTAL"]
    products, _ = _coarsest_tiling(products)
    industries = [i for i in a.index["ind_use"]
                  if not i.startswith(("TU", "P3", "P5", "P6", "P7", "TOTAL"))
                  and a.at(stk_flow="TOTAL", prd_ava=products[0], ind_use=i)
                  is not None]
    industries, _ = _coarsest_tiling(industries)

    def at(cb, row, ind):
        v = cb.at(stk_flow="TOTAL", prd_ava=row, ind_use=ind)
        return np.nan if v is None else float(v)

    def mat(cb):
        return np.array([[at(cb, p, i) for i in industries] for p in products],
                        float)

    def vec(cb, row):
        return np.array([at(cb, row, i) for i in industries], float)

    return products, industries, mat(a), mat(b), mat(c), (a, b, c, vec)


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    ran = 0
    for geo, name in COUNTRIES:
        pack = six_pack(geo)
        if pack is None:
            print(f"\n    {name}: the six-pack files are not in data/eurostat "
                  f"— skipped")
            continue
        ran += 1
        products, industries, Ua, Ub, Uc, (a, b, c, vec) = pack
        print(f"\n    {name} {YEAR} against {PRIOR} — "
              f"{len(products)} products x {len(industries)} industries")

        # ---- ID-16, cell by cell -------------------------------------------
        r16 = dg.id16_six_pack(Ua, Ub, Uc)
        print(f"      ID-16  {r16.status:<4} {r16.detail}")
        check(f"{name}: ID-16 runs on real data instead of reporting nothing "
              f"to run on",
              r16.status == "PASS" and r16.worst < 1e-6,
              f"worst deviation {r16.worst:.2e} over the tested cells — the "
              f"identity is arithmetic, so what this establishes is that the "
              f"three values are a genuine six-pack")

        suppressed = int(r16.detail.split("cells tested, ")[1].split(" ")[0])
        check(f"{name}: and it refuses an index where the base is zero or "
              f"negative",
              suppressed > 0,
              f"{suppressed} of {Ua.size} cells suppressed — CORE_012's own "
              f"Table A11.2, p. 354 prints 568.8 and −100.0 for want of this "
              f"guard")

        # ---- D3, by industry ------------------------------------------------
        vol_ic = 100.0 * np.nansum(Ub, 0) / np.nansum(Uc, 0)
        vol_out = 100.0 * vec(b, "P1") / vec(c, "P1")
        ok = np.isfinite(vol_ic) & np.isfinite(vol_out)
        r3 = dg.d3_volume_change_coherence(vol_out[ok], vol_ic[ok])
        print(f"      D3     {r3.status:<4} {r3.n_flagged} of {int(ok.sum())} "
              f"industries beyond 5 index points, worst {r3.worst:.1f}")
        check(f"{name}: D3 has volume indices to compare",
              r3.status in ("PASS", "FLAG") and int(ok.sum()) > 40,
              f"{int(ok.sum())} industries carry both volume changes; the "
              f"source expects them to move together and says a large "
              f"difference means 'further investigation is advisable'")

        # ---- D5, by product -------------------------------------------------
        price = 100.0 * np.where(np.abs(Ub) > 1e-9, Ua / Ub, np.nan)
        flagged = 0
        tested = 0
        for row in price:
            if np.isfinite(row).sum() < 5:
                continue
            tested += 1
            r5 = dg.d5_price_dispersion(row)
            flagged += r5.n_flagged
        print(f"      D5     {flagged} user-price outliers across {tested} "
              f"products")
        check(f"{name}: D5 can measure price dispersion across users",
              tested > 40,
              f"{tested} products have enough users to compare; {flagged} "
              f"user prices sit beyond the MAD threshold")

        # ---- D2d, the ratio change ------------------------------------------
        ratio_t = vec(a, "B1G") / vec(a, "P1")
        ratio_p = vec(c, "B1G") / vec(c, "P1")
        d = np.abs(ratio_t - ratio_p)
        moved = int(np.nansum(d > 0.05))
        print(f"      D2d    {moved} industries move their GVA/output ratio by "
              f"more than 5 points, worst {np.nanmax(d):.3f}")
        check(f"{name}: D2d has a second year to compare against",
              np.isfinite(d).sum() > 40,
              f"{int(np.isfinite(d).sum())} industries carry the ratio in both "
              f"years — the check needed t−1 and had none")

    if not ran:
        print("\n    no six-pack available — nothing to do.")
        return 0

    print()
    print("    Still NOT APPLICABLE: ID-15 and D2c need the valuation")
    print("    matrices, S4 needs the legal VAT rates, and D4 needs labour")
    print("    input — the `LE` row of this table is 'Closing balance sheet',")
    print("    not employment, and a first pass that mistook it flagged 48")
    print("    industries at up to 284 %. Plausible, and an artefact.")
    print()
    print("    UNVERIFIED PRECONDITION: CORE_012 ¶11.17, p. 323 holds these")
    print("    identities only under a Laspeyres volume / Paasche price")
    print("    pairing. Nothing in the data states the pairing, and this")
    print("    caller cannot check it. D_open_questions.md OQ-D-03.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
